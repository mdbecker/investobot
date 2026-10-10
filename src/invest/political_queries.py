"""Read immutable political evidence; descriptive totals never infer donor beliefs."""

import json
from decimal import Decimal, localcontext

from invest.models import DomainError

PARTIES = ('DEMOCRATIC', 'REPUBLICAN', 'OTHER', 'NONPARTISAN', 'UNKNOWN')
RECIPIENT_TYPES = ('CANDIDATE_COMMITTEE', 'PARTY_COMMITTEE', 'PAC',
                   'JOINT_FUNDRAISER', 'OTHER_COMMITTEE')


def list_runs(ledger, ticker=None):
    """Project compact metadata without loading any research evidence payload."""
    columns = ('research_run_id', 'company_name', 'ticker', 'security_id',
               'jurisdiction', 'period_start', 'period_end', 'researched_as_of',
               'imported_at', 'coverage_status', 'rights_status')
    query = '''SELECT id, company_name, ticker, security_id, jurisdiction,
        period_start, period_end, researched_as_of, imported_at,
        coverage_status, rights_status FROM research_political_runs'''
    params = ()
    if ticker is not None:
        query += ' WHERE UPPER(ticker) = UPPER(?)'
        params = (ticker,)
    query += ' ORDER BY imported_at DESC, id DESC'
    return {'runs': [dict(zip(columns, row, strict=True))
                     for row in ledger.connection.execute(query, params)]}


def show(ledger, run_id):
    row = ledger.connection.execute(
        'SELECT package_json, imported_at FROM research_political_runs WHERE id = ?',
        (run_id,),
    ).fetchone()
    if row is None:
        raise DomainError('Unknown political research run', 1)
    return {**json.loads(row[0]), 'research_run_id': run_id, 'imported_at': row[1]}


def _precision(amounts):
    # Align the largest integer part and smallest exponent, with enough carry
    # digits for every record. No rounding may erase a documented cent.
    if not amounts:
        return 28
    integer_digits = max(value.adjusted() + 1 for value in amounts)
    fractional_digits = max(0, -min(value.as_tuple().exponent for value in amounts))
    return max(28, integer_digits + fractional_digits + len(str(len(amounts))) + 2)


def summary(ledger, run_id):
    package = show(ledger, run_id)
    scope = package['scope']
    transactions = package['contributions']
    recipients = {row['id']: row for row in package['recipients']}
    counted = [row for row in transactions if row['countable']]
    amounts = [Decimal(row['amount_usd']) for row in counted]
    party_totals = dict.fromkeys(PARTIES, Decimal(0))
    type_totals = dict.fromkeys(RECIPIENT_TYPES, Decimal(0))
    with localcontext() as context:
        context.prec = _precision(amounts)
        for transaction, amount in zip(counted, amounts, strict=True):
            recipient = recipients[transaction['recipient_id']]
            party_totals[recipient['recipient_party']] += amount
            type_totals[recipient['recipient_type']] += amount
    warnings = list(package['limitations'])
    if scope['coverage_status'] != 'COMPLETE_WITHIN_DECLARED_SCOPE':
        warnings.append('This is a partial disclosure-based view, not a complete '
                        'record of political activity.')
    warnings.append('Absence of disclosed transactions does not establish absence '
                    'of contributions. Recipient party labels do not describe '
                    'executives\' political affiliations.')
    by_executive = [
        {'executive_id': executive['id'], 'full_name': executive['full_name'],
         'role': executive['role'],
         'transactions': [row for row in transactions
                          if row['executive_id'] == executive['id']]}
        for executive in package['executives']
    ]
    by_recipient = [
        {'recipient_id': recipient['id'], 'name': recipient['name'],
         'recipient_name': recipient['name'],
         'recipient_type': recipient['recipient_type'],
         'committee_id': recipient.get('committee_id'),
         'candidate_id': recipient.get('candidate_id'),
         'candidate_name': recipient.get('candidate_name'),
         'recipient_party': recipient['recipient_party'],
         'transactions': [row for row in transactions
                          if row['recipient_id'] == recipient['id']]}
        for recipient in package['recipients']
    ]
    return {
        'research_run_id': run_id, 'company': package['company']['name'],
        'period_start': scope['period_start'], 'period_end': scope['period_end'],
        'coverage_status': scope['coverage_status'], 'rights_status': scope['rights_status'],
        'executives_reviewed': len(package['executives']),
        'verified_transactions': len(transactions),
        'totals_by_recipient_party': {key: format(value, 'f')
                                      for key, value in party_totals.items()},
        'totals_by_recipient_type': {key: format(value, 'f')
                                     for key, value in type_totals.items()},
        'unresolved_match_count': len(package['unresolved_matches']),
        'warnings': warnings, 'contributions_by_executive': by_executive,
        'contributions_by_recipient': by_recipient, 'sources': package['sources'],
    }
