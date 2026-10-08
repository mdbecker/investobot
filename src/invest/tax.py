"""Read-only Decimal lot analysis using known ledger state and explicit assumptions."""

from datetime import date, timedelta
from decimal import Decimal

from invest.models import DomainError, decimal

ZERO = Decimal(0)


def _date(value):
    try:
        return value if isinstance(value, date) else date.fromisoformat(str(value))
    except ValueError as error:
        raise DomainError("Dates must use YYYY-MM-DD") from error


def _term(acquired, sold):
    acquired, sold = _date(acquired), _date(sold)
    # Leap-day anniversaries fall on February 28 in a non-leap year.
    try:
        anniversary = acquired.replace(year=acquired.year + 1)
    except ValueError:
        anniversary = acquired.replace(year=acquired.year + 1, day=28)
    return "LONG_TERM" if sold > anniversary else "SHORT_TERM"


def _number(value):
    return format(value.normalize(), "f") if value else "0"


def _security(state, alias):
    matches = [
        s
        for s in state["securities"]
        if alias in {s["id"], s.get("ticker"), s.get("cusip"), s.get("isin"), s.get("figi")}
    ]
    if len(matches) != 1:
        raise DomainError("Security is unknown or ambiguous", 3)
    return matches[0]


def _matches(item, security):
    if item.get("security_id"):
        return item["security_id"] == security["id"]
    return item.get("security") in {security["id"], security.get("ticker")}


def _rate_config(rates):
    if not rates:
        return None
    required = {"ordinary_income_rate", "long_term_capital_gains_rate"}
    if not required <= rates.keys():
        raise DomainError("Tax estimates require ordinary-income and long-term capital-gains rates")
    values = {
        key: decimal(rates.get(key, "0"))
        for key in required | {"niit_rate", "state_capital_gains_rate"}
    }
    if any(value < 0 or value > 1 for value in values.values()):
        raise DomainError("Tax rates must be decimal fractions between zero and one")
    return values


def _rate(term, rates):
    return (
        rates["long_term_capital_gains_rate" if term == "LONG_TERM" else "ordinary_income_rate"]
        + rates["niit_rate"]
        + rates["state_capital_gains_rate"]
    )


def lots(state, as_of):
    as_of = _date(as_of)
    taxable = {a["id"] for a in state["accounts"] if a["tax_status"] == "TAXABLE"}
    results, warnings = [], []
    for lot in state["lots"]:
        if lot["account_id"] not in taxable or decimal(lot["remaining_quantity"]) <= 0:
            continue
        result = dict(lot)
        result["term"] = _term(lot["acquisition_date"], as_of)
        result["cost_basis"] = None
        result["current_value"] = None
        result["unrealized_gain_loss"] = None
        result["warnings"] = []
        position = next(
            (
                p
                for p in state["positions"]
                if p["account_id"] == lot["account_id"]
                and p.get("security_id") == lot.get("security_id")
            ),
            None,
        )
        if _date(lot["acquisition_date"]) > as_of:
            result["warnings"].append("Lot acquired after analysis date")
        elif lot.get("cost_basis") is None or decimal(lot["quantity"]) <= 0:
            result["warnings"].append("Lot basis unavailable")
        else:
            basis = (
                decimal(lot["cost_basis"])
                * decimal(lot["remaining_quantity"])
                / decimal(lot["quantity"])
            )
            result["cost_basis"] = _number(basis)
            if position and position.get("price") is not None:
                value = decimal(position["price"]) * decimal(lot["remaining_quantity"])
                result["current_value"] = _number(value)
                result["unrealized_gain_loss"] = _number(value - basis)
                result["price_as_of"] = position.get("as_of")
            else:
                result["warnings"].append("Current ledger price unavailable")
        result["status"] = "INSUFFICIENT_DATA" if result["warnings"] else "OK"
        warnings.extend(f"{lot['id']}: {warning}" for warning in result["warnings"])
        results.append(result)
    for position in state["positions"]:
        if position["account_id"] in taxable and decimal(position["quantity"]) > 0:
            represented = sum(
                (
                    decimal(l["remaining_quantity"])
                    for l in state["lots"]
                    if l["account_id"] == position["account_id"]
                    and l.get("security_id") == position.get("security_id")
                ),
                ZERO,
            )
            if represented != decimal(position["quantity"]):
                warnings.append(
                    f"{position['security']}: lot quantities do not cover the known position"
                )
    return {"lots": results, "warnings": warnings, "as_of": as_of.isoformat()}


