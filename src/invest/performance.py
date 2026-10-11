"""Actual performance from explicit complete checkpoints and external cash flows."""

import math
from collections import defaultdict
from datetime import date
from decimal import Decimal, localcontext
from fractions import Fraction

from scipy.optimize import brentq

from invest.models import DomainError, decimal


def _text(value):
    rendered = format(value, 'f')
    return rendered.rstrip('0').rstrip('.') if '.' in rendered else rendered


def _day(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        raise DomainError('Performance dates must be ISO dates') from None


def _roots(terms):
    """Isolate exponential-polynomial roots using its recursively reduced derivative."""
    merged = defaultdict(float)
    for exponent, coefficient in terms:
        merged[exponent] += coefficient
    terms = sorted((exponent, coefficient) for exponent, coefficient in merged.items()
                   if coefficient)
    if len(terms) < 2:
        return []
    origin = terms[0][0]
    terms = [(exponent - origin, coefficient) for exponent, coefficient in terms]

    def value(y):
        # A common positive scale preserves signs while avoiding exp overflow.
        powers = [-exponent * y for exponent, _ in terms]
        scale = max(powers)
        return math.fsum(coefficient * math.exp(power - scale)
                         for power, (_, coefficient) in zip(powers, terms, strict=True))

    stationary = _roots([(exponent, -exponent * coefficient)
                         for exponent, coefficient in terms if exponent])
    boundaries = [-700.0, *stationary, 700.0]
    roots = []
    magnitude = sum(abs(coefficient) for _, coefficient in terms)
    for y in stationary:
        if abs(value(y)) <= magnitude * 1e-12:
            roots.append(y)
    for left, right in zip(boundaries, boundaries[1:]):
        a, b = value(left), value(right)
        if a * b < 0:
            roots.append(brentq(value, left, right, xtol=1e-12))
    distinct = []
    for root in sorted(roots):
        if not distinct or abs(root - distinct[-1]) > 1e-8:
            distinct.append(root)
    return distinct


def calculate(payload):
    """Preserve supplied Decimal precision for all financial additions and ratios."""
    numbers = [decimal(row[key]) for group in ('checkpoints', 'cash_flows', 'investor_cash_flows')
               for row in payload.get(group, []) for key in ('value', 'amount') if key in row]
    with localcontext() as context:
        context.prec = max(80, sum(len(number.as_tuple().digits) + abs(number.as_tuple().exponent)
                                   for number in numbers) + 32)
        return _calculate(payload)


def _calculate(payload):
    """Pure calculation; unknown chronology or coverage never becomes complete."""
    first, last = _day(payload['from_date']), _day(payload['to_date'])
    if first >= last:
        raise DomainError('Actual performance requires a positive duration')
    scope = payload.get('scope', 'HOUSEHOLD')
    if scope not in {'HOUSEHOLD', 'ACCOUNT'}:
        raise DomainError('Performance scope must be HOUSEHOLD or ACCOUNT')
    checkpoints = payload.get('checkpoints', [])
    flows = payload.get('cash_flows', [])
    issues = []

    def issue(code, message):
        issues.append({'code': code, 'message': message, 'blocks_calculation': True,
                       'blocks_proposals': True, 'blocks_execution_review': True})

    currencies = {row.get('currency', payload.get('currency', 'USD'))
                  for row in checkpoints + flows}
    if len(currencies) > 1 or None in currencies:
        issue('UNSUPPORTED_CURRENCY', 'Actual performance requires one verified currency')
    if payload.get('cash_flow_history_complete') is not True:
        issue('INCOMPLETE_CASH_FLOW_HISTORY', 'External cash-flow history is incomplete')
    if payload.get('data_environment') not in {'REAL', 'SYNTHETIC'}:
        issue('UNKNOWN_DATA_ENVIRONMENT', 'Actual observations need explicit provenance')
    if any(row.get('data_environment', payload.get('data_environment')) !=
           payload.get('data_environment') for row in checkpoints + flows):
        issue('MIXED_DATA_ENVIRONMENT', 'Actual observations have mixed provenance')
    marks = defaultdict(list)
    for checkpoint in checkpoints:
        day = _day(checkpoint['date'])
        if first <= day <= last:
            if checkpoint.get('complete') is not True:
                issue('PARTIAL_VALUATION_CHECKPOINT', f'Incomplete valuation on {day}')
            value = decimal(checkpoint['value'])
            if value < 0:
                raise DomainError('Checkpoint values must be nonnegative')
            marks[day].append((checkpoint, value))
    for day, candidates in marks.items():
        if len(candidates) > 1 and not any(mark.get('timing') in {'BEFORE_FLOW', 'AFTER_FLOW'}
                                          for mark, _ in candidates):
            if len({value for _, value in candidates}) > 1:
                issue('AMBIGUOUS_VALUATION_CHECKPOINT', f'Conflicting undifferentiated marks on {day}')
    if first not in marks or last not in marks:
        issue('MISSING_VALUATION_CHECKPOINT', 'Requested endpoint checkpoint is missing')
    transfers = defaultdict(list)
    selected = []
    for flow in flows:
        day = _day(flow['date'])
        if not first <= day <= last:
            continue
        classification = flow.get('classification', 'EXTERNAL')
        if classification in {'REINVESTMENT', 'DIVIDEND', 'INTEREST', 'FEE', 'BUY', 'SELL'}:
            continue
        if scope == 'HOUSEHOLD' and classification == 'INTERNAL_TRANSFER':
            if not flow.get('transfer_id'):
                issue('UNPAIRED_INTERNAL_TRANSFER', 'Transfer link is unknown')
            else:
                transfers[flow['transfer_id']].append(flow)
            continue
        selected.append(flow)
    paired = True
    for transfer_id, legs in transfers.items():
        if (len(legs) != 2 or sum((decimal(leg['amount']) for leg in legs), Decimal(0)) != 0
                or len({leg.get('account_id') for leg in legs}) != 2
                or len({_day(leg['date']) for leg in legs}) != 1):
            paired = False
            issue('UNPAIRED_INTERNAL_TRANSFER', f'Incomplete linked transfer {transfer_id}')
    if any(item['code'] == 'UNPAIRED_INTERNAL_TRANSFER' for item in issues):
        paired = False
    flow_by_day = defaultdict(Decimal)
    for flow in selected:
        flow_by_day[_day(flow['date'])] += decimal(flow['amount'])
    missing = []
    boundaries = {}
    for day, amount in sorted(flow_by_day.items()):
        candidates = marks.get(day, [])
        before = [value for mark, value in candidates if mark.get('timing') == 'BEFORE_FLOW']
        after = [value for mark, value in candidates if mark.get('timing') == 'AFTER_FLOW']
        if not before and not after:
            missing.append(str(day))
            continue
        if len(before) > 1 or len(after) > 1:
            issue('AMBIGUOUS_FLOW_BOUNDARY', f'Multiple flow-boundary marks on {day}')
            continue
        pre = before[0] if before else after[0] - amount
        post = after[0] if after else before[0] + amount
        if pre < 0 or post < 0 or post - pre != amount:
            issue('INCONSISTENT_FLOW_BOUNDARY', f'Cash flow contradicts marks on {day}')
        else:
            boundaries[day] = (pre, post)
    if missing:
        issue('MISSING_FLOW_BOUNDARY_VALUATION', 'Missing ordered flow-boundary valuations')
    result = {'mode': 'ACTUAL', 'status': 'UNAVAILABLE' if issues else 'AVAILABLE',
              'from_date': str(first), 'to_date': str(last), 'scope': scope,
              'data_environment': payload.get('data_environment'), 'issues': issues,
              'fee_method': payload.get('fee_method', 'NET_OF_FEES'),
              'net_external_contributions': _text(sum(flow_by_day.values(), Decimal(0))),
              'coverage': {'paired_transfers_complete': paired,
                           'missing_boundary_dates': missing,
                           'cash_flow_history_complete': payload.get('cash_flow_history_complete') is True},
              'twr': {'status': 'UNAVAILABLE', 'return': None,
                      'method': 'LINKED_COMPLETE_FLOW_BOUNDARIES'},
              'xirr': {'status': 'UNAVAILABLE', 'annualized_return': None, 'return': None,
                       'method': 'MONEY_WEIGHTED_ACTUAL_DAYS_365_25',
                       'statistics_method': 'FLOAT64_ROOT_ISOLATION_LOG_RATE',
                       'log_rate_search_bounds': [-700, 700]},
              'cagr': {'status': 'UNAVAILABLE', 'annualized_return': None,
                       'calendar_days': (last - first).days, 'year_days': '365.25'}}
    common_blockers = [item for item in issues if item['code'] not in {
        'MISSING_FLOW_BOUNDARY_VALUATION', 'AMBIGUOUS_FLOW_BOUNDARY'}]
    if common_blockers:
        return result
    start_value = boundaries[first][0] if first in boundaries else marks[first][0][1]
    end_value = boundaries[last][1] if last in boundaries else marks[last][-1][1]
    if not issues:
        growth = Fraction(1)
        previous = start_value
        for day, (pre, post) in sorted(boundaries.items()):
            if day == first:
                previous = post
                continue
            if previous <= 0:
                issue('NONPOSITIVE_RETURN_BASELINE', 'TWR interval starts at zero')
                break
            growth *= Fraction(pre) / Fraction(previous)
            previous = post
        else:
            if previous > 0:
                growth *= Fraction(end_value) / Fraction(previous)
                with localcontext() as context:
                    context.prec = max(80, len(str(growth.numerator)) + len(str(growth.denominator)))
                    twr = Decimal(growth.numerator) / Decimal(growth.denominator) - 1
                result['twr'].update(status='AVAILABLE', return_value=_text(twr))
                result['twr']['return'] = result['twr'].pop('return_value')
                annualized = -1.0 if growth == 0 else math.expm1(
                    math.log(float(growth)) * 365.25 / (last - first).days)
                result['cagr'].update(status='AVAILABLE', annualized_return=annualized)
            else:
                issue('NONPOSITIVE_RETURN_BASELINE', 'TWR interval starts at zero')
    investor_flows = payload.get('investor_cash_flows')
    if investor_flows is None:
        investor_flows = [{'date': str(first), 'amount': -start_value},
                          *[{'date': flow['date'], 'amount': -decimal(flow['amount'])}
                            for flow in selected], {'date': str(last), 'amount': end_value}]
    scale = max((abs(decimal(row['amount'])) for row in investor_flows), default=Decimal(1))
    scale = scale or Decimal(1)
    amounts = [(float((_day(row['date']) - first).days) / 365.25,
                float(decimal(row['amount']) / scale)) for row in investor_flows]
    if len(amounts) > 128:
        issue('XIRR_UNAVAILABLE_COMPLEXITY', 'More than 128 investor flow records require review')
    else:
        roots = _roots(amounts)
        if len(roots) == 1:
            rate = math.expm1(roots[0])
            result['xirr'].update(status='AVAILABLE', annualized_return=rate, return_value=rate)
            result['xirr']['return'] = result['xirr'].pop('return_value')
        else:
            issue('MULTIPLE_XIRR_ROOTS' if len(roots) > 1 else 'NO_XIRR_ROOT',
                  'XIRR requires one independently supported root')
    result['status'] = 'PARTIAL' if issues else 'AVAILABLE'
    return result
