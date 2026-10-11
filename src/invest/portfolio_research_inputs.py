"""Read existing public holdings observations against accepted security identities."""

from invest.lookthrough import research_universe
from invest.models import DomainError


def universe(ledger, *, as_of, top=20, min_exposure='0.01'):
    state = ledger.planning_state()
    securities = state['securities']
    observations = {}
    environments = {account.get('data_environment') for account in state['accounts']}
    for security in securities:
        if security['asset_type'] not in {'ETF', 'MUTUAL_FUND'}:
            continue
        candidates = [entry for entry in ledger.rows('fund_holdings_cache')
                      if entry.get('ticker') == security['ticker']]
        if not candidates:
            continue
        entry = max(candidates, key=lambda row: row.get('retrieved_at', ''))
        environments.add(entry.get('data_environment'))
        holdings = []
        for holding in entry.get('holdings', []):
            ids = {key: holding[key] for key in ('cusip', 'isin', 'figi') if holding.get(key)}
            matched = [candidate for candidate in securities
                       if ids and any(candidate.get(key) == value for key, value in ids.items())
                       and not any(candidate.get(key) and candidate[key] != value for key, value in ids.items())]
            if len(matched) != 1 or holding.get('weight') is None:
                continue
            holdings.append({'security_id': matched[0]['id'], 'weight': holding['weight']})
        observations[security['id']] = {'as_of': entry.get('data_as_of'),
            'source_id': entry['id'], 'data_environment': entry.get('data_environment'),
            'holdings': holdings}
    if len(environments) != 1 or next(iter(environments), None) not in {'REAL', 'SYNTHETIC'}:
        raise DomainError('Research universe requires one explicit source environment', 3)
    result = research_universe(state, observations, as_of=as_of, top=top, min_exposure=min_exposure)
    result['data_environment'] = next(iter(environments))
    result['household_total_value'] = result['total_value']
    for company in result['companies']:
        security = next(row for row in securities if row['id'] == company['security_id'])
        company['identity'] = {key: security.get(key) for key in ('cik', 'lei', 'ticker', 'name')}
        company['identity']['security_id'] = security['id']
        company['issuer_identity_evidence'] = security.get('issuer_identity_evidence')
    return result
