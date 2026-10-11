"""Immutable hypothetical buy-and-hold experiments over aligned total-return evidence."""

import copy
import hashlib
import json
import math
import statistics
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal, localcontext
from fractions import Fraction

from invest.ledger import household_currency
from invest.models import DomainError, decimal

ALGORITHM = 'buy-and-hold-total-return-1'


def _text(value):
    rendered = format(value, 'f')
    return rendered.rstrip('0').rstrip('.') if '.' in rendered else rendered


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), default=str)


def _hash(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _issue(code, message):
    return {'code': code, 'message': message, 'blocks_calculation': True,
            'blocks_proposals': True, 'blocks_execution_review': True}


def run(ledger, *, portfolio, start, end, policy, manifest):
    """Save reproducible hypothetical results; never mutate actual financial inputs."""
    from invest.db import SCHEMA_VERSION

    foundation = ledger.connection.execute(
        "SELECT checksum FROM schema_migrations WHERE id='001'").fetchone()
    if foundation is None:
        raise DomainError('Backtest requires verified foundation schema identity', 3)
    storage_identity = {'schema_version': SCHEMA_VERSION, 'manifest_hash': foundation[0]}
    try:
        first, last = date.fromisoformat(start), date.fromisoformat(end)
    except ValueError:
        raise DomainError('Backtest dates must be ISO dates') from None
    if first >= last:
        raise DomainError('Backtest end must follow start')
    policy, manifest = copy.deepcopy(policy), copy.deepcopy(manifest)
    state = ledger.planning_state()
    household_currency(state)
    issues = []
    cash_return = decimal(policy.get('cash_return', '0'))
    slippage = decimal(policy.get('slippage', '0'))
    requested_taxes = policy.get('modeled_taxes', policy.get('taxes', False))
    if cash_return != 0:
        issues.append(_issue('UNSUPPORTED_CASH_RETURN_MODEL',
                             'MVP historical cash earns zero; nonzero return needs an explicit supported unit and model'))
    if slippage != 0:
        issues.append(_issue('UNSUPPORTED_SLIPPAGE_MODEL',
                             'MVP historical execution models zero slippage only'))
    if requested_taxes not in (False, None):
        issues.append(_issue('UNSUPPORTED_BACKTEST_TAX_MODEL',
                             'MVP hypothetical returns do not model taxes'))
    numeric_values = [decimal(row['total_return_index'])
                      for rows in manifest.get('series', {}).values() for row in rows
                      if 'total_return_index' in row]
    numeric_values.extend(decimal(row['market_value']) for row in state['positions'])
    numeric_values.extend(decimal(row['amount']) for row in state['cash_balances'])
    numeric_values.extend(decimal(event['amount']) for event in policy.get('contribution_schedule', []))
    numeric_values.extend(decimal(policy.get(key, default)) for key, default in (
        ('starting_value', '10000'), ('fee_per_trade', '0')))
    precision = max(100, max((len(value.as_tuple().digits) + abs(value.as_tuple().exponent)
                              for value in numeric_values), default=0) * 3 + 32)
    with localcontext() as context:
        context.prec = precision
        if portfolio == 'current':
            values = {}
            for position in state['positions']:
                sid = position['security_id']
                values[sid] = values.get(sid, Decimal(0)) + decimal(position['market_value'])
            values['CASH'] = sum((decimal(row['amount']) for row in state['cash_balances']), Decimal(0))
            total = sum(values.values(), Decimal(0))
            if total <= 0:
                raise DomainError('Current allocation requires a positive known valuation', 3)
            weights = {sid: value / total for sid, value in values.items() if value}
            mode = 'HYPOTHETICAL_CURRENT_ALLOCATION'
        else:
            if isinstance(portfolio, str):
                from invest.targets import show

                target_id, separator, version = portfolio.partition('@')
                target = show(ledger, target_id, version=int(version) if separator else None)
                allocation = target['target_allocations']
            else:
                allocation = portfolio
            weights = {sid: decimal(value) for sid, value in allocation.items() if decimal(value)}
            mode = 'HYPOTHETICAL_TARGET_ALLOCATION'
            total = decimal(policy.get('starting_value', '10000'))
        if any(value < 0 for value in weights.values()) or abs(sum(
                weights.values(), Decimal(0)) - 1) > Decimal('0.000001'):
            raise DomainError('Backtest weights must be fractions totaling one')
        fee = decimal(policy.get('fee_per_trade', '0'))
        if fee < 0 or total <= 0:
            raise DomainError('Starting value must be positive and fees nonnegative')
        schedule = policy.get('contribution_schedule', [])
        contributions = {}
        for event in schedule:
            day = event['date']
            amount = decimal(event['amount'])
            if amount < 0 or not start <= day <= end:
                raise DomainError('Contribution dates and amounts must fit the requested period')
            contributions[day] = contributions.get(day, Decimal(0)) + amount
        series = manifest.get('series', {})
        environment = manifest.get('data_environment')
        observed_environments = {row.get('data_environment', environment)
                                 for rows in series.values() for row in rows}
        if environment not in {'REAL', 'SYNTHETIC'} or observed_environments - {environment}:
            issues.append(_issue('MIXED_DATA_ENVIRONMENT', 'History needs one explicit source environment'))
        if manifest.get('currency', household_currency(state)) != household_currency(state):
            issues.append(_issue('UNSUPPORTED_CURRENCY', 'History currency requires a verified FX model'))
        known_ids = {security['id'] for security in state['securities']} | {'CASH'}
        if set(weights) - known_ids:
            issues.append(_issue('UNRESOLVED_SECURITY', 'Historical allocation needs canonical securities'))
        if portfolio == 'current' and any(not any(cash['account_id'] == account['id']
                for cash in state['cash_balances']) for account in state['accounts']):
            issues.append(_issue('UNKNOWN_CASH_COVERAGE', 'Current allocation excludes unknown account cash'))
        sessions = manifest.get('sessions')
        if sessions is None:
            sessions = sorted({row['date'] for rows in series.values() for row in rows
                               if start <= row['date'] <= end})
            calendar_coverage = 'PROVIDER_OBSERVED_SESSIONS_ONLY'
        else:
            calendar_coverage = 'EXPLICIT_PINNED_SESSIONS'
            if sessions != sorted(set(sessions)):
                raise DomainError('Pinned sessions must be unique and increasing')
            sessions = [day for day in sessions if start <= day <= end]
        if not sessions or sessions[0] != start or sessions[-1] != end:
            issues.append(_issue('MISSING_HISTORY', 'Requested endpoints are not supplied sessions'))
        if any(day not in sessions for day in contributions):
            issues.append(_issue('MISSING_HISTORY', 'Contributions require a supplied session'))
        indexes = {}
        for sid in sorted(weights):
            if sid == 'CASH':
                continue
            rows = series.get(sid, [])
            if len({row['date'] for row in rows}) != len(rows):
                raise DomainError('Duplicate total-return observations', 2)
            selected = {row['date']: row for row in rows if row['date'] in sessions}
            if set(selected) != set(sessions):
                issues.append(_issue('MISSING_HISTORY', f'Incomplete pinned sessions for {sid}'))
                continue
            if any('total_return_index' not in row for row in selected.values()):
                issues.append(_issue('UNVERIFIED_TOTAL_RETURN', f'Total-return evidence missing for {sid}'))
                continue
            indexes[sid] = {day: decimal(row['total_return_index']) for day, row in selected.items()}
            if any(value <= 0 for value in indexes[sid].values()):
                issues.append(_issue('INVALID_TOTAL_RETURN_INDEX', f'Nonpositive return index for {sid}'))
        frequency = policy.get('rebalance_frequency', 'BUY_AND_HOLD')
        if frequency not in {'BUY_AND_HOLD', 'QUARTERLY'}:
            raise DomainError('Supported historical frequencies are BUY_AND_HOLD and QUARTERLY')
        trigger = decimal(policy.get('drift_trigger', '0.05'))
        if not 0 <= trigger <= 1:
            raise DomainError('Historical drift trigger must be a fraction')
        assumptions = {
            'cash_return': _text(cash_return), 'fee_per_trade': _text(fee),
            'contribution_schedule': [{'date': day, 'amount': _text(value)}
                                      for day, value in sorted(contributions.items())],
            'dividends': 'REINVESTED_TOTAL_RETURN_INDEX', 'external_contributions': bool(contributions),
            'slippage': _text(slippage), 'modeled_taxes': requested_taxes,
            'rebalance_frequency': frequency,
            'drift_trigger': _text(trigger),
            'benchmark': policy.get('benchmark'), 'survivorship_free': False,
            'session_coverage': calendar_coverage}
        inputs = {'portfolio': portfolio, 'weights': {sid: _text(value) for sid, value in weights.items()},
                  'policy': policy, 'manifest': manifest, 'start': start, 'end': end,
                  'algorithm': ALGORITHM, 'state': state if portfolio == 'current' else None}
        comparison = {'start': start, 'end': end, 'sessions': sessions, 'assumptions': assumptions,
                      'manifest_id': manifest.get('id'), 'manifest_hash': _hash(manifest),
                      'security_universe': sorted(series), 'algorithm': ALGORITHM,
                      'storage_identity': storage_identity}
        result = {'id': str(uuid.uuid4()), 'created_at': datetime.now(timezone.utc).isoformat(),
                  'mode': mode, 'status': 'UNAVAILABLE' if issues else 'AVAILABLE',
                  'start': start, 'end': end, 'assumptions': assumptions, 'issues': issues,
                  'manifest_id': manifest.get('id'), 'source_hash': _hash(inputs),
                  'storage_identity': storage_identity,
                  'algorithm_version': ALGORITHM, 'total_return': None, 'annualized_return': None,
                  'volatility': None, 'max_drawdown': None, 'final_allocation': None,
                  'turnover': None, 'tracking_dates': sessions, 'statistics_method': 'FLOAT64_DAILY_252',
                  'data_environment': manifest.get('data_environment')}
        if not issues:
            cash = total * weights.get('CASH', Decimal(0))
            holdings = {sid: total * weight / indexes[sid][start]
                        for sid, weight in weights.items() if sid != 'CASH'}
            initial_fees = fee * len(holdings)
            if cash < initial_fees:
                # Fees reduce deployed capital proportionally; no borrowed cash.
                available = total - initial_fees
                if available <= 0:
                    raise DomainError('Fees exhaust hypothetical starting capital')
                cash = available * weights.get('CASH', Decimal(0))
                holdings = {sid: available * weight / indexes[sid][start]
                            for sid, weight in weights.items() if sid != 'CASH'}
            else:
                cash -= initial_fees
            cumulative = Fraction(1)
            previous = total
            returns, curve = [], []
            turnover = total * (1 - weights.get('CASH', Decimal(0)))
            peak = Fraction(1)
            drawdown = Fraction(0)
            last_rebalanced = None
            for day in sessions:
                contribution = contributions.get(day, Decimal(0))
                if contribution:
                    purchase_fees = fee * len(holdings)
                    available = contribution - purchase_fees
                    if available < 0:
                        raise DomainError('Fees exceed contribution')
                    cash += available * weights.get('CASH', Decimal(0))
                    for sid in holdings:
                        holdings[sid] += available * weights[sid] / indexes[sid][day]
                    turnover += available * (1 - weights.get('CASH', Decimal(0)))
                value = cash + sum((quantity * indexes[sid][day]
                                    for sid, quantity in holdings.items()), Decimal(0))
                month = date.fromisoformat(day).month
                period = day[:7]
                if (frequency == 'QUARTERLY' and month in {3, 6, 9, 12}
                        and last_rebalanced != period and day != start):
                    actual = {sid: quantity * indexes[sid][day]
                              for sid, quantity in holdings.items()}
                    actual['CASH'] = cash
                    if max(abs(actual.get(sid, Decimal(0)) / value - weight)
                           for sid, weight in weights.items()) > trigger:
                        changes = {sid: value * weights[sid] - actual[sid] for sid in holdings}
                        trades = sum(change != 0 for change in changes.values())
                        rebalance_fees = fee * trades
                        if rebalance_fees >= value:
                            raise DomainError('Rebalance fees exhaust hypothetical capital')
                        turnover += sum((abs(change) for change in changes.values()), Decimal(0))
                        value -= rebalance_fees
                        cash = value * weights.get('CASH', Decimal(0))
                        holdings = {sid: value * weights[sid] / indexes[sid][day]
                                    for sid in holdings}
                        last_rebalanced = period
                period_return = (value - contribution) / previous - 1
                cumulative *= Fraction(value - contribution) / Fraction(previous)
                if day != start:
                    returns.append(float(period_return))
                peak = max(peak, cumulative)
                drawdown = min(drawdown, cumulative / peak - 1)
                curve.append({'date': day, 'value': _text(value),
                              'contribution': _text(contribution), 'linked_growth': _text(
                                  Decimal(cumulative.numerator) / Decimal(cumulative.denominator))})
                previous = value
            growth = Decimal(cumulative.numerator) / Decimal(cumulative.denominator)
            result.update(total_return=_text(growth - 1), final_value=_text(previous),
                          annualized_return=math.expm1(math.log(float(cumulative)) *
                                                     365.25 / (last - first).days),
                          volatility=statistics.stdev(returns) * math.sqrt(252) if len(returns) > 1 else None,
                          max_drawdown=_text(Decimal(drawdown.numerator) /
                                             Decimal(drawdown.denominator)),
                          turnover=_text(turnover / total),
                          final_allocation={sid: _text(quantity * indexes[sid][end] / previous)
                                            for sid, quantity in holdings.items()}, history=curve)
            result['final_allocation']['CASH'] = _text(cash / previous)
        with ledger.connection:
            ledger.connection.execute('INSERT INTO backtest_runs VALUES (?,?,?,?,?,?,?,?)',
                                      (result['id'], result['created_at'], start, end,
                                       result['status'], _hash(comparison), _json(result), _json(inputs)))
        return result


def compare(ledger, run_ids):
    """Compare persisted experiments only; mismatch never silently changes a window."""
    if len(run_ids) < 2:
        raise DomainError('Compare requires at least two saved backtests')
    results, hashes, issues = [], [], []
    for run_id in run_ids:
        row = ledger.connection.execute(
            'SELECT result_json,comparison_hash FROM backtest_runs WHERE id=?', (run_id,)).fetchone()
        if row is None:
            raise DomainError('Backtest does not exist')
        result = json.loads(row[0])
        results.append(result)
        hashes.append(row[1])
        issues.extend(result['issues'])
    if len(set(hashes)) > 1:
        issues.append(_issue('ASSUMPTION_MISMATCH', 'Pinned histories, periods or model assumptions differ'))
    return {'status': 'INCOMPARABLE' if issues else 'COMPARABLE', 'runs': results,
            'start': results[0]['start'], 'end': results[0]['end'],
            'assumptions': results[0]['assumptions'], 'issues': issues}
