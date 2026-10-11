"""Exact copy-on-write activity accounting shared by acceptance and simulation."""

import copy
import uuid
from datetime import date
from decimal import Decimal, localcontext

from invest.issues import _issue
from invest.models import DomainError, decimal


def activity_change(state, activity):
    """Public copy-on-write accounting transform; failed changes cannot alter input."""
    return activity_change_inplace(copy.deepcopy(state), activity)


def activity_content(value):
    """Normalize monetary lexemes only; identity and source evidence stay literal."""
    from invest.db import DECIMAL_FIELDS, text_decimal

    def normalize(item):
        if isinstance(item, dict):
            return {key: text_decimal(child) if key in DECIMAL_FIELDS else normalize(child)
                    for key, child in item.items()}
        if isinstance(item, list):
            return [normalize(child) for child in item]
        return item

    result = normalize(value)
    result.setdefault('fee', '0')
    return result


def activity_change_inplace(state, activity):
    from invest.db import DECIMAL_FIELDS

    numbers = []

    def collect(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in DECIMAL_FIELDS and isinstance(child, (str, int, float, Decimal)) and not isinstance(child, bool):
                    numbers.append(decimal(child))
                elif isinstance(child, (dict, list)):
                    collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    collect(state)
    collect(activity)
    with localcontext() as context:
        context.prec = max(100, sum(len(number.as_tuple().digits) + abs(number.as_tuple().exponent)
                                   for number in numbers) + 64)
        return _activity_change_inplace(state, activity)


def _activity_change_inplace(state, activity):
    """Shared accounting for disposable working states; discard state on failure."""
    account_id, kind = activity["account_id"], activity["type"].upper()
    if kind in {'DIVIDEND_REINVESTMENT', 'STOCK_SPLIT', 'RETURN_OF_CAPITAL'}:
        from invest.corporate_actions import apply
        return apply(state, activity)
    account = next((a for a in state["accounts"] if a["id"] == account_id), None)
    if not account:
        raise DomainError("Account does not exist")
    date.fromisoformat(activity["date"])
    if kind not in {
        "BUY",
        "SELL",
        "TRANSFER_IN",
        "TRANSFER_OUT",
        "DIVIDEND",
        "INTEREST",
        "FEE",
        "CASH_DEPOSIT",
        "CASH_WITHDRAWAL",
    }:
        raise DomainError("Unsupported activity type")
    if kind in {"TRANSFER_IN", "TRANSFER_OUT"}:
        raise DomainError("Security transfers require explicit classification and manual review; unsupported in MVP")
    if activity.get("to_account") or activity.get("from_account"):
        raise DomainError("Cross-account movement requires explicit classification and manual review", 3)
    cash = next((c for c in state["cash_balances"] if c["account_id"] == account_id), None)
    if not cash:
        raise DomainError("Cash balance is unknown", 3)
    delta = Decimal("0")
    confirmed_allocations = []
    if kind in {"BUY", "SELL", "TRANSFER_IN", "TRANSFER_OUT"}:
        qty, price, fee = (
            decimal(activity["quantity"]),
            decimal(activity["price"]),
            decimal(activity.get("fee", 0)),
        )
        if qty <= 0 or price < 0 or fee < 0:
            raise DomainError("Quantity must be positive; price and fee nonnegative")
        from invest.security_identity import resolve

        security = resolve(state['securities'], activity['security'])
        p = next(
            (
                p
                for p in state["positions"]
                if p["account_id"] == account_id and p["security_id"] == security["id"]
            ),
            None,
        )
        if p is None:
            p = dict(
                id=f"{account_id}:{security['id']}",
                account_id=account_id,
                security_id=security["id"],
                security=security["ticker"],
                name=security["name"],
                asset_type=security["asset_type"],
                quantity="0",
                market_value="0",
                cost_basis=None,
                as_of=activity["date"],
                source_timestamp=None,
            )
            state["positions"].append(p)
        selling = kind in {"SELL", "TRANSFER_OUT"}
        if kind == "SELL" and fee > qty * price:
            raise DomainError("Sale fee exceeds gross proceeds")
        if selling and qty > decimal(p["quantity"]):
            raise DomainError("Sale/transfer exceeds known position", 3)
        old_qty = decimal(p["quantity"])
        market_price = decimal(p["price"]) if p.get("price") is not None else (
            decimal(p["market_value"]) / old_qty if old_qty else None)
        p["quantity"] = str(old_qty + (-qty if selling else qty))
        if market_price is not None:
            p["market_value"] = str(decimal(p["quantity"]) * market_price)
        else:
            p["market_value"] = None
            p["valuation_state"] = "UNRESOLVED"
        # Execution price belongs to the activity, not the remaining portfolio mark.
        if kind == "BUY":
            delta = -(qty * price + fee)
            if p.get("cost_basis") is not None:
                p["cost_basis"] = str(decimal(p["cost_basis"]) + qty * price + fee)
            lid = str(uuid.uuid4())
            state["lots"].append(
                dict(
                    id=lid,
                    account_id=account_id,
                    security_id=security["id"],
                    security=security["ticker"],
                    acquisition_date=activity["date"],
                    quantity=str(qty),
                    remaining_quantity=str(qty),
                    cost_basis=str(qty * price + fee),
                )
            )
        elif kind == "SELL":
            delta = qty * price - fee
        if selling:
            allocations = activity.get("lot_allocations")
            if allocations is None:
                p["lot_state"] = "UNRESOLVED"
                p["cost_basis"] = None
            else:
                if not isinstance(allocations, list) or not allocations:
                    raise DomainError("Supply nonempty executed lot allocations")
                if len({a["lot_id"] for a in allocations}) != len(allocations):
                    raise DomainError("Duplicate executed lot allocation")
                if sum((decimal(a["quantity"]) for a in allocations), Decimal("0")) != qty:
                    raise DomainError("Executed lot allocations must equal sold quantity", 3)
                basis_removed = Decimal("0")
                fee_remaining = fee
                for allocation in allocations:
                    lot = next((l for l in state["lots"] if l["id"] == allocation["lot_id"]
                        and l["account_id"] == account_id and l["security_id"] == security["id"]), None)
                    used = decimal(allocation["quantity"])
                    if lot is None or used <= 0 or used > decimal(lot["remaining_quantity"]):
                        raise DomainError("Executed lot allocation exceeds available lot shares", 3)
                    if lot.get('identity_status') == 'UNRESOLVED' or lot.get('saleable') is False:
                        raise DomainError('Executed lot needs verified saleable identity', 3)
                    if account.get('data_environment') == 'REAL' and (
                            lot.get('identity_status') != 'VERIFIED' or lot.get('saleable') is not True
                            or not lot.get('source_lot_id') or not lot.get('identity_source')):
                        error = DomainError('Real executed lot requires reviewed source identity and saleability', 3)
                        error.result = {'status': 'BLOCKED', 'issues': [_issue('UNVERIFIED_LOT_IDENTITY', str(error))]}
                        raise error
                    remaining = decimal(lot['remaining_quantity'])
                    available_basis = (decimal(lot['remaining_adjusted_basis'])
                                       if lot.get('remaining_adjusted_basis') is not None else
                                       decimal(lot['cost_basis']) * remaining / decimal(lot['quantity']))
                    removed = available_basis if used == remaining else available_basis * used / remaining
                    basis_removed += removed
                    lot['remaining_adjusted_basis'] = str(available_basis - removed)
                    lot["remaining_quantity"] = str(remaining - used)
                    acquired = date.fromisoformat(lot['acquisition_date'])
                    sold = date.fromisoformat(activity['date'])
                    anniversary = acquired.replace(year=acquired.year + 1, day=min(acquired.day, 28)) if acquired.month == 2 and acquired.day == 29 else acquired.replace(year=acquired.year + 1)
                    allocated_fee = fee_remaining if allocation is allocations[-1] else fee * used / qty
                    fee_remaining -= allocated_fee
                    confirmed_allocations.append(dict(lot_id=lot['id'], quantity=str(used),
                        basis_removed=str(removed), term='LONG_TERM' if sold > anniversary else 'SHORT_TERM',
                        realized_gain=str(used * price - allocated_fee - removed), fee_allocated=str(allocated_fee)))
                if p.get("cost_basis") is not None:
                    p["cost_basis"] = str(decimal(p["cost_basis"]) - basis_removed)
                represented = sum((decimal(l["remaining_quantity"]) for l in state["lots"]
                    if l["account_id"] == account_id and l["security_id"] == security["id"]), Decimal("0"))
                p["lot_state"] = "RESOLVED" if represented == decimal(p["quantity"]) else "UNRESOLVED"
    else:
        amount = decimal(activity["amount"])
        if amount <= 0:
            raise DomainError("Amount must be positive")
        delta = -amount if kind in {"FEE", "CASH_WITHDRAWAL"} else amount
    after_cash = decimal(cash["amount"]) + delta
    if after_cash < 0:
        raise DomainError("Insufficient cash", 3)
    cash["amount"] = str(after_cash)
    return state, {
        "cash_change": str(delta),
        "cash_after": str(after_cash),
        "warnings": ["Recorded activities do not establish complete household transaction history"],
        "_confirmed_allocations": confirmed_allocations if kind == 'SELL' and activity.get('lot_allocations') else None,
    }


