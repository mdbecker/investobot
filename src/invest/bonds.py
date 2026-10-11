"""Regular fixed-coupon cash flows with explicitly disclosed conventions."""

import calendar
import math
from datetime import date
from decimal import Decimal, InvalidOperation

from scipy.optimize import brentq

from invest.models import DomainError

REQUIRED = ('face_value', 'coupon', 'maturity', 'issue_date', 'settlement_date', 'frequency', 'clean_price')
FREQUENCIES = {1, 2, 4, 12}


def number(value, name, positive=False):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError):
        raise DomainError(f'{name} must be a finite number') from None
    if not result.is_finite() or result < 0 or (positive and result == 0):
        raise DomainError(f"{name} must be finite and {'positive' if positive else 'nonnegative'}")
    converted = float(result)
    if not math.isfinite(converted):
        raise DomainError(f'{name} is outside calculation range')
    return converted


def qdate(value):
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        raise DomainError('Bond dates must be supported ISO YYYY-MM-DD dates') from None


def metric(value):
    if not math.isfinite(value):
        raise DomainError('Bond calculation did not produce a finite result', 3)
    return format(value, '.12g')


def _shift(anchor, months):
    ordinal = anchor.year * 12 + anchor.month - 1 + months
    year, month = divmod(ordinal, 12)
    if not 1 <= year <= 9999:
        raise DomainError('Coupon schedule is outside supported date range')
    month += 1
    return date(year, month, min(anchor.day, calendar.monthrange(year, month)[1]))


def _fraction(start, end, convention, reference_start, reference_end, frequency):
    if convention == 'ACTUAL_365_FIXED':
        return (end - start).days / 365
    if convention == 'THIRTY_360_BOND_BASIS':
        first = min(start.day, 30)
        last = min(end.day, 30) if first == 30 else end.day
        return ((end.year - start.year) * 360 + (end.month - start.month) * 30 + last - first) / 360
    return (end - start).days / (reference_end - reference_start).days / frequency


