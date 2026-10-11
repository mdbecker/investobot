"""Read existing public holdings observations against accepted security identities."""

import json

from invest.analytics_store import read_snapshot, select_vintage
from invest.lookthrough import research_universe
from invest.models import DomainError


def universe(ledger, *, as_of, top=20, min_exposure='0.01'):
    state = ledger.planning_state()
    securities = state['securities']
    observations = {}
    environments = {account.get('data_environment') for account in state['accounts']}
    pinned = {}
    for record in ledger.connection.execute('''SELECT DISTINCT d.manifest_json FROM data_snapshots d
            JOIN data_snapshot_artifacts l ON l.snapshot_id=d.id
            JOIN dataset_artifacts a ON a.id=l.artifact_id WHERE a.kind='FUND_HOLDINGS' '''):
        manifest = json.loads(record[0])
        for artifact in manifest['artifacts']:
            if artifact['kind'] == 'FUND_HOLDINGS':
                pinned[artifact['id']] = (dict(artifact, data_environment=artifact.get(
                    'data_environment') or manifest['data_environment']), manifest)
    for security in securities:
        if security['asset_type'] not in {'ETF', 'MUTUAL_FUND'}:
            continue
        vintages = [record[0] for record in pinned.values()
                    if record[0].get('security_id') == security['id']]
        if vintages:
            vintage = select_vintage(vintages, security_id=security['id'], as_of=as_of)
            if vintage['status'] not in {'AVAILABLE', 'REVIEW_REQUIRED'}:
                continue
            selected_manifest = dict(pinned[vintage['id']][1], artifacts=[pinned[vintage['id']][0]])
            selected_rows = read_snapshot(ledger, selected_manifest)
            if selected_rows['status'] != 'AVAILABLE':
                raise DomainError('Pinned holdings failed immutable artifact validation', 3)
            entry = dict(vintage, data_as_of=vintage['as_of'], holdings=selected_rows['rows'])
        else:
            candidates = [entry for entry in ledger.rows('fund_holdings_cache')
                          if entry.get('ticker') == security['ticker'] and
                          entry.get('retrieved_at', '')[:10] <= as_of and
                          (entry.get('published_at') or entry.get('retrieved_at', ''))[:10] <= as_of]
            if not candidates:
                continue
            entry = max(candidates, key=lambda row: row.get('retrieved_at', ''))
        environments.add(entry.get('data_environment'))
        holdings = []
        for holding in entry.get('holdings', []):
            ids = {key: holding[key] for key in ('cusip', 'isin', 'figi') if holding.get(key)}
            matched = [candidate for candidate in securities
                       if (candidate['id'] == holding.get('security_id') or
                           ids and any(candidate.get(key) == value for key, value in ids.items()))
                       and not any(candidate.get(key) and candidate[key] != value for key, value in ids.items())]
            if len(matched) != 1 or holding.get('weight') is None:
                continue
            holdings.append({'security_id': matched[0]['id'], 'weight': holding['weight']})
        observations[security['id']] = {'as_of': entry.get('data_as_of'),
            'source_id': entry['id'], 'data_environment': entry.get('data_environment'),
            'published_at': entry.get('published_at'), 'observed_at': entry.get('observed_at'),
            'source_hash': entry.get('sha256'),
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
