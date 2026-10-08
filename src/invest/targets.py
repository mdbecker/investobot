"""Versioned household targets never change accepted holdings or execute trades."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from pydantic import ValidationError

from invest.ledger import summarize
from invest.models import DomainError, TargetInput, decimal


def _target(ledger, target_id):
    target = next((t for t in ledger.rows("targets") if t["id"] == target_id), None)
    if target is None:
        raise DomainError("Target does not exist")
    return target


def _validate_references(ledger, payload):
    securities = {s["id"] for s in ledger.rows("securities")}
    accounts = {a["id"] for a in ledger.rows("accounts")}
    positions = {p["id"] for p in ledger.rows("positions")}
    constraints = payload["planning_constraints"]
    if set(payload["target_allocations"]) - securities - {"CASH"}:
        raise DomainError("Target allocations require registered canonical security IDs or CASH")
    referenced_accounts = (set(constraints["eligible_accounts"])
                           | set(constraints["permitted_securities"])
                           | set(constraints["cash_minimums"])
                           | set(constraints["trade_increments"]))
    if referenced_accounts - accounts:
        raise DomainError("Target constraints reference an unknown account")
    if len(constraints["eligible_accounts"]) != len(set(constraints["eligible_accounts"])):
        raise DomainError("Eligible accounts must be unique")
    if set(constraints["excluded_positions"]) - positions:
        raise DomainError("Excluded positions require accepted canonical position IDs")
    for allowed in constraints["permitted_securities"].values():
        if set(allowed) - securities:
            raise DomainError("Permitted investments require registered canonical security IDs")
    for increments in constraints["trade_increments"].values():
        if set(increments) - securities:
            raise DomainError("Trade increments require registered canonical security IDs")
    known_cash = {c["account_id"] for c in ledger.rows("cash_balances")}
    if set(constraints["cash_minimums"]) - known_cash:
        raise DomainError("Cash minimums require known account cash balances", 3)


def _deactivate_others(ledger, target_id, timestamp):
    for previous in ledger.rows("targets"):
        if previous["id"] != target_id and previous["status"] == "ACTIVE":
            ledger.put("targets", previous["id"], dict(previous, status="DRAFT", updated_at=timestamp))


def save(ledger, payload):
    """Validate a full target input and append an immutable version atomically."""
    try:
        validated = TargetInput.model_validate(payload).model_dump(mode="json")
    except ValidationError as exc:
        raise DomainError(str(exc)) from exc
    _validate_references(ledger, validated)
    previous = _target(ledger, validated["id"]) if validated["id"] else None
    target_id = previous["id"] if previous else str(uuid.uuid4())
    versions = [v for v in ledger.rows("target_versions") if v["id"] == target_id]
    version = max((v["version"] for v in versions), default=0) + 1
    timestamp = datetime.now(timezone.utc).isoformat()
    version_id = str(uuid.uuid4())
    value = dict(validated, id=target_id, version=version, version_id=version_id,
                 created_at=previous["created_at"] if previous else timestamp,
                 updated_at=timestamp)
    metadata = {key: value[key] for key in
                ("id", "name", "description", "status", "version", "created_at", "updated_at")}
    metadata["current_version_id"] = version_id
    with ledger.connection:
        if value["status"] == "ACTIVE":
            _deactivate_others(ledger, target_id, timestamp)
        ledger.put("target_versions", version_id, value)
        ledger.put("targets", target_id, metadata)
    return show(ledger, target_id)


def list_targets(ledger):
    return {"targets": [show(ledger, t["id"]) for t in ledger.rows("targets")]}


def show(ledger, target_id, version=None):
    metadata = _target(ledger, target_id)
    versions = sorted((v for v in ledger.rows("target_versions") if v["id"] == target_id),
                      key=lambda v: v["version"])
    selected = next((v for v in versions if
                     (v["version"] == version if version is not None else
                      v["version_id"] == metadata["current_version_id"])), None)
    if selected is None:
        raise DomainError("Target version does not exist")
    result = dict(selected)
    if selected["version_id"] == metadata["current_version_id"]:
        result.update(status=metadata["status"], updated_at=metadata["updated_at"])
    result["versions"] = [{key: v[key] for key in ("version", "version_id", "updated_at")}
                          for v in versions]
    return result


def activate(ledger, target_id):
    metadata = _target(ledger, target_id)
    timestamp = datetime.now(timezone.utc).isoformat()
    with ledger.connection:
        _deactivate_others(ledger, target_id, timestamp)
        ledger.put("targets", target_id, dict(metadata, status="ACTIVE", updated_at=timestamp))
    return show(ledger, target_id)


def archive(ledger, target_id):
    metadata = _target(ledger, target_id)
    with ledger.connection:
        ledger.put("targets", target_id, dict(metadata, status="ARCHIVED",
                                              updated_at=datetime.now(timezone.utc).isoformat()))
    return show(ledger, target_id)


def diff(ledger, target_id, version=None):
    """Calculate target-minus-current drift with Decimal and canonical identities."""
    target = show(ledger, target_id, version)
    state = ledger.state()
    summary = summarize(state)  # Reuses household currency validation and unknown-cash warnings.
    total = decimal(summary["total_value"])
    current = {"CASH": decimal(summary["cash"])}
    for position in state["positions"]:
        security_id = position["security_id"]
        current[security_id] = current.get(security_id, Decimal("0")) + decimal(position["market_value"])
    rows = []
    for security_id in sorted(set(current) | set(target["target_allocations"])):
        value = current.get(security_id, Decimal("0"))
        current_weight = value / total if total else Decimal("0")
        target_weight = decimal(target["target_allocations"].get(security_id, "0"))
        target_value = total * target_weight
        rows.append({
            "security_id": security_id,
            "current_value": str(value),
            "target_value": str(target_value),
            "difference_value": str(target_value - value),
            "current_weight": str(current_weight),
            "target_weight": str(target_weight),
            "difference_weight": str(target_weight - current_weight),
        })
    return {
        "target_id": target_id,
        "target_version_id": target["version_id"],
        "target_version": target["version"],
        "currency": summary["currency"],
        "total_value": str(total),
        "allocations": rows,
        "warnings": summary["warnings"] + (["Household value is zero; current weights are undefined"]
                                            if not total else []),
        "proposes_trades": False,
    }
