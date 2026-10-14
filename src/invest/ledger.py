"""Small explicit SQLite ledger; mutations are atomic and preserve normalized audit history."""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal, localcontext
from pathlib import Path

from pydantic import ValidationError

from invest.accounting import activity_change as activity_change
from invest.accounting import activity_change_inplace as activity_change_inplace
from invest.accounting import activity_content as activity_content
from invest.issues import _issue as _issue
from invest.models import (
    AccountUpdate,
    Activity,
    ClassificationInput,
    DomainError,
    SecurityInput,
    Snapshot,
    decimal,
)
from invest.portfolio_summary import household_currency as household_currency
from invest.portfolio_summary import summarize as summarize

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
    "targets",
    "target_versions",
]
ACCOUNT_SETTINGS = ("account_type", "tax_status", "history_complete", "currency",
                    "institution", "name", "active")


def snapshot_fingerprint(snap):
    return hashlib.sha256(json.dumps({k: v for k, v in snap.items()
        if k not in {"imported_at", "status", "warnings"}}, sort_keys=True).encode()).hexdigest()




class Ledger:
    def __init__(self, path):
        from invest.db import connect

        self.path = Path(path)
        self.connection = connect(path)

    def rows(self, table, *, account_id=None):
        from invest.db import rows

        if table not in TABLES:
            raise ValueError("Unknown table")
        result = rows(self.connection, table, account_id=account_id)
        history = {"accounts": "metadata_history", "securities": "classification_history"}.get(table)
        if history:
            for row in result:
                row.setdefault(history, [])
        return result

    def put(self, table, key, data):
        from invest.db import put

        if table not in TABLES:
            raise ValueError("Unknown table")
        put(self.connection, table, key, data)

    def _account_snapshots(self, account_id):
        """Read complete account history without decoding unrelated account evidence."""
        return [json.loads(row[0]) for row in self.connection.execute(
            'SELECT payload_json FROM snapshot_observations WHERE account_id=? ORDER BY id',
            (account_id,))]

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

    def planning_state(self):
        """Current financial inputs plus compact latest accepted provenance; no audit payloads."""
        state = {table: self.rows(table) for table in (
            "accounts", "securities", "positions", "lots", "cash_balances", "activities")}
        for table, field in (("accounts", "metadata_history"), ("securities", "classification_history")):
            for row in state[table]:
                row.pop(field, None)
        query = """SELECT id, account_id, imported_at, source_timestamp, source_hash,
                          positions_complete, lots_complete,cash_known,data_environment FROM (
            SELECT id,account_id,imported_at,source_timestamp,source_hash,
                positions_complete,lots_complete,cash_known,data_environment,
                ROW_NUMBER() OVER (PARTITION BY account_id
                    ORDER BY imported_at DESC,id DESC) AS ordinal
            FROM snapshot_observations WHERE status!='EVIDENCE_ONLY') WHERE ordinal=1 ORDER BY account_id"""
        state['snapshots'] = [dict(id=r[0], account={'id': r[1]}, imported_at=r[2],
            source_timestamp=r[3], source_hash=r[4], positions_complete=bool(r[5]),
            lots_complete=bool(r[6]),cash_known=bool(r[7]),data_environment=r[8]) for r in self.connection.execute(query)]
        return state

    def resolve(self, alias):
        from invest.security_identity import resolve

        return resolve(self.rows('securities'), alias)

    def register_security(self, payload):
        data = SecurityInput.model_validate(payload).model_dump(mode="json")
        matches = [s for s in self.rows("securities") if any(data.get(k) and data[k] == s.get(k) for k in ("cusip", "isin", "figi"))]
        if not matches:
            matches = [s for s in self.rows("securities") if s["ticker"] == data["ticker"]]
        if len(matches) > 1 or (matches and any(data.get(k) and matches[0].get(k) and data[k] != matches[0][k] for k in ("cusip", "isin", "figi"))):
            raise DomainError("Security identifiers conflict", 3)
        if matches and (matches[0].get("currency") != data["currency"] or matches[0].get("asset_type") != data["asset_type"]):
            raise DomainError("Security classification conflicts with accepted metadata", 3)
        if matches and any(data.get(key) and matches[0].get(key) and data[key] != matches[0][key]
                           for key in ('cik', 'lei', 'issuer_id', 'data_environment')):
            raise DomainError('Issuer identity conflicts with accepted metadata', 3)
        existing = matches[0] if matches else {}
        data = dict(existing, **{k: v for k, v in data.items() if v is not None}, id=existing.get("id", str(uuid.uuid4())))
        with self.connection:
            self.put("securities", data["id"], data)
        return data

    def classify_security(self, security_id, asset_type, source, confirm=False):
        correction = ClassificationInput.model_validate(dict(asset_type=asset_type, source=source))
        security = next((s for s in self.rows("securities") if s["id"] == security_id), None)
        if security is None:
            raise DomainError("Classification requires an existing canonical security ID", 3)
        previous = security.get("asset_type", "OTHER")
        if previous != correction.asset_type and previous != "OTHER":
            raise DomainError("Known security classification conflicts; manual review required", 3)
        if previous == correction.asset_type:
            return dict(status="UNCHANGED", security_id=security_id, committed=False)
        result = dict(status="PREVIEW", security_id=security_id, previous_type=previous,
                      new_type=correction.asset_type, source=correction.source, committed=False)
        if confirm:
            security["asset_type"] = correction.asset_type
            security["classification_history"].append(dict(previous_type=previous,
                new_type=correction.asset_type, source=correction.source,
                changed_at=datetime.now(timezone.utc).isoformat()))
            with self.connection:
                self.put("securities", security_id, security)
                for position in self.rows("positions"):
                    if position["security_id"] == security_id:
                        self.put("positions", position["id"], dict(position, asset_type=correction.asset_type))
            result.update(status="APPLIED", committed=True)
        return result

    def update_account(self, account_id, payload, yes=False):
        correction = AccountUpdate.model_validate(payload)
        account = next((a for a in self.rows("accounts") if a["id"] == account_id), None)
        if account is None:
            raise DomainError("Account does not exist", 3)
        supplied = correction.model_dump(mode="json", exclude_unset=True)
        changes = {key: dict(before=account.get(key), after=value)
                   for key, value in supplied.items()
                   if key in ACCOUNT_SETTINGS and account.get(key) != value}
        if "currency" in changes and (
                any(p["account_id"] == account_id for p in self.rows("positions")) or
                any(c["account_id"] == account_id for c in self.rows("cash_balances"))):
            raise DomainError("Currency changes with positions or cash balances require an FX model", 3)
        if not changes:
            return dict(status="UNCHANGED", account_id=account_id, committed=False, changes={})
        result = dict(status="PREVIEW", account_id=account_id, changes=changes, committed=False,
                      reason=correction.reason, source=correction.source)
        if yes:
            account.update({key: value["after"] for key, value in changes.items()})
            account["metadata_history"].append(dict(changes=changes, reason=correction.reason,
                source=correction.source, changed_at=datetime.now(timezone.utc).isoformat()))
            with self.connection:
                self.put("accounts", account_id, account)
            result.update(status="APPLIED", committed=True)
        return result

    def _snapshot_security(self, position, account_id, *, securities=None, held=None):
        """Resolve source identities consistently for review and atomic acceptance."""
        from invest.security_identity import resolve_observation

        if held is None:
            held = {row["security_id"] for row in self.rows("positions") if row["account_id"] == account_id}
        if securities is None:
            securities = self.rows('securities')
        return resolve_observation(securities, position, held)

    def reconcile(self, snapshot):
        snap = Snapshot.model_validate(snapshot).model_dump(mode="json")
        account_id = snap["account"]["id"]
        issues = []
        for issue in snap['issues']:
            if issue.get('blocks_acceptance') is True or (
                    'blocks_acceptance' not in issue and issue.get('blocks_calculation')):
                issues.append(dict(issue, blocks_acceptance=True))
            elif (snap['positions_complete'] and issue.get('code') in {
                    'UNRESOLVED_SOURCE_ROW', 'AMBIGUOUS_SUMMARY_ROW', 'UNKNOWN_DATA_ENVIRONMENT'}):
                issues.append(dict(issue, blocks_acceptance=True))
            else:
                issues.append(dict(issue, blocks_acceptance=issue.get('blocks_acceptance', False)))
        environment = snap['data_environment']
        if environment is None:
            issues.append(_issue('UNKNOWN_DATA_ENVIRONMENT',
                'Confirm REAL or SYNTHETIC provenance before accepting observations'))
        elif any(row.get('data_environment') not in (None, environment)
                 for row in snap['positions'] + snap['lots']):
            issues.append(_issue('MIXED_DATA_ENVIRONMENT',
                'Observation rows must share the explicitly confirmed source environment'))
        accepted = next((row for row in self.rows('accounts') if row['id'] == account_id), None)
        if accepted and accepted.get('data_environment') not in (None, environment):
            issues.append(_issue('MIXED_DATA_ENVIRONMENT',
                'Observation provenance conflicts with the accepted account environment'))
        value_checks = []
        for position in snap['positions']:
            precisions = [position.get(name) for name in
                          ('displayed_price_precision', 'displayed_market_value_precision')]
            if any(type(value) is not int or not 0 <= value <= 100 for value in precisions):
                issues.append(_issue('UNKNOWN_PRICE_PRECISION',
                    'Verify original displayed price and value precision', security=position['security']))
                continue
            quantity, price, value = [decimal(position[name]) for name in
                                      ('quantity', 'price', 'market_value')]
            with localcontext() as context:
                context.prec = max(100, sum(len(number.as_tuple().digits) + abs(number.as_tuple().exponent)
                                           for number in (quantity, price, value)) + 110)
                discrepancy = abs(quantity * price - value)
                tolerance = max(Decimal('0.01'), abs(quantity) * Decimal('0.5') *
                                Decimal(10) ** -precisions[0] +
                                Decimal('0.5') * Decimal(10) ** -precisions[1])
                value_checks.append(dict(security=position['security'],
                    observed_discrepancy=format(discrepancy, 'f'),
                    rounding_tolerance=format(tolerance, 'f'), within_tolerance=discrepancy <= tolerance))
                if discrepancy > tolerance:
                    issues.append(_issue('INCONSISTENT_POSITION_VALUE',
                        'Reported value exceeds source rounding tolerance', security=position['security']))
        existing_positions = self.rows('positions', account_id=account_id)
        securities = self.rows('securities')
        held = {p['security_id'] for p in existing_positions if p['account_id'] == account_id}
        old = {p['security_id']: p for p in existing_positions}
        incoming = {}
        for position in snap['positions']:
            try:
                security, _ = self._snapshot_security(position, account_id,
                    securities=securities, held=held)
            except DomainError as error:
                issues.append(_issue('SECURITY_IDENTITY_CONFLICT', str(error),
                                     security=position['security']))
                continue
            identity = security['id'] if security else position['security']
            if identity in incoming:
                issues.append(_issue('SECURITY_IDENTITY_CONFLICT',
                    'Multiple source positions resolve to one canonical security', security=identity))
            incoming[identity] = position
        changes, observations = [], []
        for symbol in sorted(old.keys() | incoming.keys()):
            if symbol not in incoming:
                entry = {"kind": "removed_position", "security": symbol,
                         "status": "CHANGED_VALUE" if snap["positions_complete"] else "UNKNOWN_VALUE"}
                (changes if snap["positions_complete"] else observations).append(entry)
            elif symbol not in old:
                changes.append({"kind": "new_position", "security": symbol, "status": "CHANGED_VALUE"})
            else:
                if old[symbol]['security'] != incoming[symbol]['security']:
                    changes.append(dict(kind='ticker', security_id=symbol,
                        before=old[symbol]['security'], after=incoming[symbol]['security'],
                        status='CHANGED_VALUE'))
                for field in ("quantity", "price", "market_value", "cost_basis"):
                    before, after = old[symbol].get(field), incoming[symbol].get(field)
                    status = "UNKNOWN_VALUE" if after is None else (
                        "CONFIRMED_VALUE" if before is not None and decimal(before) == decimal(after)
                        else "CHANGED_VALUE")
                    entry = dict(kind=field, security=symbol, before=before, after=after, status=status)
                    (changes if status == "CHANGED_VALUE" else observations).append(entry)
        account = next((a for a in self.rows("accounts") if a["id"] == account_id), None)
        discrepancies = [dict(field=k, before=account.get(k), after=snap["account"].get(k))
                         for k in ACCOUNT_SETTINGS if account and account.get(k) != snap["account"].get(k)]
        if discrepancies:
            changes.append(dict(kind="account_classification", status="CHANGED_VALUE",
                                before=account, after=snap["account"], applied=False))
        current_cash = next((c for c in self.rows("cash_balances") if c["account_id"] == account_id), None)
        if snap["cash_known"] and (not current_cash or decimal(current_cash["amount"]) != decimal(snap["cash"])):
            changes.append(dict(kind="cash", status="CHANGED_VALUE",
                                before=current_cash["amount"] if current_cash else None, after=snap["cash"]))
        elif not snap["cash_known"]:
            observations.append(dict(kind="cash", status="UNKNOWN_VALUE"))
        old_lots = [{k: v for k, v in lot.items() if k not in {"account_id", "security_id"}}
                    for lot in self.rows("lots", account_id=account_id)]
        if snap["lots"] and sorted(old_lots, key=lambda l: l["id"]) != sorted(snap["lots"], key=lambda l: l["id"]):
            changes.append(dict(kind="lots", status="CHANGED_VALUE"))
        elif snap["lots_complete"] and old_lots != snap["lots"]:
            changes.append(dict(kind="lots", status="CHANGED_VALUE"))
        elif not snap["lots_complete"]:
            observations.append(dict(kind="lots", status="UNKNOWN_VALUE"))
        previous = self._account_snapshots(account_id)
        dated = [s["source_timestamp"] for s in previous if s.get("source_timestamp")]
        latest_known = max(dated, key=source_time, default=None)
        source_status = "NO_PRIOR_DATED_STATE"
        if latest_known:
            source_status = ("UNKNOWN_SOURCE_DATE" if snap["source_timestamp"] is None else
                "OLDER_THAN_ACCEPTED" if source_time(snap["source_timestamp"]) < source_time(latest_known)
                else "KNOWN_CURRENT")
        elif snap["source_timestamp"]:
            source_status = "KNOWN_CURRENT"
        identical = any(s.get("fingerprint") == snapshot_fingerprint(snap) for s in previous)
        # Applying an undated observation replaces current source timestamps,
        # even when numerical values agree. Losing dated provenance is itself
        # a change requiring review; only an identical accepted import is exempt.
        override_required = not identical and (source_status == "OLDER_THAN_ACCEPTED" or
            source_status == "UNKNOWN_SOURCE_DATE")
        warnings = list(snap["warnings"])
        if source_status == "OLDER_THAN_ACCEPTED":
            observations.append(dict(kind="freshness", status="CONFLICT"))
            warnings.append("Older source date requires a reviewed override and justification")
        if snap["source_timestamp"] is None:
            issues.append(dict(_issue('UNKNOWN_SOURCE_DATE',
                'Import time does not establish source freshness'), blocks_acceptance=False))
            observations.append(dict(kind="freshness", status="UNKNOWN_VALUE"))
            warnings.append("Unknown source date; import time does not establish source freshness")
            if override_required:
                warnings.append("Undated changes may replace more trustworthy dated observations; override required")
        if discrepancies:
            warnings.append("Account configuration is preserved by snapshot application; use invest account update for reviewed corrections")
        classification_reviews = []
        for position in snap["positions"]:
            try:
                security, _ = self._snapshot_security(position, account_id, securities=securities, held=held)
            except DomainError as error:
                issues.append(_issue('SECURITY_IDENTITY_CONFLICT', str(error), security=position['security']))
                continue
            if (security and security.get("asset_type", "OTHER") == "OTHER"
                    and position["asset_type"] != "OTHER"):
                classification_reviews.append(dict(security_id=security["id"],
                    ticker=security["ticker"], canonical_type="OTHER", observed_type=position["asset_type"],
                    action_required="EXPLICIT_CLASSIFICATION"))
                warnings.append(f"{security['id']} ({security['ticker']}): source suggests {position['asset_type']}; "
                    "canonical OTHER is preserved. Verify provenance, then use "
                    f"invest security classify {security['id']} --asset-type {position['asset_type']} "
                    '--source "VERIFIED_SOURCE" --confirm for an explicit audited correction')
        events = [row for row in self.rows('activities') if row['account_id'] == account_id]
        if events:
            source = snap['source_timestamp']
            latest_event = max((row.get('event_timestamp') or row['date'] for row in events), key=source_time)
            if source is None or source[:10] < latest_event[:10]:
                issues.append(_issue('OBSERVATION_PRECEDES_CONFIRMED_ACTIVITY',
                    'Observation is evidence only; confirmed activity remains authoritative'))
            elif source[:10] == latest_event[:10] and (len(source) == 10 or len(latest_event) == 10):
                issues.append(_issue('AMBIGUOUS_SOURCE_ORDER',
                    'Verify source and event ordering with dated original evidence'))
            elif source_time(source) < source_time(latest_event):
                issues.append(_issue('OBSERVATION_PRECEDES_CONFIRMED_ACTIVITY',
                    'Dated observation precedes the confirmed activity'))
            else:
                canonical_old = {row['security_id']: row for row in existing_positions
                                 if row['account_id'] == account_id}
                canonical_incoming = {}
                for symbol, position in incoming.items():
                    try:
                        security, _ = self._snapshot_security(position, account_id, securities=securities, held=held)
                    except DomainError:
                        # The identity review pass above already records its typed blocker.
                        continue
                    canonical_id = security['id'] if security else symbol
                    canonical_incoming[canonical_id] = position
                    prior_position = canonical_old.get(canonical_id)
                    if prior_position and decimal(position['quantity']) != decimal(prior_position['quantity']):
                        issues.append(_issue('CONFIRMED_EVENT_DISCREPANCY',
                            'Observation quantity contradicts confirmed activity', security=symbol))
                if snap['positions_complete']:
                    for identity in canonical_old.keys() - canonical_incoming.keys():
                        if decimal(canonical_old[identity]['quantity']) > 0:
                            issues.append(_issue('CONFIRMED_EVENT_DISCREPANCY',
                                'Complete observation omits confirmed inventory', security=canonical_old[identity]['security']))
                if snap['cash_known'] and current_cash and decimal(snap['cash']) != decimal(current_cash['amount']):
                    issues.append(_issue('CONFIRMED_EVENT_DISCREPANCY',
                        'Observation cash contradicts confirmed activity', account_id=account_id))
                known_lots = {row['id']: row for row in old_lots}
                if snap['lots_complete']:
                    observed_lots = {row['id'] for row in snap['lots']}
                    for identity in known_lots.keys() - observed_lots:
                        if decimal(known_lots[identity]['remaining_quantity']) > 0:
                            issues.append(_issue('CONFIRMED_EVENT_DISCREPANCY',
                                'Complete observation omits remaining confirmed lot inventory', lot_id=identity))
                for candidate in snap['lots']:
                    previous = known_lots.get(candidate['id'])
                    if previous is not None and any(
                            candidate.get(field) is not None and previous.get(field) is not None and
                            decimal(candidate[field]) != decimal(previous[field])
                            for field in ('remaining_quantity', 'remaining_adjusted_basis')):
                        issues.append(_issue('CONFIRMED_EVENT_DISCREPANCY',
                            'Observation lot contradicts confirmed adjusted inventory', lot_id=candidate['id']))
        return dict(account_id=account_id, changes=changes, observations=observations,
                    value_checks=value_checks,
                    status='REVIEW_REQUIRED' if issues else 'AVAILABLE', issues=issues,
                    classification_reviews=classification_reviews,
                    account_metadata_discrepancies=discrepancies,
                    source_date_status=source_status, latest_known_source_date=latest_known,
                    override_required=override_required,
                    unidentified_securities=sorted(p['security'] for identity, p in incoming.items()
                                                   if identity not in {s['id'] for s in securities}),
                    warnings=warnings + (["State differences do not establish transactions"] if changes else []))

    def apply(self, snapshot, allow_older=False, justification=None):
        snap = Snapshot.model_validate(snapshot).model_dump(mode="json")
        account_id = snap["account"]["id"]
        # Import timestamps are provenance, never evidence of source freshness.
        fingerprint = snapshot_fingerprint(snap)
        previous = self._account_snapshots(account_id)
        identical = next((s for s in previous if s.get("fingerprint") == fingerprint), None)
        if identical:
            return dict(status="UNCHANGED", snapshot_id=identical["id"], account_id=account_id, warnings=snap["warnings"])
        reconciliation = self.reconcile(snap)
        acceptance_issues = [issue for issue in reconciliation['issues'] if issue.get('blocks_acceptance', True)]
        if acceptance_issues:
            if {row['code'] for row in acceptance_issues} == {'OBSERVATION_PRECEDES_CONFIRMED_ACTIVITY'}:
                audit_id = str(uuid.uuid4())
                with self.connection:
                    self.put('snapshots', audit_id, dict(snap, id=audit_id,
                        fingerprint=fingerprint, status='EVIDENCE_ONLY'))
                return dict(status='REVIEW_REQUIRED', committed=False, snapshot_id=audit_id,
                            issues=reconciliation['issues'])
            error = DomainError('Observation requires resolution of acceptance issues', 3)
            error.result = reconciliation
            raise error
        if allow_older and (not justification or not justification.strip()):
            raise DomainError("Snapshot override requires a justification")
        if reconciliation["override_required"] and (not allow_older or not justification or not justification.strip()):
            raise DomainError("Older or undated snapshot requires explicit override and justification", 3)
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
                pos = next((p for p in self.rows("positions", account_id=account_id) if p["security"] == symbol), None)
            remaining = sum((decimal(l["remaining_quantity"]) for l in snap["lots"] if l["security"] == symbol), Decimal("0"))
            if (pos is not None and snap["lots_complete"] and remaining == decimal(pos["quantity"])
                    and pos.get("cost_basis") is not None):
                basis = sum((decimal(l['remaining_adjusted_basis']) if l.get('remaining_adjusted_basis') is not None else
                             decimal(l["cost_basis"]) * decimal(l["remaining_quantity"]) / decimal(l["quantity"])
                             for l in snap["lots"] if l["security"] == symbol), Decimal("0"))
                if abs(basis - decimal(pos["cost_basis"])) > Decimal("0.01"):
                    raise DomainError("Position basis contradicts complete lot inventory", 3)
            if pos is None or remaining > decimal(pos["quantity"]):
                raise DomainError("Lot quantities exceed imported position", 3)
        with self.connection:
            account = next((a for a in self.rows("accounts") if a["id"] == account_id), None)
            accepted_account = account or dict(snap['account'], data_environment=snap['data_environment'])
            self.put("accounts", account_id, accepted_account)
            # Call-local writer indexes retain canonical identities and are updated
            # after writes. Resolution still uses the shared ambiguity checks.
            positions_by_id = {p['id']: p for p in self.rows('positions', account_id=account_id)}
            securities_by_id = {s['id']: s for s in self.rows('securities')}
            held = {p['security_id'] for p in positions_by_id.values() if p['account_id'] == account_id}
            original_lots = self.rows('lots', account_id=account_id)
            known_account_lot_ids = {lot['id'] for lot in original_lots}
            observed_ids = set()
            for p in snap["positions"]:
                existing, supplied = self._snapshot_security(p, account_id,
                    securities=securities_by_id.values(), held=held)
                sid = existing["id"] if existing else str(uuid.uuid4())
                observed_ids.add(sid)
                security = dict(existing) if existing else dict(id=sid, ticker=p["security"], name=p["name"],
                    asset_type=p["asset_type"], currency=(account or snap["account"])["currency"], cusip=None, isin=None, figi=None,
                    data_environment=snap['data_environment'])
                security.update(ticker=p["security"], **supplied)
                accepted_type = security.get("asset_type", "OTHER")
                if accepted_type != "OTHER" and p["asset_type"] not in {"OTHER", accepted_type}:
                    raise DomainError("Source security classification conflicts; manual review required", 3)
                # An observed type is initial metadata only for a new security.
                # Established OTHER corrections require classify_security().
                self.put("securities", sid, security)
                securities_by_id[sid] = security
                p = dict(p, asset_type=security["asset_type"], id=f"{account_id}:{sid}", account_id=account_id, security_id=sid,
                         source_timestamp=snap["source_timestamp"], data_environment=snap['data_environment'])
                prior_position = positions_by_id.get(p['id'])
                if (p.get("cost_basis") is None and prior_position and not snap["lots_complete"]
                        and decimal(p["quantity"]) == decimal(prior_position["quantity"])
                        and prior_position.get("lot_state") == "RESOLVED"):
                    p["cost_basis"] = prior_position.get("cost_basis")
                self.put("positions", p["id"], p)
                positions_by_id[p['id']] = p
                held.add(sid)
            if snap["positions_complete"]:
                for p in list(positions_by_id.values()):
                    if p["account_id"] == account_id and p["security_id"] not in observed_ids:
                        self.connection.execute("DELETE FROM position_balances WHERE id=?", (p["id"],))
                        del positions_by_id[p['id']]
                        for l in original_lots:
                            if l["account_id"] == account_id and l["security_id"] == p["security_id"]:
                                self.connection.execute("DELETE FROM tax_lots WHERE id=? AND NOT EXISTS "
                                    "(SELECT 1 FROM activity_lot_allocations WHERE lot_id=tax_lots.id)", (l["id"],))
            if snap["lots_complete"]:
                for lot in original_lots:
                    if lot["account_id"] == account_id:
                        self.connection.execute("DELETE FROM tax_lots WHERE id=? AND NOT EXISTS "
                            "(SELECT 1 FROM activity_lot_allocations WHERE lot_id=tax_lots.id)", (lot["id"],))
            # Refresh after guarded deletes: allocation-protected historical lots
            # remain visible, while genuinely deleted lots have no current row.
            lots_by_id = {lot['id']: lot for lot in self.rows('lots', account_id=account_id)}
            from invest.db import rows as database_rows
            from invest.security_identity import resolve
            for lot in snap["lots"]:
                sid = resolve(securities_by_id.values(), lot["security"])["id"]
                prior = lots_by_id.get(lot['id'])
                if prior is None and lot['id'] not in known_account_lot_ids:
                    # Lot IDs are globally unique, even when inventory reads are local.
                    matches = database_rows(self.connection, 'lots', key=lot['id'])
                    prior = matches[0] if matches else None
                if prior and (prior["account_id"] != account_id or prior["security_id"] != sid):
                    raise DomainError("Lot identifier belongs to another account/security", 3)
                accepted_lot = dict(lot, account_id=account_id, security_id=sid,
                    data_environment=snap['data_environment'])
                self.put("lots", lot["id"], accepted_lot)
                lots_by_id[lot['id']] = accepted_lot
            remaining_by_security = {}
            for lot in sorted(lots_by_id.values(), key=lambda row: row['id']):
                if lot['account_id'] == account_id:
                    sid = lot['security_id']
                    remaining_by_security[sid] = remaining_by_security.get(sid, Decimal('0')) + decimal(lot['remaining_quantity'])
            for p in positions_by_id.values():
                if p["account_id"] == account_id:
                    remaining = remaining_by_security.get(p['security_id'], Decimal('0'))
                    p["lot_state"] = "RESOLVED" if remaining == decimal(p["quantity"]) else "UNRESOLVED"
                    self.put("positions", p["id"], p)
            if snap["cash_known"]:
                self.put("cash_balances", account_id, dict(id=account_id, account_id=account_id,
                    amount=snap["cash"], as_of=snap["source_timestamp"], imported_at=snap["imported_at"],
                    data_environment=snap['data_environment']))
            audit_id = str(uuid.uuid4())
            self.put("snapshots", audit_id, dict(snap, id=audit_id, fingerprint=fingerprint,
                override_justification=justification if allow_older else None,
                override_kind=("UNKNOWN_SOURCE_DATE_OVERRIDE" if snap["source_timestamp"] is None
                    else "OLDER_SOURCE_OVERRIDE") if allow_older and reconciliation["override_required"] else None))
        return dict(status="APPLIED", snapshot_id=audit_id, account_id=account_id,
                    warnings=reconciliation["warnings"], issues=reconciliation['issues'],
                    evidence_complete=not reconciliation['issues'])

    def summary(self):
        return summarize(self.state())

    def record_activity(self, activity, yes=False):
        try:
            activity = Activity.model_validate(activity).model_dump(mode="json", exclude_unset=True)
        except ValidationError as exc:
            raise DomainError(str(exc)) from exc
        aid = activity.get("activity_id")
        if not isinstance(aid, str) or not aid.strip():
            raise DomainError("Every confirmed activity requires a unique activity_id")
        prior = next((a for a in self.rows("activities") if a.get("activity_id") == aid), None)
        content = {k: v for k, v in activity.items() if k not in {"id", "recorded_at"}}
        account = next((row for row in self.rows('accounts') if row['id'] == activity['account_id']), None)
        if account and account.get('data_environment'):
            content['data_environment'] = account['data_environment']
        if (account and account.get('data_environment') == 'REAL' and
                activity['type'] in {'BUY', 'SELL', 'DIVIDEND_REINVESTMENT'} and 'fee' not in activity):
            error = DomainError('Executed fee is unknown; explicitly review the original confirmation', 3)
            error.result = {'status': 'BLOCKED', 'issues': [_issue('UNKNOWN_EXECUTION_FEE', str(error))]}
            raise error
        content = activity_content(content)
        if prior:
            original = {k: v for k, v in prior.items() if k not in {"id", "recorded_at"}}
            if original.get('lot_allocations'):
                original['lot_allocations'] = [{k: row[k] for k in ('lot_id', 'quantity')}
                                              for row in original['lot_allocations']]
            if activity_content(original) != content:
                error = DomainError("Activity ID already exists with different content", 3)
                error.result = {'status': 'BLOCKED', 'issues': [_issue('ACTIVITY_ID_CONFLICT', str(error))]}
                raise error
            return dict(status="UNCHANGED", activity_id=aid, committed=False)
        state = self.state()
        changed, result = activity_change(state, activity)
        confirmed_allocations = result.pop('_confirmed_allocations', None)
        if yes:
            with self.connection:
                for table in ["positions", "cash_balances", "lots"]:
                    for item in changed[table]:
                        self.put(table, item["id"], item)
                accepted_content = dict(content)
                if confirmed_allocations is not None:
                    accepted_content['lot_allocations'] = confirmed_allocations
                self.put("activities", aid, dict(accepted_content, id=aid,
                    recorded_at=datetime.now(timezone.utc).isoformat()))
        return dict(result, activity_id=aid, status="RECORDED" if yes else "PREVIEW", committed=yes)


def source_time(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    except (ValueError, AttributeError) as exc:
        raise DomainError("Source timestamp must be an ISO date or datetime") from exc
