"""Known fixed-rate bond calculations using QuantLib and disclosed conventions."""

import math
from datetime import date
from decimal import Decimal, InvalidOperation

import QuantLib as ql

from invest.models import DomainError

REQUIRED = (
    "face_value",
    "coupon",
    "maturity",
    "issue_date",
    "settlement_date",
    "frequency",
    "clean_price",
)
FREQUENCIES = {1: ql.Annual, 2: ql.Semiannual, 4: ql.Quarterly, 12: ql.Monthly}


def number(value, name, positive=False):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError):
        raise DomainError(f"{name} must be a finite number") from None
    if not result.is_finite() or result < 0 or (positive and result == 0):
        raise DomainError(f"{name} must be finite and {'positive' if positive else 'nonnegative'}")
    converted = float(result)
    if not math.isfinite(converted):
        raise DomainError(f"{name} is outside calculation range")
    return converted


def qdate(value):
    try:
        parsed = date.fromisoformat(value)
        return ql.Date(parsed.day, parsed.month, parsed.year)
    except (ValueError, TypeError, RuntimeError):
        raise DomainError("Bond dates must be supported ISO YYYY-MM-DD dates") from None


def metric(value):
    if not math.isfinite(value):
        raise DomainError("Bond calculation did not produce a finite result", 3)
    return format(value, ".12g")


def analyze(terms):
    if not isinstance(terms, dict):
        raise DomainError("Bond terms must be a JSON object")
    missing = [key for key in REQUIRED if terms.get(key) is None]
    if missing:
        return {
            "status": "INSUFFICIENT_DATA",
            "warnings": ["Missing known bond terms: " + ", ".join(missing)],
        }
    face = number(terms["face_value"], "face_value", positive=True)
    coupon = number(terms["coupon"], "coupon")
    price = number(terms["clean_price"], "clean_price", positive=True)
    frequency = terms["frequency"]
    if type(frequency) is not int or frequency not in FREQUENCIES:
        raise DomainError("Frequency must be 1, 2, 4, or 12 coupon payments per year")
    issue, settlement, maturity = (
        qdate(terms[key]) for key in ("issue_date", "settlement_date", "maturity")
    )
    if not issue <= settlement < maturity or issue == maturity:
        raise DomainError("Issue must be on or before settlement; maturity must follow settlement")
    day_count_name = terms.get("day_count", "ACTUAL_ACTUAL_BOND")
    day_counts = {
        "ACTUAL_ACTUAL_BOND": ql.ActualActual(ql.ActualActual.Bond),
        "THIRTY_360_BOND_BASIS": ql.Thirty360(ql.Thirty360.BondBasis),
        "ACTUAL_365_FIXED": ql.Actual365Fixed(),
    }
    if day_count_name not in day_counts:
        raise DomainError("Unsupported day_count convention")
    day_count = day_counts[day_count_name]
    warnings = [
        "Regular fixed-rate coupon schedule only; supplied issue/maturity dates define schedule."
    ]
    if "day_count" not in terms:
        warnings.append(
            "day_count defaulted explicitly to ACTUAL_ACTUAL_BOND; verify against bond terms"
        )
    conventions = {
        "day_count": day_count_name,
        "calendar": "NullCalendar",
        "business_day_adjustment": "Unadjusted",
        "schedule_generation": "Backward",
        "settlement_days": 0,
        "compounding": "Compounded",
        "frequency": frequency,
        "redemption": "100 per 100 face value",
        "clean_price_units": "per 100 face value",
        "accrued_interest_units": "currency for supplied face value",
        "dirty_price_units": "per 100 face value",
        "yield_units": "annual decimal fraction",
    }
    schedule = ql.Schedule(
        issue,
        maturity,
        ql.Period(12 // frequency, ql.Months),
        ql.NullCalendar(),
        ql.Unadjusted,
        ql.Unadjusted,
        ql.DateGeneration.Backward,
        False,
    )
    try:
        bond = ql.FixedRateBond(0, face, schedule, [coupon], day_count, ql.Unadjusted, 100, issue)
        ytm = ql.BondFunctions.bondYield(
            bond,
            ql.BondPrice(price, ql.BondPrice.Clean),
            day_count,
            ql.Compounded,
            FREQUENCIES[frequency],
            settlement,
        )
        accrued_per100 = bond.accruedAmount(settlement)
        result = {
            "status": "CALCULATED",
            "yield_to_maturity": metric(ytm),
            "accrued_interest": metric(accrued_per100 * face / 100),
            "accrued_interest_per_100": metric(accrued_per100),
            "dirty_price": metric(price + accrued_per100),
            "dirty_value": metric((price + accrued_per100) * face / 100),
            "modified_duration": metric(
                ql.BondFunctions.duration(
                    bond,
                    ytm,
                    day_count,
                    ql.Compounded,
                    FREQUENCIES[frequency],
                    ql.Duration.Modified,
                    settlement,
                )
            ),
            "convexity": metric(
                ql.BondFunctions.convexity(
                    bond, ytm, day_count, ql.Compounded, FREQUENCIES[frequency], settlement
                )
            ),
            "settlement_date": terms["settlement_date"],
            "conventions": conventions,
            "warnings": warnings,
            "call_yields": [],
        }
        calls = terms.get("call_schedule")
        if calls is None:
            warnings.append("Call schedule unavailable; yield to worst is not calculable")
        elif not isinstance(calls, list):
            raise DomainError("call_schedule must be a list of date/price objects")
        else:
            yields = [ytm]
            complete = True
            for call in calls:
                if not isinstance(call, dict) or "date" not in call or "price" not in call:
                    raise DomainError("Each call must supply date and redemption price per 100")
                call_date = qdate(call["date"])
                call_price = number(call["price"], "call price", positive=True)
                if not settlement < call_date <= maturity:
                    raise DomainError(
                        "Call dates must be after settlement and no later than maturity"
                    )
                if call_date not in list(schedule):
                    complete = False
                    warnings.append(
                        "Off-coupon call date requires explicit stub/accrued redemption terms; yield to worst unavailable"
                    )
                    continue
                call_schedule = ql.Schedule(
                    [d for d in schedule if d <= call_date],
                    ql.NullCalendar(),
                    ql.Unadjusted,
                    ql.Unadjusted,
                    ql.Period(12 // frequency, ql.Months),
                    ql.DateGeneration.Backward,
                    False,
                )
                called = ql.FixedRateBond(
                    0, face, call_schedule, [coupon], day_count, ql.Unadjusted, call_price, issue
                )
                call_yield = ql.BondFunctions.bondYield(
                    called,
                    ql.BondPrice(price, ql.BondPrice.Clean),
                    day_count,
                    ql.Compounded,
                    FREQUENCIES[frequency],
                    settlement,
                )
                yields.append(call_yield)
                result["call_yields"].append(
                    {
                        "date": call["date"],
                        "redemption_price": metric(call_price),
                        "yield": metric(call_yield),
                    }
                )
            if complete:
                result["yield_to_worst"] = metric(min(yields))
                warnings.append(
                    "Yield to worst covers only maturity and the supplied call schedule; verify schedule completeness"
                )
        return result
    except RuntimeError:
        raise DomainError(
            "QuantLib could not calculate these terms; verify coupon schedule, price and dates", 3
        ) from None
