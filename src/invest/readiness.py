"""Read-only completeness preflight; observations and quotes never imply permission to trade."""

from datetime import date

from invest.ledger import _issue


def check(state, *, as_of):
    today = date.fromisoformat(as_of)
    issues, actions = [], []
    for account in state.get('accounts', []):
        identity = account['id']
        cash = next((row for row in state.get('cash_balances', []) if row['account_id'] == identity), None)
        if cash is None:
            issues.append(_issue('UNKNOWN_CASH_COVERAGE', 'Confirm same-account cash coverage', account_id=identity))
            actions.append({'account_id': identity, 'action': 'Import and review an explicitly cash-complete account observation'})
        if account.get('data_environment') not in {'REAL', 'SYNTHETIC'}:
            issues.append(_issue('UNKNOWN_DATA_ENVIRONMENT', 'Verify account observation provenance', account_id=identity))
        if account.get('history_complete') is not True:
            issues.append(_issue('INCOMPLETE_ACTIVITY_HISTORY', 'Verify dated account history coverage', account_id=identity))
        for row in state.get('positions', []):
            if row['account_id'] != identity:
                continue
            if row.get('market_value') is None or row.get('valuation_state') == 'UNRESOLVED':
                issues.append(_issue('MISSING_VALUATION_MARK', 'Confirm an independent portfolio valuation mark', security_id=row['security_id']))
            timestamp = row.get('source_timestamp')
            if timestamp is None:
                issues.append(_issue('UNKNOWN_POSITION_FRESHNESS', 'Import time does not establish quantity freshness', security_id=row['security_id']))
            elif date.fromisoformat(timestamp[:10]) > today:
                issues.append(_issue('FUTURE_POSITION_OBSERVATION', 'Observation follows the requested date', security_id=row['security_id']))
            if row.get('lot_state') != 'RESOLVED':
                issues.append(_issue('UNKNOWN_LOT_COVERAGE', 'Review complete stable lot identity and adjusted basis', security_id=row['security_id']))
    environments = {row.get('data_environment') for row in state.get('accounts', [])}
    if len(environments - {None}) > 1:
        issues.append(_issue('MIXED_DATA_ENVIRONMENT', 'Mixed evidence cannot authorize proposals'))
    if not state.get('accounts'):
        issues.append(_issue('NO_ACCEPTED_ACCOUNTS', 'Import and explicitly accept reviewed account evidence'))
    if issues and not actions:
        actions.append({'action': 'Review the original evidence for each reported coverage issue'})
    return {'status': 'REVIEW_REQUIRED' if issues else 'AVAILABLE', 'as_of': today.isoformat(),
            'issues': issues, 'next_human_actions': actions,
            'calculation_allowed': not issues, 'proposals_allowed': False,
            'execution_review_allowed': False,
            'policy_review': 'Separate approved trading and tax policies remain required'}
