"""Read-only independent coverage preflight; readiness never grants trading permission."""

from datetime import date

from invest.ledger import _issue


def _freshness(timestamp, today):
    if timestamp is None:
        return {'source_timestamp': None, 'status': 'UNKNOWN', 'age_days': None}
    observed = date.fromisoformat(timestamp[:10])
    return {'source_timestamp': timestamp, 'status': 'FUTURE' if observed > today else 'DATED',
            'age_days': (today - observed).days}


def check(state, *, as_of):
    today = date.fromisoformat(as_of)
    issues, actions, coverage = [], [], []

    def add(code, message, *, calculation=True, **fields):
        issue = _issue(code, message, **fields)
        issue['blocks_calculation'] = calculation
        issues.append(issue)
        actions.append({'action': message, **fields})

    snapshots = [s for s in state.get('snapshots', []) if s.get('status') != 'EVIDENCE_ONLY']
    environments = set()
    for account in state.get('accounts', []):
        identity = account['id']
        observations = [s for s in snapshots if s.get('account', {}).get('id') == identity]
        latest = max(observations, key=lambda s: (s.get('imported_at', ''), s.get('id', '')), default={})
        cash = next((r for r in state.get('cash_balances', []) if r['account_id'] == identity), None)
        positions = [r for r in state.get('positions', []) if r['account_id'] == identity]
        source = latest.get('source_timestamp')
        domains = {
            'positions': {'coverage': 'COMPLETE' if latest.get('positions_complete') is True else
                          'PARTIAL' if latest.get('positions_complete') is False else 'UNKNOWN',
                          'freshness': _freshness(source, today)},
            'lots': {'coverage': 'COMPLETE' if latest.get('lots_complete') is True else
                     'PARTIAL' if latest.get('lots_complete') is False else 'UNKNOWN',
                     'freshness': _freshness(source, today)},
            'cash': {'coverage': 'COMPLETE' if cash is not None else 'UNKNOWN',
                     'freshness': _freshness(cash.get('as_of') if cash else None, today)},
        }
        coverage.append({'account_id': identity, 'domains': domains,
                         'source_hash': latest.get('source_hash'), 'imported_at': latest.get('imported_at')})
        if domains['positions']['coverage'] != 'COMPLETE':
            add('INCOMPLETE_POSITION_COVERAGE', 'Review an explicitly positions-complete account observation', account_id=identity)
        if domains['lots']['coverage'] != 'COMPLETE':
            add('UNKNOWN_LOT_COVERAGE', 'Review complete stable lot identity and adjusted basis',
                calculation=False, account_id=identity)
        for domain, codes in (
            ('positions', ('UNKNOWN_POSITION_FRESHNESS', 'FUTURE_POSITION_OBSERVATION')),
            ('cash', ('UNKNOWN_CASH_FRESHNESS', 'FUTURE_CASH_OBSERVATION')),
        ):
            freshness = domains[domain]['freshness']['status']
            if freshness in {'UNKNOWN', 'FUTURE'}:
                add(codes[freshness == 'FUTURE'], 'Verify independent ' + domain + ' source chronology', account_id=identity)
        if cash is None:
            add('UNKNOWN_CASH_COVERAGE', 'Import and review an explicitly cash-complete account observation', account_id=identity)
        environment = account.get('data_environment')
        environments.add(environment)
        if latest:
            environments.add(latest.get('data_environment'))
        if environment not in {'REAL', 'SYNTHETIC'} or (latest and latest.get('data_environment') not in {'REAL', 'SYNTHETIC'}):
            add('UNKNOWN_DATA_ENVIRONMENT', 'Verify account observation provenance', account_id=identity)
        if account.get('history_complete') is not True:
            add('INCOMPLETE_ACTIVITY_HISTORY', 'Verify dated account history coverage', calculation=False, account_id=identity)
        for row in positions:
            sid = row['security_id']
            if row.get('market_value') is None or row.get('valuation_state') == 'UNRESOLVED':
                add('MISSING_VALUATION_MARK', 'Confirm an independent portfolio valuation mark', security_id=sid)
            freshness = _freshness(row.get('source_timestamp'), today)['status']
            if freshness == 'UNKNOWN':
                add('UNKNOWN_POSITION_FRESHNESS', 'Import time does not establish quantity freshness', security_id=sid)
            elif freshness == 'FUTURE':
                add('FUTURE_POSITION_OBSERVATION', 'Observation follows the requested date', security_id=sid)
            if row.get('lot_state') != 'RESOLVED':
                add('UNKNOWN_LOT_COVERAGE', 'Review complete stable lot identity and adjusted basis', calculation=False, security_id=sid)
    if {'REAL', 'SYNTHETIC'} <= environments:
        add('MIXED_DATA_ENVIRONMENT', 'Mixed evidence cannot authorize proposals', calculation=False)
    if not state.get('accounts'):
        add('NO_ACCEPTED_ACCOUNTS', 'Import and explicitly accept reviewed account evidence')
    return {'status': 'REVIEW_REQUIRED' if issues else 'AVAILABLE', 'as_of': today.isoformat(),
            'issues': issues, 'next_human_actions': actions, 'coverage': coverage,
            'calculation_allowed': not any(i['blocks_calculation'] for i in issues),
            'proposals_allowed': False, 'execution_review_allowed': False,
            'policy_review': 'Separate approved trading and tax policies remain required',
            'freshness_policy': 'DATED reports age only; approved policy limits determine proposal freshness'}
