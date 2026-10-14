"""Read accepted historical observations; never value history from today's quotes."""

from collections import defaultdict
from decimal import Decimal, localcontext

from invest.db import rows
from invest.ledger import _issue, source_time
from invest.models import decimal
from invest.performance import calculate


def _valuation(observation):
    values = [position.get('market_value') for position in observation['positions']]
    if observation.get('cash_known'):
        values.append(observation['cash'])
    complete = (observation.get('positions_complete') is True
                and observation.get('cash_known') is True
                and all(value is not None for value in values))
    amounts = [decimal(value) for value in values if value is not None]
    with localcontext() as context:
        context.prec = max(100, sum(len(number.as_tuple().digits) + abs(number.as_tuple().exponent)
                                   for number in amounts) + 64)
        return sum(amounts, Decimal(0)), complete


def _date_checkpoints(selected, identities, flows, currency):
    """Combine only compatible account observations at a common dated boundary."""
    checkpoints, issues = [], []
    for day, observed in sorted(selected.items()):
        same_day = [flow for flow in flows if flow['date'] == day]
        groups = defaultdict(dict)
        ambiguous_order = False
        for account, observations in observed.items():
            for observation in observations:
                timing = None
                if same_day:
                    source = observation['source_timestamp']
                    if len(source) == 10 or any(not flow.get('event_timestamp') or
                                               len(flow['event_timestamp']) == 10
                                               for flow in same_day):
                        ambiguous_order = True
                        continue
                    moment = source_time(source)
                    moments = [source_time(flow['event_timestamp']) for flow in same_day]
                    if moment < min(moments):
                        timing = 'BEFORE_FLOW'
                    elif moment > max(moments):
                        timing = 'AFTER_FLOW'
                    else:
                        ambiguous_order = True
                        continue
                groups[timing].setdefault(account, []).append(observation)

        if same_day and (ambiguous_order or not any(set(group) == identities
                                                    for group in groups.values())):
            issues.append(_issue('AMBIGUOUS_FLOW_BOUNDARY',
                f'Account observations cannot establish a common ordered flow boundary on {day}'))

        for timing, group in groups.items():
            # An account-only side of a flow is not a household boundary. A full
            # opposite side may still establish the household's ordered value.
            if same_day and set(group) != identities:
                continue
            values = []
            complete = set(group) == identities
            conflict = False
            for observations in group.values():
                valuations = [_valuation(observation) for observation in observations]
                if len({value for value, _ in valuations}) > 1:
                    conflict = True
                value, covered = valuations[-1]
                values.append(value)
                complete = complete and covered
            if conflict:
                issues.append(_issue('AMBIGUOUS_VALUATION_CHECKPOINT',
                    f'Conflicting same-date account valuations on {day}'))
                complete = False
            with localcontext() as context:
                context.prec = max(100, sum(len(value.as_tuple().digits) + abs(value.as_tuple().exponent)
                                           for value in values) + 64)
                checkpoint = {'date': day, 'value': str(sum(values, Decimal(0))),
                              'complete': complete, 'currency': currency}
            if timing:
                checkpoint['timing'] = timing
            checkpoints.append(checkpoint)
    return checkpoints, issues


def report(connection, *, from_date=None, to_date=None, as_of=None, account_id=None):
    end = to_date or as_of
    if from_date is None or end is None:
        return {'status': 'UNAVAILABLE', 'mode': 'ACTUAL', 'as_of': as_of or end,
                'twr': {'status': 'UNAVAILABLE', 'return': None},
                'xirr': {'status': 'UNAVAILABLE', 'annualized_return': None},
                'issues': [_issue('MISSING_PERFORMANCE_INTERVAL', 'Supply an explicit from/to interval and complete dated evidence')]}
    accounts = rows(connection, 'accounts')
    if account_id is not None:
        accounts = [row for row in accounts if row['id'] == account_id]
        if not accounts:
            from invest.models import DomainError

            raise DomainError('Performance account does not exist', 3)
    identities = {row['id'] for row in accounts}
    currencies = {row.get('currency') for row in accounts}
    activities = rows(connection, 'activities')
    selected = defaultdict(lambda: defaultdict(list))
    for observation in rows(connection, 'snapshots'):
        source = observation.get('source_timestamp')
        if observation['account']['id'] not in identities or not source or observation.get('status') == 'EVIDENCE_ONLY' or not from_date <= source[:10] <= end:
            continue
        selected[source[:10]][observation['account']['id']].append(observation)
    flows = []
    for activity in activities:
        if activity['account_id'] in identities and activity['type'] in {'CASH_DEPOSIT', 'CASH_WITHDRAWAL'}:
            amount = decimal(activity['amount'])
            if activity['type'] == 'CASH_WITHDRAWAL':
                amount = amount.copy_negate()
            flows.append({'id': activity['activity_id'], 'account_id': activity['account_id'],
                          'date': activity['date'], 'amount': str(amount),
                          'classification': activity.get('classification') or 'EXTERNAL',
                          'transfer_id': activity.get('transfer_id'),
                          'currency': activity.get('currency') or next((row.get('currency') for row in accounts if row['id'] == activity['account_id']), None),
                          'event_timestamp': activity.get('event_timestamp')})
    checkpoints, checkpoint_issues = _date_checkpoints(
        selected, identities, flows, next(iter(currencies)) if len(currencies) == 1 else None)
    environments = {row.get('data_environment') for row in accounts}
    payload = {'from_date': from_date, 'to_date': end, 'scope': 'ACCOUNT' if account_id else 'HOUSEHOLD',
               'data_environment': next(iter(environments)) if len(environments) == 1 else None,
               'cash_flow_history_complete': bool(accounts) and all(row.get('history_complete') is True for row in accounts),
               'checkpoints': checkpoints, 'cash_flows': flows}
    result = calculate(payload)
    if checkpoint_issues:
        result['issues'].extend(checkpoint_issues)
        result['twr'].update(status='UNAVAILABLE', **{'return': None})
        result['cagr'].update(status='UNAVAILABLE', annualized_return=None)
        # Dated investor flows and complete endpoints independently support
        # XIRR even when an intermediate intraday TWR boundary is ambiguous.
        if any(issue['code'] != 'AMBIGUOUS_FLOW_BOUNDARY' for issue in checkpoint_issues):
            result['xirr'].update(status='UNAVAILABLE', annualized_return=None, **{'return': None})
        result['status'] = 'PARTIAL' if result['xirr']['status'] == 'AVAILABLE' else 'UNAVAILABLE'
    result['as_of'] = as_of or end
    return result
