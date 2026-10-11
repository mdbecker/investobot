"""Read accepted historical observations; never value history from today's quotes."""

from collections import defaultdict
from datetime import datetime
from decimal import Decimal, localcontext

from invest.db import rows
from invest.ledger import _issue
from invest.models import decimal
from invest.performance import calculate


def report(connection, *, from_date=None, to_date=None, as_of=None):
    end = to_date or as_of
    if from_date is None or end is None:
        return {'status': 'UNAVAILABLE', 'mode': 'ACTUAL', 'as_of': as_of or end,
                'twr': {'status': 'UNAVAILABLE', 'return': None},
                'xirr': {'status': 'UNAVAILABLE', 'annualized_return': None},
                'issues': [_issue('MISSING_PERFORMANCE_INTERVAL', 'Supply an explicit from/to interval and complete dated evidence')]}
    accounts = rows(connection, 'accounts')
    activities = rows(connection, 'activities')
    checkpoints = []
    selected = defaultdict(dict)
    for observation in rows(connection, 'snapshots'):
        source = observation.get('source_timestamp')
        if not source or observation.get('status') == 'EVIDENCE_ONLY' or not from_date <= source[:10] <= end:
            continue
        selected[source][observation['account']['id']] = observation
    identities = {row['id'] for row in accounts}
    flows = []
    for activity in activities:
        if activity['type'] in {'CASH_DEPOSIT', 'CASH_WITHDRAWAL'}:
            amount = decimal(activity['amount'])
            if activity['type'] == 'CASH_WITHDRAWAL':
                amount = amount.copy_negate()
            flows.append({'id': activity['activity_id'], 'account_id': activity['account_id'],
                          'date': activity['date'], 'amount': str(amount),
                          'classification': 'EXTERNAL', 'event_timestamp': activity.get('event_timestamp')})
    for source, observed in sorted(selected.items()):
        complete = set(observed) == identities and all(
            row.get('positions_complete') is True and row.get('cash_known') is True for row in observed.values())
        amounts = [decimal(position['market_value']) for row in observed.values()
                   for position in row['positions']]
        amounts.extend(decimal(row['cash']) for row in observed.values() if row.get('cash_known'))
        with localcontext() as context:
            context.prec = max(100, sum(len(number.as_tuple().digits) + abs(number.as_tuple().exponent)
                                       for number in amounts) + 64)
            value = sum(amounts, Decimal(0))
        checkpoint = {'date': source[:10], 'value': str(value), 'complete': complete}
        same_day = [flow for flow in flows if flow['date'] == source[:10]]
        if same_day and len(source) > 10 and all(flow.get('event_timestamp') and len(flow['event_timestamp']) > 10 for flow in same_day):
            moment = datetime.fromisoformat(source.replace('Z', '+00:00'))
            moments = [datetime.fromisoformat(flow['event_timestamp'].replace('Z', '+00:00')) for flow in same_day]
            if moment < min(moments):
                checkpoint['timing'] = 'BEFORE_FLOW'
            elif moment > max(moments):
                checkpoint['timing'] = 'AFTER_FLOW'
        checkpoints.append(checkpoint)
    environments = {row.get('data_environment') for row in accounts}
    payload = {'from_date': from_date, 'to_date': end, 'scope': 'HOUSEHOLD',
               'data_environment': next(iter(environments)) if len(environments) == 1 else None,
               'cash_flow_history_complete': bool(accounts) and all(row.get('history_complete') is True for row in accounts),
               'checkpoints': checkpoints, 'cash_flows': flows}
    result = calculate(payload)
    result['as_of'] = as_of or end
    return result
