"""Read-only recursive fund exposure over pinned canonical observations."""

from datetime import date
from decimal import Decimal, localcontext

from invest.models import DomainError, decimal

FUNDS = {'ETF', 'MUTUAL_FUND'}


def _day(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        raise DomainError('Exposure dates must be ISO dates') from None


def _text(value):
    result = format(value, 'f')
    return result.rstrip('0').rstrip('.') if '.' in result else result


def exposure(state, observations, *, as_of, max_age_days=120, max_depth=8):
    """Preserve each path; unknown holdings are never redistributed or normalized."""
    if not isinstance(max_depth, int) or not 1 <= max_depth <= 8:
        raise DomainError('Look-through depth must be between one and eight')
    if not isinstance(max_age_days, int) or max_age_days < 0:
        raise DomainError('Holdings age must be a nonnegative number of days')
    reporting_day = _day(as_of)
    securities = {row['id']: row for row in state.get('securities', [])}
    accounts = {row['id']: row for row in state.get('accounts', [])}
    currencies = {row.get('currency', 'USD') for row in accounts.values()}
    for table in ('positions', 'cash_balances'):
        for row in state.get(table, []):
            currencies.add(row.get('currency') or accounts.get(row['account_id'], {}).get(
                'currency', 'USD'))
    if len(currencies) > 1:
        raise DomainError('Exposure currencies differ; verified FX model required', 3)
    currency = next(iter(currencies), 'USD')
    rows, issues = {}, []
    unknown = Decimal(0)
    stale = Decimal(0)
    unresolved = Decimal(0)
    sectors, assets = {}, {}
    values = [decimal(row['market_value']) for row in state.get('positions', [])]
    values.extend(decimal(row['amount']) for row in state.get('cash_balances', []))
    weights = [decimal(holding['weight']) for observation in observations.values()
               for holding in observation.get('holdings', [])]
    precision = max(80, sum(len(number.as_tuple().digits) + abs(number.as_tuple().exponent)
                            for number in values + weights) + max_depth * 40)
    with localcontext() as context:
        context.prec = precision
        total = sum(values, Decimal(0))

    def issue(code, security_id, value, path):
        issues.append({'code': code, 'security_id': security_id, 'value': _text(value),
                       'path': path, 'blocks_calculation': False,
                       'blocks_proposals': True, 'blocks_execution_review': True})

    def missing(code, sid, value, path):
        nonlocal unknown, stale
        unknown += value
        if code == 'STALE_HOLDINGS':
            stale += value
        issue(code, sid, value, path)

    def visit(sid, value, path, evidence, depth, ancestors, direct=False):
        nonlocal unresolved
        security = securities.get(sid, {})
        asset = security.get('asset_type', evidence.get('asset_type', 'OTHER'))
        observation = observations.get(sid)
        if asset in FUNDS or observation is not None:
            if sid in ancestors:
                return missing('FUND_CYCLE', sid, value, path)
            if depth >= max_depth:
                return missing('MAX_LOOKTHROUGH_DEPTH', sid, value, path)
            if observation is None:
                return missing('UNKNOWN_HOLDINGS', sid, value, path)
            if observation.get('currency', currency) != currency:
                raise DomainError('Underlying holdings currency differs; FX model required', 3)
            if observation.get('published_at') and _day(observation['published_at']) > reporting_day:
                return missing('FUTURE_PUBLICATION', sid, value, path)
            if not observation.get('as_of'):
                return missing('UNKNOWN_HOLDINGS_DATE', sid, value, path)
            observed = _day(observation['as_of'])
            if observed > reporting_day:
                return missing('FUTURE_OBSERVATION', sid, value, path)
            if (reporting_day - observed).days > max_age_days:
                return missing('STALE_HOLDINGS', sid, value, path)
            holdings = observation.get('holdings', [])
            weights = [decimal(row['weight']) for row in holdings]
            if any(weight < 0 for weight in weights) or sum(weights, Decimal(0)) > 1:
                raise DomainError('Fund weights must be nonnegative and sum to at most one', 2)
            if len({row['security_id'] for row in holdings}) != len(holdings):
                raise DomainError('Duplicate canonical holdings require source resolution', 2)
            provenance = {key: observation.get(key) for key in (
                'as_of', 'published_at', 'source_id', 'source_hash', 'data_environment')}
            next_path = path + [{'security_id': sid, **provenance}]
            for holding, weight in zip(holdings, weights, strict=True):
                visit(holding['security_id'], value * weight, next_path,
                      holding, depth + 1, ancestors | {sid})
            residual = value * (1 - sum(weights, Decimal(0)))
            if residual:
                missing('PARTIAL_HOLDINGS', sid, residual, next_path)
            return
        if asset not in {'STOCK', 'CASH', 'BOND', 'TREASURY'}:
            return missing('UNRESOLVED_SECURITY', sid, value, path)
        issuer = evidence.get('issuer_id') if evidence.get('issuer_verified') is True else None
        if not issuer and security.get('issuer_identity_evidence') and security.get('issuer_id'):
            issuer = security['issuer_id']
        key = issuer or sid
        row = rows.setdefault(key, {'security_id': sid, 'ticker': security.get('ticker'),
                                    'issuer_id': issuer, 'asset_type': asset,
                                    'direct_value': Decimal(0), 'indirect_value': Decimal(0),
                                    'total_value': Decimal(0), 'contributions': []})
        row['direct_value' if direct else 'indirect_value'] += value
        row['total_value'] += value
        row['contributions'].append({'value': _text(value), 'path': path,
                                     'security_id': sid, 'direct': direct})
        assets[asset] = assets.get(asset, Decimal(0)) + value
        sector = evidence.get('sector') or security.get('sector') or 'UNKNOWN'
        sectors[sector] = sectors.get(sector, Decimal(0)) + value
        if asset == 'STOCK' and issuer is None:
            unresolved += value
            issue('UNRESOLVED_ISSUER', sid, value, path)

    with localcontext() as context:
        context.prec = precision
        for position in state.get('positions', []):
            sid = position.get('security_id') or position['security']
            visit(sid, decimal(position['market_value']),
                  [{'account_id': position['account_id'], 'holding_as_of': position.get('as_of')}],
                  position, 0, set(), direct=True)
        for cash in state.get('cash_balances', []):
            visit('CASH', decimal(cash['amount']), [{'account_id': cash['account_id']}],
                  {'asset_type': 'CASH'}, 0, set(), direct=True)
        output = []
        for row in rows.values():
            result = {key: _text(value) if isinstance(value, Decimal) else value
                      for key, value in row.items()}
            result['percentage'] = _text(row['total_value'] / total * 100) if total else None
            output.append(result)
        output.sort(key=lambda row: (-decimal(row['total_value']),
                                     row['issuer_id'] or row['security_id']))
        return {'as_of': str(reporting_day), 'currency': currency,
                'total_value': _text(total), 'exposures': output,
                'unknown_exposure_value': _text(unknown),
                'unknown_exposure_percentage': _text(unknown / total * 100) if total else None,
                'stale_exposure_value': _text(stale), 'unresolved_issuer_value': _text(unresolved),
                'complete': unknown == 0 and unresolved == 0,
                'by_sector': {key: _text(value) for key, value in sorted(sectors.items())},
                'by_asset_type': {key: _text(value) for key, value in sorted(assets.items())},
                'issues': issues, 'status': 'PARTIAL' if issues else 'AVAILABLE'}


def research_universe(state, observations, *, as_of, top=20, min_exposure='0.01', **kwargs):
    """Select verified operating issuers using the whole known household denominator."""
    if isinstance(top, bool) or not isinstance(top, int) or top < 1:
        raise DomainError('Research universe top must be a positive integer')
    minimum = decimal(min_exposure)
    if not 0 <= minimum <= 1:
        raise DomainError('Minimum exposure must be a fraction between zero and one')
    result = exposure(state, observations, as_of=as_of, **kwargs)
    with localcontext() as context:
        context.prec = max(80, len(result['total_value']) + len(str(minimum)) +
                           sum(len(row['total_value']) for row in result['exposures']))
        total = decimal(result['total_value'])
        eligible = [row for row in result['exposures'] if row['asset_type'] == 'STOCK'
                    and row['issuer_id'] is not None]
        qualifying = [row for row in eligible if decimal(row['total_value']) >= minimum * total]
        selected = qualifying[:top]
        selected_ids = {row['issuer_id'] for row in selected}
        result.update(companies=selected, requested_top=top, min_exposure=_text(minimum),
                      filtered_exposure_value=_text(sum((decimal(row['total_value'])
                          for row in eligible if row['issuer_id'] not in selected_ids), Decimal(0))),
                      detected_company_count=len(eligible), selected_company_count=len(selected))
    return result