def _wash(state, security, sale_date, loss, excluded_lots, retained_quantities=None):
    begin, end = sale_date - timedelta(days=30), sale_date + timedelta(days=30)
    conflicts, warnings = [], []
    complete = all(
        a.get("history_complete", False)
        for a in state["accounts"]
        if a.get("account_type") not in {"bank", "cash"}
    )
    if not complete:
        warnings.append("Household purchase history is incomplete")
    if loss:
        acquisitions = []
        for activity in state["activities"]:
            if activity.get("type") == "BUY" and _matches(activity, security):
                acquisitions.append(dict(activity, source="activity"))
        for lot in state["lots"]:
            if lot["id"] not in excluded_lots and _matches(lot, security):
                acquired = dict(lot, date=lot["acquisition_date"], source="lot")
                # A dated lot and its recorded purchase are one known acquisition.
                matched = next(
                    (
                        a
                        for a in acquisitions
                        if a["account_id"] == acquired["account_id"]
                        and a.get("date") == acquired["date"]
                        and decimal(a.get("quantity", 0)) == decimal(acquired.get("quantity", 0))
                    ),
                    None,
                )
                if retained_quantities and lot["id"] in retained_quantities:
                    acquired["quantity"] = _number(retained_quantities[lot["id"]])
                    if matched is not None:
                        matched["quantity"] = acquired["quantity"]
                if matched is None:
                    acquisitions.append(acquired)
        for acquired in acquisitions:
            if begin <= _date(acquired["date"]) <= end:
                conflicts.append(
                    {
                        "id": acquired.get("id"),
                        "account_id": acquired["account_id"],
                        "date": acquired["date"],
                        "quantity": acquired.get("quantity"),
                        "source": acquired["source"],
                    }
                )
    status = (
        "POTENTIAL_CONFLICT"
        if conflicts
        else ("NO_KNOWN_CONFLICT" if complete or not loss else "INSUFFICIENT_DATA")
    )
    warnings.append(
        "Future acquisitions and unloaded household or spouse accounts may change wash-sale treatment"
    )
    return {
        "status": status,
        "conflicts": conflicts,
        "affected_accounts": sorted({c["account_id"] for c in conflicts}),
        "window_start": begin.isoformat(),
        "window_end": end.isoformat(),
        "warnings": warnings,
    }


