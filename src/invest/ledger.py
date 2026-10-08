"""Small explicit SQLite ledger; mutations are atomic and preserve normalized audit history."""

import copy
import hashlib
import json
import sqlite3
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from invest.models import DomainError, Snapshot, decimal

TABLES = [
    "accounts",
    "securities",
    "positions",
    "lots",
    "cash_balances",
    "activities",
    "snapshots",
    "market_data_cache",
    "fund_holdings_cache",
    "trade_proposals",
]


class Ledger:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.execute("PRAGMA foreign_keys=ON")
        version = self.connection.execute("PRAGMA user_version").fetchone()[0]
        if version > 1:
            raise DomainError("Database schema is newer than this application", 3)
        if version == 0:
            with self.connection:
                for table in TABLES:
                    self.connection.execute(
                        f"CREATE TABLE {table} (id TEXT PRIMARY KEY, data TEXT NOT NULL)"
                    )
                self.connection.execute("PRAGMA user_version=1")

    def rows(self, table):
        if table not in TABLES:
            raise ValueError("Unknown table")
        return [
            json.loads(r[0])
            for r in self.connection.execute(f"SELECT data FROM {table} ORDER BY id")
        ]

    def put(self, table, key, data):
        if table not in TABLES:
            raise ValueError("Unknown table")
        self.connection.execute(
            f"INSERT OR REPLACE INTO {table} VALUES (?, ?)", (key, json.dumps(data, default=str))
        )

    def state(self):
        return {
            table: self.rows(table)
            for table in [
                "accounts",
                "securities",
                "positions",
                "lots",
                "cash_balances",
                "activities",
                "snapshots",
            ]
        }

    def resolve(self, alias):
        matches = [
            s
            for s in self.rows("securities")
            if alias in {s["id"], s.get("ticker"), s.get("cusip"), s.get("isin"), s.get("figi")}
        ]
        if len(matches) != 1:
            raise DomainError("Security is unknown or ambiguous", 3)
        return matches[0]

    def reconcile(self, snapshot):
        snap = Snapshot.model_validate(snapshot).model_dump(mode="json")
        account_id = snap["account"]["id"]
        old = {p["security"]: p for p in self.rows("positions") if p["account_id"] == account_id}
        incoming = {p["security"]: p for p in snap["positions"]}
        changes, observations = [], []
        for symbol in sorted(old.keys() | incoming.keys()):
            if symbol not in incoming:
                entry = {"kind": "removed_position", "security": symbol,
                         "status": "CHANGED_VALUE" if snap["positions_complete"] else "UNKNOWN_VALUE"}
                (changes if snap["positions_complete"] else observations).append(entry)
            elif symbol not in old:
                changes.append({"kind": "new_position", "security": symbol, "status": "CHANGED_VALUE"})
            else:
                for field in ("quantity", "price", "market_value", "cost_basis"):
                    before, after = old[symbol].get(field), incoming[symbol].get(field)
                    status = "UNKNOWN_VALUE" if after is None else (
                        "CONFIRMED_VALUE" if before is not None and decimal(before) == decimal(after)
                        else "CHANGED_VALUE")
                    entry = dict(kind=field, security=symbol, before=before, after=after, status=status)
                    (changes if status == "CHANGED_VALUE" else observations).append(entry)
        account = next((a for a in self.rows("accounts") if a["id"] == account_id), None)
        if account and any(account.get(k) != snap["account"].get(k)
                           for k in ("tax_status", "account_type", "currency")):
            changes.append(dict(kind="account_classification", status="CHANGED_VALUE",
                                before=account, after=snap["account"]))
        current_cash = next((c for c in self.rows("cash_balances") if c["account_id"] == account_id), None)
        if snap["cash_known"] and (not current_cash or decimal(current_cash["amount"]) != decimal(snap["cash"])):
            changes.append(dict(kind="cash", status="CHANGED_VALUE",
                                before=current_cash["amount"] if current_cash else None, after=snap["cash"]))
        elif not snap["cash_known"]:
            observations.append(dict(kind="cash", status="UNKNOWN_VALUE"))
        old_lots = [{k: v for k, v in lot.items() if k not in {"account_id", "security_id"}}
                    for lot in self.rows("lots") if lot["account_id"] == account_id]
        if snap["lots"] and sorted(old_lots, key=lambda l: l["id"]) != sorted(snap["lots"], key=lambda l: l["id"]):
            changes.append(dict(kind="lots", status="CHANGED_VALUE"))
        elif snap["lots_complete"] and old_lots != snap["lots"]:
            changes.append(dict(kind="lots", status="CHANGED_VALUE"))
        elif not snap["lots_complete"]:
            observations.append(dict(kind="lots", status="UNKNOWN_VALUE"))
        dated = [s["source_timestamp"] for s in self.rows("snapshots")
                 if s["account"]["id"] == account_id and s.get("source_timestamp")]
        if dated and snap["source_timestamp"] and source_time(snap["source_timestamp"]) < max(map(source_time, dated)):
            observations.append(dict(kind="freshness", status="CONFLICT"))
        if snap["source_timestamp"] is None:
            observations.append(dict(kind="freshness", status="UNKNOWN_VALUE"))
        known = {s["ticker"] for s in self.rows("securities")}
        return dict(account_id=account_id, changes=changes, observations=observations,
                    unidentified_securities=sorted(incoming.keys() - known),
                    warnings=snap["warnings"] + (["State differences do not establish transactions"] if changes else []))

    def apply(self, snapshot, allow_older=False, justification=None):
        snap = Snapshot.model_validate(snapshot).model_dump(mode="json")
        account_id = snap["account"]["id"]
        # Import timestamps are provenance, never evidence of source freshness.
        fingerprint = hashlib.sha256(json.dumps({k: v for k, v in snap.items()
            if k not in {"imported_at", "status", "warnings"}}, sort_keys=True).encode()).hexdigest()
        previous = [s for s in self.rows("snapshots") if s["account"]["id"] == account_id]
        latest = max(previous, key=lambda s: s["imported_at"], default=None)
        if latest and latest.get("fingerprint") == fingerprint:
            return dict(status="UNCHANGED", snapshot_id=latest["id"], account_id=account_id, warnings=snap["warnings"])
        dated = [source_time(s["source_timestamp"]) for s in previous if s.get("source_timestamp")]
        if snap["source_timestamp"]:
            older = bool(dated and source_time(snap["source_timestamp"]) < max(dated))
            if older and (not allow_older or not justification or not justification.strip()):
                raise DomainError("Older snapshot requires explicit override and justification", 3)
        if allow_older and (not justification or not justification.strip()):
            raise DomainError("Snapshot override requires a justification")
        if len({p["security"] for p in snap["positions"]}) != len(snap["positions"]):
            raise DomainError("Duplicate positions must be resolved before apply", 3)
        if len({l["id"] for l in snap["lots"]}) != len(snap["lots"]):
            raise DomainError("Duplicate lot identifiers", 3)
        for lot in snap["lots"]:
            if decimal(lot["remaining_quantity"]) > decimal(lot["quantity"]):
                raise DomainError("Lot remaining quantity exceeds original quantity", 3)
        for symbol in {l["security"] for l in snap["lots"]}:
            pos = next((p for p in snap["positions"] if p["security"] == symbol), None)
            if pos is None and not snap["positions_complete"]:
                pos = next((p for p in self.rows("positions") if p["account_id"] == account_id and p["security"] == symbol), None)
            remaining = sum((decimal(l["remaining_quantity"]) for l in snap["lots"] if l["security"] == symbol), Decimal("0"))
            if pos is None or remaining > decimal(pos["quantity"]):
                raise DomainError("Lot quantities exceed imported position", 3)
        with self.connection:
            self.put("accounts", account_id, snap["account"])
            observed_ids = set()
            for p in snap["positions"]:
                supplied = {key: p[key].strip().upper() for key in ("cusip", "isin", "figi") if p.get(key)}
                existing = [s for s in self.rows("securities") if any(s.get(k) == v for k, v in supplied.items())]
                if not existing:
                    existing = [s for s in self.rows("securities") if s["ticker"] == p["security"]
                                and not any(s.get(k) and s[k] != v for k, v in supplied.items())]
                if len(existing) > 1 or (existing and any(existing[0].get(k) and existing[0][k] != v for k, v in supplied.items())):
                    raise DomainError("Security aliases conflict; resolve identity explicitly", 3)
                sid = existing[0]["id"] if existing else str(uuid.uuid4())
                observed_ids.add(sid)
                security = dict(existing[0]) if existing else dict(id=sid, ticker=p["security"], name=p["name"],
                    asset_type=p["asset_type"], currency=snap["account"]["currency"], cusip=None, isin=None, figi=None)
                security.update(ticker=p["security"], **supplied)
                self.put("securities", sid, security)
                p = dict(p, id=f"{account_id}:{sid}", account_id=account_id, security_id=sid,
                         source_timestamp=snap["source_timestamp"])
                self.put("positions", p["id"], p)
            if snap["positions_complete"]:
                for p in self.rows("positions"):
                    if p["account_id"] == account_id and p["security_id"] not in observed_ids:
                        self.connection.execute("DELETE FROM positions WHERE id=?", (p["id"],))
                        for l in self.rows("lots"):
                            if l["account_id"] == account_id and l["security_id"] == p["security_id"]:
                                self.connection.execute("DELETE FROM lots WHERE id=?", (l["id"],))
            if snap["lots_complete"]:
                for lot in self.rows("lots"):
                    if lot["account_id"] == account_id:
                        self.connection.execute("DELETE FROM lots WHERE id=?", (lot["id"],))
            for lot in snap["lots"]:
                sid = self.resolve(lot["security"])["id"]
                prior = next((l for l in self.rows("lots") if l["id"] == lot["id"]), None)
                if prior and (prior["account_id"] != account_id or prior["security_id"] != sid):
                    raise DomainError("Lot identifier belongs to another account/security", 3)
                self.put("lots", lot["id"], dict(lot, account_id=account_id, security_id=sid))
            for p in self.rows("positions"):
                if p["account_id"] == account_id:
                    remaining = sum((decimal(l["remaining_quantity"]) for l in self.rows("lots")
                        if l["account_id"] == account_id and l["security_id"] == p["security_id"]), Decimal("0"))
                    p["lot_state"] = "RESOLVED" if remaining == decimal(p["quantity"]) else "UNRESOLVED"
                    self.put("positions", p["id"], p)
            if snap["cash_known"]:
                self.put("cash_balances", account_id, dict(id=account_id, account_id=account_id,
                    amount=snap["cash"], as_of=snap["source_timestamp"], imported_at=snap["imported_at"]))
            audit_id = str(uuid.uuid4())
            self.put("snapshots", audit_id, dict(snap, id=audit_id, fingerprint=fingerprint,
                override_justification=justification if allow_older else None))
        return dict(status="APPLIED", snapshot_id=audit_id, account_id=account_id, warnings=snap["warnings"])

    def summary(self):
        return summarize(self.state())

    def record_activity(self, activity, yes=False):
        activity = copy.deepcopy(activity)
        aid = activity.get("activity_id")
        if not isinstance(aid, str) or not aid.strip():
            raise DomainError("Every confirmed activity requires a unique activity_id")
        prior = next((a for a in self.rows("activities") if a.get("activity_id") == aid), None)
        content = {k: v for k, v in activity.items() if k not in {"id", "recorded_at"}}
        if prior:
            if {k: v for k, v in prior.items() if k not in {"id", "recorded_at"}} != content:
                raise DomainError("Activity ID already exists with different content", 3)
            return dict(status="UNCHANGED", activity_id=aid, committed=False)
        state = self.state()
        changed, result = activity_change(state, activity)
        if yes:
            with self.connection:
                for table in ["positions", "cash_balances", "lots"]:
                    for item in changed[table]:
                        self.put(table, item["id"], item)
                self.put("activities", aid, dict(content, id=aid,
                    recorded_at=datetime.now(timezone.utc).isoformat()))
        return dict(result, activity_id=aid, status="RECORDED" if yes else "PREVIEW", committed=yes)