def analyze(terms):
    if not isinstance(terms, dict):
        raise DomainError('Bond terms must be a JSON object')
    if terms.get('instrument_type', 'FIXED_RATE') not in {'FIXED_RATE', 'FIXED_COUPON', 'PLAIN_FIXED_RATE'}:
        return {'status': 'UNAVAILABLE', 'issues': [{
            'code': 'UNSUPPORTED_BOND_STRUCTURE',
            'message': 'Only regular plain fixed-coupon instruments are supported',
            'blocks_calculation': True, 'blocks_proposals': True, 'blocks_execution_review': True}],
            'warnings': ['Complex instrument terms require a separately verified pricing model']}
    missing = [key for key in REQUIRED if terms.get(key) is None]
    if missing:
        return {'status': 'INSUFFICIENT_DATA', 'warnings': ['Missing known bond terms: ' + ', '.join(missing)]}
    face = number(terms['face_value'], 'face_value', positive=True)
    coupon = number(terms['coupon'], 'coupon')
    price = number(terms['clean_price'], 'clean_price', positive=True)
    frequency = terms['frequency']
    if type(frequency) is not int or frequency not in FREQUENCIES:
        raise DomainError('Frequency must be 1, 2, 4, or 12 coupon payments per year')
    issue, settlement, maturity = (qdate(terms[key]) for key in ('issue_date', 'settlement_date', 'maturity'))
    if not issue <= settlement < maturity:
        raise DomainError('Issue must be on or before settlement; maturity must follow settlement')
    convention = terms.get('day_count', 'ACTUAL_ACTUAL_BOND')
    if convention not in {'ACTUAL_ACTUAL_BOND', 'THIRTY_360_BOND_BASIS', 'ACTUAL_365_FIXED'}:
        raise DomainError('Unsupported day_count convention')
    conventions = {
        'day_count': convention, 'calendar': 'NullCalendar', 'business_day_adjustment': 'Unadjusted',
        'schedule_generation': 'Backward', 'settlement_days': 0, 'compounding': 'Compounded',
        'frequency': frequency, 'redemption': '100 per 100 face value',
        'clean_price_units': 'per 100 face value', 'accrued_interest_units': 'currency for supplied face value',
        'dirty_price_units': 'per 100 face value', 'yield_units': 'annual decimal fraction',
    }
    warnings = ['Regular fixed-rate coupon schedule only; supplied issue/maturity dates define schedule.']
    if 'day_count' not in terms:
        warnings.append('day_count defaulted explicitly to ACTUAL_ACTUAL_BOND; verify against bond terms')
    schedule = [maturity]
    index = 1
    while schedule[-1] > issue:
        schedule.append(_shift(maturity, -index * (12 // frequency)))
        index += 1
    if schedule[-1] != issue:
        return {'status': 'INSUFFICIENT_DATA', 'warnings': [
            'Irregular coupon stub requires explicit schedule conventions; no metrics calculated'],
            'conventions': conventions}
    schedule.reverse()
    intervals = [(start, end) for start, end in zip(schedule, schedule[1:]) if end > settlement]
    previous, following = intervals[0]
    accrued = 100 * coupon * _fraction(previous, settlement, convention, previous, following, frequency)
    dirty = price + accrued

    def flows(until, redemption):
        elapsed = 0
        result = []
        for start, end in intervals:
            if end > until:
                break
            elapsed += _fraction(max(start, settlement), end, convention, start, end, frequency)
            amount = 100 * coupon * _fraction(start, end, convention, start, end, frequency)
            result.append((elapsed, amount + (redemption if end == until else 0)))
        return result

    def solve(cashflows):
        def present(yield_value):
            base = 1 + yield_value / frequency
            return sum(amount / base ** (frequency * elapsed) for elapsed, amount in cashflows)
        high = 1.0
        while present(high) > dirty and high < 1e12:
            high *= 2
        try:
            value = brentq(lambda y: present(y) - dirty, -frequency * .99, high, xtol=1e-13)
        except (ValueError, OverflowError, ZeroDivisionError):
            raise DomainError('Could not solve these fixed cash flows; verify schedule, price and dates', 3) from None
        return value

    cashflows = flows(maturity, 100)
    ytm = solve(cashflows)
    base = 1 + ytm / frequency
    present = sum(amount / base ** (frequency * elapsed) for elapsed, amount in cashflows)
    duration = sum(elapsed * amount / base ** (frequency * elapsed + 1)
                   for elapsed, amount in cashflows) / present
    convexity = sum(elapsed * (elapsed + 1 / frequency) * amount / base ** (frequency * elapsed + 2)
                    for elapsed, amount in cashflows) / present
    result = {'status': 'CALCULATED', 'yield_to_maturity': metric(ytm),
              'accrued_interest': metric(accrued * face / 100), 'accrued_interest_per_100': metric(accrued),
              'dirty_price': metric(dirty), 'dirty_value': metric(dirty * face / 100),
              'modified_duration': metric(duration), 'convexity': metric(convexity),
              'settlement_date': terms['settlement_date'], 'conventions': conventions,
              'warnings': warnings, 'call_yields': []}
    calls = terms.get('call_schedule')
    if calls is None:
        warnings.append('Call schedule unavailable; yield to worst is not calculable')
    elif not isinstance(calls, list):
        raise DomainError('call_schedule must be a list of date/price objects')
    else:
        yields, complete = [ytm], True
        for call in calls:
            if not isinstance(call, dict) or 'date' not in call or 'price' not in call:
                raise DomainError('Each call must supply date and redemption price per 100')
            call_date = qdate(call['date'])
            call_price = number(call['price'], 'call price', positive=True)
            if not settlement < call_date <= maturity:
                raise DomainError('Call dates must be after settlement and no later than maturity')
            if call_date not in schedule:
                complete = False
                warnings.append('Off-coupon call date requires explicit stub/accrued redemption terms; yield to worst unavailable')
                continue
            value = solve(flows(call_date, call_price))
            yields.append(value)
            result['call_yields'].append({'date': call['date'], 'redemption_price': metric(call_price), 'yield': metric(value)})
        if complete:
            result['yield_to_worst'] = metric(min(yields))
            warnings.append('Yield to worst covers only maturity and the supplied fixed-redemption scenarios; verify schedule completeness')
    return result