def analyze(
    state, account, security, quantity, price, sale_date, method="FIFO", lot_ids=None, rates=None
):
    """Analyze a proposed sale; quantity=None sells the selected specific lots in full."""
    account_row = next((a for a in state["accounts"] if account in {a["id"], a.get("name")}), None)
    if not account_row:
        raise DomainError("Account does not exist")
    security_row = _security(state, security)
    account_id, sale_date = account_row["id"], _date(sale_date)
    price, configured = decimal(price), _rate_config(rates)
    method = method.upper()
    if method not in {"FIFO", "LIFO", "HIFO", "SPECIFIC", "MIN_TAX"}:
        raise DomainError("Unsupported lot selection method")
    if price < 0:
        raise DomainError("Sale price must be nonnegative")
    if method == "MIN_TAX" and configured is None:
        raise DomainError("MIN_TAX requires configured tax rates")
    available = [
        dict(lot)
        for lot in state["lots"]
        if lot["account_id"] == account_id
        and _matches(lot, security_row)
        and decimal(lot["remaining_quantity"]) > 0
    ]
    if method == "SPECIFIC":
        if not lot_ids or len(set(lot_ids)) != len(lot_ids):
            raise DomainError("SPECIFIC requires unique ordered lot IDs")
        by_id = {lot["id"]: lot for lot in available}
        if any(lid not in by_id for lid in lot_ids):
            raise DomainError("Specific lot is unavailable for this account/security", 3)
        available = [by_id[lid] for lid in lot_ids]
    if quantity is None:
        if method != "SPECIFIC":
            raise DomainError("Quantity or specific lots are required")
        quantity = sum((decimal(l["remaining_quantity"]) for l in available), ZERO)
    quantity = decimal(quantity)
    if quantity <= 0:
        raise DomainError("Sale quantity must be positive")
    position = next(
        (
            p
            for p in state["positions"]
            if p["account_id"] == account_id and _matches(p, security_row)
        ),
        None,
    )
    if position is None or quantity > decimal(position["quantity"]):
        raise DomainError("Sale exceeds known position", 3)
    result = {
        "status": "OK",
        "account_id": account_id,
        "security_id": security_row["id"],
        "security": security_row.get("ticker"),
        "sale_date": sale_date.isoformat(),
        "quantity": _number(quantity),
        "price": _number(price),
        "method": method,
        "selected_lots": [],
        "realized_gain_loss": None,
        "short_term_gain_loss": None,
        "long_term_gain_loss": None,
        "estimated_tax_effect": None,
        "tax_estimate_status": "UNAVAILABLE" if configured else "NOT_CONFIGURED",
        "warnings": [],
    }
    if account_row["tax_status"] == "OTHER":
        result["status"] = "INSUFFICIENT_DATA"
        result["warnings"].append("Account tax status is unknown; no taxable gain is estimated")
        result["wash_sale"] = _wash(state, security_row, sale_date, True, set())
        return result
    if account_row["tax_status"] != "TAXABLE":
        result.update(
            realized_gain_loss="0",
            short_term_gain_loss="0",
            long_term_gain_loss="0",
            status="NOT_TAXABLE",
        )
        result["warnings"].append("Sale is in a non-taxable account; no taxable gain is estimated")
        result["wash_sale"] = _wash(state, security_row, sale_date, False, set())
        return result
    if sum((decimal(l["remaining_quantity"]) for l in available), ZERO) < quantity or any(
        l.get("cost_basis") is None
        or decimal(l["quantity"]) <= 0
        or _date(l["acquisition_date"]) > sale_date
        for l in available
    ):
        result["status"] = "INSUFFICIENT_DATA"
        result["warnings"].append(
            "Available lot quantities, acquisition dates or basis are insufficient"
        )
        result["wash_sale"] = _wash(state, security_row, sale_date, True, set())
        result["wash_sale"]["status"] = (
            "POTENTIAL_CONFLICT" if result["wash_sale"]["conflicts"] else "INSUFFICIENT_DATA"
        )
        return result
    for lot in available:
        lot["_basis"] = decimal(lot["cost_basis"]) / decimal(lot["quantity"])
        lot["_term"] = _term(lot["acquisition_date"], sale_date)
    if method in {"FIFO", "LIFO"}:
        available.sort(key=lambda l: (l["acquisition_date"], l["id"]), reverse=method == "LIFO")
    elif method == "HIFO":
        available.sort(key=lambda l: (-l["_basis"], l["acquisition_date"], l["id"]))
    elif method == "MIN_TAX":
        available.sort(
            key=lambda l: (
                (price - l["_basis"]) * _rate(l["_term"], configured),
                l["acquisition_date"],
                l["id"],
            )
        )
    remaining, st, lt, estimate, loss = quantity, ZERO, ZERO, ZERO, False
    excluded, retained = set(), {}
    for lot in available:
        if remaining <= 0:
            break
        used = min(remaining, decimal(lot["remaining_quantity"]))
        basis, proceeds = used * lot["_basis"], used * price
        gain = proceeds - basis
        result["selected_lots"].append(
            {
                "id": lot["id"],
                "acquisition_date": lot["acquisition_date"],
                "quantity": _number(used),
                "basis": _number(basis),
                "proceeds": _number(proceeds),
                "gain_loss": _number(gain),
                "term": lot["_term"],
            }
        )
        if lot["_term"] == "SHORT_TERM":
            st += gain
        else:
            lt += gain
        if configured:
            estimate += gain * _rate(lot["_term"], configured)
        loss |= gain < 0
        if used == decimal(lot["remaining_quantity"]):
            excluded.add(lot["id"])
        else:
            retained[lot["id"]] = decimal(lot["remaining_quantity"]) - used
        remaining -= used
    result.update(
        realized_gain_loss=_number(st + lt),
        short_term_gain_loss=_number(st),
        long_term_gain_loss=_number(lt),
        estimated_tax_effect=_number(estimate) if configured else None,
    )
    if not configured:
        result["warnings"].append("Tax rates absent; no dollar tax effect estimated")
    else:
        result["tax_estimate_status"] = "UNADJUSTED_POTENTIAL_EFFECT"
        result["warnings"].append(
            "Estimated tax effect excludes wash-sale adjustments; loss savings are not guaranteed"
        )
    result["wash_sale"] = _wash(state, security_row, sale_date, loss, excluded, retained)
    return result


def harvest_candidates(state, as_of):
    report = lots(state, as_of)
    candidates = []
    for lot in report["lots"]:
        if lot["unrealized_gain_loss"] is not None and decimal(lot["unrealized_gain_loss"]) < 0:
            candidate = dict(lot)
            security = _security(state, lot.get("security_id") or lot["security"])
            candidate["wash_sale"] = _wash(state, security, _date(as_of), True, {lot["id"]})
            candidates.append(candidate)
    candidates.sort(key=lambda l: (decimal(l["unrealized_gain_loss"]), l["id"]))
    return {"candidates": candidates, "warnings": report["warnings"], "as_of": report["as_of"]}