def household_currency(state):
    currencies = {a.get("currency", "USD") for a in state.get("accounts", [])}
    if len(currencies) > 1:
        raise DomainError("Household currencies differ; no FX conversion is configured", 3)
    return next(iter(currencies), "USD")


def summarize(state):
    currency = household_currency(state)
    cash = sum((decimal(c["amount"]) for c in state["cash_balances"]), Decimal("0"))
    value = sum((decimal(p["market_value"]) for p in state["positions"]), cash)
    accounts, taxes, allocation = {}, {}, {"CASH": str(cash)}
    warnings = []
    for a in state["accounts"]:
        if not any(c["account_id"] == a["id"] for c in state["cash_balances"]):
            warnings.append(f"{a['id']}: cash balance unavailable; total excludes unknown cash")
        total = sum(
            (decimal(p["market_value"]) for p in state["positions"] if p["account_id"] == a["id"]),
            Decimal("0"),
        )
        total += sum(
            (decimal(c["amount"]) for c in state["cash_balances"] if c["account_id"] == a["id"]),
            Decimal("0"),
        )
        accounts[a["id"]] = str(total)
        taxes[a["tax_status"]] = str(decimal(taxes.get(a["tax_status"], "0")) + total)
    unrealized = Decimal("0")
    for p in state["positions"]:
        asset = p.get("asset_type", "OTHER")
        allocation[asset] = str(decimal(allocation.get(asset, "0")) + decimal(p["market_value"]))
        if p.get("cost_basis") is None:
            warnings.append(f"{p['security']}: basis unavailable")
        else:
            unrealized += decimal(p["market_value"]) - decimal(p["cost_basis"])
    return {
        "currency": currency,
        "total_value": str(value),
        "cash": str(cash),
        "by_account": accounts,
        "by_tax_status": taxes,
        "allocation": allocation,
        "largest_positions": sorted(
            state["positions"], key=lambda p: decimal(p["market_value"]), reverse=True
        )[:10],
        "unrealized_gain_loss_known_basis": str(unrealized),
        "snapshot_dates": sorted({p["as_of"] for p in state["positions"]}),
        "warnings": warnings,
    }


