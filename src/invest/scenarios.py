"""Hypothetical actions use copied household state and a read-only provider cache."""

import copy
from contextlib import nullcontext
from decimal import Decimal

from invest.analytics import exposure
from invest.ledger import activity_change_inplace, household_currency, summarize
from invest.models import DomainError, decimal
from invest.tax import analyze

ZERO = Decimal("0")


class ReadonlyCache:
    def __init__(self, ledger):
        self.ledger = ledger
        self.connection = nullcontext()

    def rows(self, table):
        return self.ledger.rows(table)

    def put(self, table, key, data):
        pass


def readonly_client(client):
    cloned = copy.copy(client)
    cloned.ledger = ReadonlyCache(client.ledger)
    return cloned


def simulate(state, client, actions, rates=None):
    household_currency(state)
    if not isinstance(actions, list) or not actions:
        raise DomainError("Supply a nonempty array of hypothetical actions")
    before_state, working = copy.deepcopy(state), copy.deepcopy(state)
    client = readonly_client(client)
    planned = [dict(a, id=f"planned-{i}") for i, a in enumerate(actions) if a.get("type") == "BUY"]
    analyses, warnings = [], []
    for action in actions:
        kind = action.get("type")
        if kind == "MOVE_CASH":
            accounts = {a["id"]: a for a in working["accounts"]}
            a = accounts.get(action["account_id"])
            b = accounts.get(action["to_account"])
            if not a or not b or a["tax_status"] != b["tax_status"] or a["tax_status"] == "OTHER":
                raise DomainError("Cross-tax-treatment movements require manual contribution/rollover review", 3)
            if action.get("classification") != "CASH_TRANSFER":
                raise DomainError("Cash movement requires explicit CASH_TRANSFER classification", 3)
            amount = decimal(action["amount"])
            source = next(
                (c for c in working["cash_balances"] if c["account_id"] == action["account_id"]),
                None,
            )
            target = next(
                (c for c in working["cash_balances"] if c["account_id"] == action["to_account"]),
                None,
            )
            if source is None or target is None:
                raise DomainError("Cash transfer requires known source and destination accounts", 3)
            if source is target or amount <= 0:
                raise DomainError("Cash transfer requires distinct accounts and positive amount")
            if decimal(source["amount"]) < amount:
                raise DomainError("Insufficient cash for transfer", 3)
            source["amount"] = str(decimal(source["amount"]) - amount)
            target["amount"] = str(decimal(target["amount"]) + amount)
            continue
        if kind not in {"BUY", "SELL"}:
            raise DomainError("Scenario actions must be BUY, SELL or MOVE_CASH")
        analysis = None
        if kind == "SELL":
            # Future purchases supplied in the scenario are known hypothetical acquisitions.
            tax_state = dict(working, activities=working["activities"] + planned)
            qty = decimal(action["quantity"])
            fee = decimal(action.get("fee", "0"))
            price = decimal(action["price"])
            if qty <= 0 or fee < 0 or price * qty < fee:
                raise DomainError("Invalid sale quantity, price or fee")
            analysis = analyze(
                tax_state,
                action["account_id"],
                action["security"],
                str(qty),
                str(price),
                action["date"],
                method=action.get("method", "FIFO"),
                lot_ids=action.get("lot_ids"),
                rates=rates,
                fee=str(fee),
            )
            analyses.append(analysis)
            warnings.extend(analysis["warnings"])
        simulated_action = dict(action)
        if analysis and analysis["selected_lots"]:
            simulated_action["lot_allocations"] = [{"lot_id": l["id"], "quantity": l["quantity"]} for l in analysis["selected_lots"]]
        working, change = activity_change_inplace(working, simulated_action)
        # Hypothetical marks are explicit scenario assumptions, never ledger price updates.
        security = next(s for s in working["securities"] if action["security"] in {s["id"], s["ticker"]})
        position = next(p for p in working["positions"] if p["account_id"] == action["account_id"] and p["security_id"] == security["id"])
        position.update(price=str(action["price"]), market_value=str(decimal(position["quantity"]) * decimal(action["price"])), as_of=action["date"])
        working["activities"].append(dict(action, id=f"scenario-{len(working['activities'])}"))
    before_exposure = exposure(before_state, client)
    after_exposure = exposure(working, client)
    before_map = {r["identifier"]: r for r in before_exposure["exposures"]}
    after_map = {r["identifier"]: r for r in after_exposure["exposures"]}
    changes = []
    for identity in before_map.keys() | after_map.keys():
        b, a = before_map.get(identity, {}), after_map.get(identity, {})
        delta = decimal(a.get("total_value", "0")) - decimal(b.get("total_value", "0"))
        changes.append(
            {
                "identifier": identity,
                "ticker": a.get("ticker") or b.get("ticker"),
                "before": b.get("total_value", "0"),
                "after": a.get("total_value", "0"),
                "change": str(delta),
            }
        )
    changes.sort(key=lambda r: abs(decimal(r["change"])), reverse=True)
    unknown = any(a["realized_gain_loss"] is None for a in analyses)
    totals = {
        key: None if unknown else str(sum((decimal(a[key]) for a in analyses), ZERO))
        for key in ["realized_gain_loss", "short_term_gain_loss", "long_term_gain_loss"]
    }
    tax_effect = (
        None
        if not rates or unknown
        else str(sum((decimal(a["estimated_tax_effect"] or "0") for a in analyses), ZERO))
    )
    return dict(
        status="INSUFFICIENT_TAX_DATA" if unknown else "SIMULATED",
        hypothetical_state=working,
        before=summarize(before_state),
        after=summarize(working),
        before_exposure=before_exposure,
        after_exposure=after_exposure,
        exposure_changes=changes,
        tax_analyses=analyses,
        estimated_tax_effect=tax_effect,
        warnings=list(
            dict.fromkeys(warnings + before_exposure["warnings"] + after_exposure["warnings"])
        ),
        **totals,
    )