def activity_change(state, activity):
    state = copy.deepcopy(state)
    account_id, kind = activity["account_id"], activity["type"].upper()
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
    if kind in {"BUY", "SELL", "TRANSFER_IN", "TRANSFER_OUT"}:
        qty, price, fee = (
            decimal(activity["quantity"]),
            decimal(activity["price"]),
            decimal(activity.get("fee", 0)),
        )
        if qty <= 0 or price < 0 or fee < 0:
            raise DomainError("Quantity must be positive; price and fee nonnegative")
        security = next(
            (s for s in state["securities"] if activity["security"] in {s["id"], s["ticker"]}), None
        )
        if not security:
            raise DomainError("Security does not resolve")
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
        if selling and qty > decimal(p["quantity"]):
            raise DomainError("Sale/transfer exceeds known position", 3)
        old_qty = decimal(p["quantity"])
        market_price = decimal(p["price"]) if p.get("price") is not None else (
            decimal(p["market_value"]) / old_qty if old_qty else None)
        p["quantity"] = str(old_qty + (-qty if selling else qty))
        if market_price is not None:
            p["market_value"] = str(decimal(p["quantity"]) * market_price)
        else:
            p["market_value"] = "0"
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
                for allocation in allocations:
                    lot = next((l for l in state["lots"] if l["id"] == allocation["lot_id"]
                        and l["account_id"] == account_id and l["security_id"] == security["id"]), None)
                    used = decimal(allocation["quantity"])
                    if lot is None or used <= 0 or used > decimal(lot["remaining_quantity"]):
                        raise DomainError("Executed lot allocation exceeds available lot shares", 3)
                    basis_removed += decimal(lot["cost_basis"]) * used / decimal(lot["quantity"])
                    lot["remaining_quantity"] = str(decimal(lot["remaining_quantity"]) - used)
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
    }


def source_time(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    except (ValueError, AttributeError) as exc:
        raise DomainError("Source timestamp must be an ISO date or datetime") from exc
