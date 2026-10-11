"""Reproducible exports of persisted plans, without financial recomputation."""

import hashlib
import json
import os
import tempfile
from pathlib import Path

from invest.models import DomainError


def _text(value):
    if value is None:
        return "unknown"
    if isinstance(value, (dict, list)):
        value = json.dumps(value, sort_keys=True, ensure_ascii=False)
    return (
        str(value).replace("\\", "\\\\").replace("|", "\\|").replace("\r", " ").replace("\n", " ")
    )


def _table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(_text(value) for value in row) + " |" for row in rows)
    if len(lines) == 2:
        lines.append("| " + " | ".join("none supplied" for _ in headers) + " |")
    return "\n".join(lines)


def _allocation_rows(value):
    return value.get("allocations", []) if isinstance(value, dict) else value or []


def render(plan, format="markdown"):
    """Render only stored plan values; do not resolve current state or prices."""
    if format == "json":
        return json.dumps(plan, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if format != "markdown":
        raise DomainError("Report format must be markdown or json")
    target = plan.get("target", {})
    state = plan.get("source_state", {})
    securities = {row["id"]: row for row in state.get("securities", [])}
    accounts = {row["id"]: row for row in state.get("accounts", [])}

    def security_name(identity):
        security = securities.get(identity, {})
        label = security.get("ticker") or identity
        if security.get("name"):
            label = f"{label} · {security['name']}"
        return f"{label} ({identity})"

    assumptions = plan.get("assumptions", {})
    tax = plan.get("tax_analysis", {})
    snapshots = state.get('snapshots', [])
    snapshot_ids = plan.get('source_snapshot_ids', [row['id'] for row in snapshots])
    snapshot_dates = plan.get('source_snapshot_dates', {
        row['account']['id']: row.get('source_timestamp') for row in snapshots})
    lines = [
        f"# {_text(plan.get('name'))}",
        "",
        f"Plan: {_text(plan.get('id'))} · Saved status: {_text(plan.get('status'))}",
        f"Created: {_text(plan.get('created_at'))} · Planning date: {_text(plan.get('as_of'))}",
        "",
        "This is a historical report of saved plan inputs. Use `invest plan show PLAN_ID` to verify current status and whether the plan is STALE before acting.",
        "Trades are not executed automatically. Every proposed trade requires a human decision and manual execution.",
        "",
        "## Target and source portfolio",
        "",
        f"Target: {_text(target.get('name'))} · Version: {_text(target.get('version'))} · Version ID: {_text(plan.get('target_version_id'))}",
        f"Rationale: {_text(target.get('description'))}",
        f"Source snapshots: {_text(snapshot_ids)}",
        f"Source state hash: {_text(plan.get('source_state_hash'))}",
        f"Data environment: {_text(plan.get('data_environment'))}",
        f"Policy: {_text(plan.get('policy_id'))} · Version: {_text(plan.get('policy', {}).get('version'))}",
        f"Policy source: {_text(plan.get('policy', {}).get('source'))}",
        f"Immutable manifests: {_text(plan.get('manifest_ids'))}",
        f"Observation source hashes: {_text({row['id']: row.get('source_hash') for row in snapshots})}",
        "",
        _table(
            ["Account", "Source snapshot date"],
            sorted(snapshot_dates.items()),
        ),
        "",
        "## Market assumptions",
        "",
        _table(
            ["Security", "Price", "Currency", "Source", "As of"],
            [
                [
                    security_name(sid),
                    row.get("price"),
                    row.get("currency"),
                    row.get("source"),
                    row.get("as_of"),
                ]
                for sid, row in sorted(assumptions.get("prices", {}).items())
            ],
        ),
        "",
        f"Market data timestamps: {_text(plan.get('market_data_as_of'))}",
        f"Tax rates: {_text(assumptions.get('tax_rates'))}",
        f"Planning constraints: {_text(assumptions.get('planning_constraints'))}",
        f"Algorithm: {_text(plan.get('algorithm_version', assumptions.get('algorithm')))}",
        "",
        "## Current versus proposed allocation",
        "",
    ]
    current = {row["security_id"]: row for row in _allocation_rows(plan.get("current_allocation"))}
    proposed = {
        row["security_id"]: row for row in _allocation_rows(plan.get("proposed_allocation"))
    }
    lines.append(
        _table(
            [
                "Security",
                "Current value",
                "Proposed value",
                "Target value",
                "Current weight",
                "Proposed weight",
                "Target weight",
            ],
            [
                [
                    security_name(sid),
                    current.get(sid, {}).get("current_value"),
                    proposed.get(sid, {}).get("current_value"),
                    proposed.get(sid, current.get(sid, {})).get("target_value"),
                    current.get(sid, {}).get("current_weight"),
                    proposed.get(sid, {}).get("current_weight"),
                    proposed.get(sid, current.get(sid, {})).get("target_weight"),
                ]
                for sid in sorted(current.keys() | proposed.keys())
            ],
        )
    )
    lines += [
        "",
        "Weights are persisted fractions, not percentage points.",
        "",
        "## Proposed manual trades",
        "",
    ]
    grouped = {}
    for action in plan.get("proposed_actions", []):
        grouped.setdefault(action.get("account_id"), []).append(action)
    for account_id, actions in sorted(grouped.items(), key=lambda item: str(item[0])):
        account = accounts.get(account_id, {})
        lines += [
            f"### {_text(account.get('name') or account_id)} ({_text(account_id)})",
            "",
            _table(
                [
                    "Action",
                    "Security",
                    "Quantity",
                    "Execution price assumption",
                    "Fee",
                    "Date",
                    "Specific lots",
                ],
                [
                    [
                        action.get("type"),
                        security_name(action.get("security")),
                        action.get("quantity"),
                        action.get("price"),
                        action.get("fee"),
                        action.get("date"),
                        action.get("lot_allocations") or action.get("lot_ids"),
                    ]
                    for action in actions
                ],
            ),
            "",
        ]
    if not grouped:
        lines += ["No proposed trades.", ""]
    lines += [
        "## Tax estimates and wash-sale limitations",
        "",
        f"Realized short-term gain/loss: {_text(tax.get('short_term_gain_loss'))}",
        f"Realized long-term gain/loss: {_text(tax.get('long_term_gain_loss'))}",
        f"Total realized gain/loss: {_text(tax.get('realized_gain_loss'))}",
        f"Estimated current tax effect: {_text(tax.get('estimated_tax_effect'))}",
        "",
        "Estimated tax effects exclude filing-specific constraints and automatic wash-sale basis adjustments; loss savings are not guaranteed.",
        "",
    ]
    for analysis in tax.get("analyses", []):
        lines += [
            f"Account {_text(analysis.get('account_id'))}, security {_text(analysis.get('security_id'))}: {_text(analysis.get('status'))}",
            f"Selected lots: {_text(analysis.get('selected_lots'))}",
            f"Completeness: {_text(analysis.get('tax_data_completeness'))}",
            f"Wash-sale concerns: {_text(analysis.get('wash_sale'))}",
            f"Assumptions: {_text(analysis.get('assumptions'))}",
            f"Warnings: {_text(analysis.get('warnings'))}",
            "",
        ]
    before, after = plan.get("cash_before", {}), plan.get("cash_after", {})
    lines += [
        "## Cash balances",
        "",
        _table(
            ["Account", "Before", "After"],
            [
                [account, before.get(account), after.get(account)]
                for account in sorted(before.keys() | after.keys())
            ],
        ),
        "",
        "## Remaining target drift",
        "",
        _table(
            ["Security", "Remaining value difference", "Remaining weight difference"],
            [
                [
                    security_name(row.get("security_id")),
                    row.get("difference_value"),
                    row.get("difference_weight"),
                ]
                for row in _allocation_rows(plan.get("remaining_target_drift"))
            ],
        ),
        "",
        "## Concentration and exposure",
        "",
        _table(
            ["Security", "Before exposure", "After exposure", "Change"],
            [
                [row.get("identifier"), row.get("before"), row.get("after"), row.get("change")]
                for row in plan.get("exposure_analysis", {}).get("changes", [])
            ],
        ),
        "",
        f"Unresolved exposure before: {_text(plan.get('exposure_analysis', {}).get('before', {}).get('unknown_exposure_value'))}",
        f"Unresolved exposure after: {_text(plan.get('exposure_analysis', {}).get('after', {}).get('unknown_exposure_value'))}",
        "",
        "## Missing information and unresolved constraints",
        "",
    ]
    lines += [f"- {_text(warning)}" for warning in plan.get("warnings", [])]
    lines += [f"- {_text(issue.get('code'))}: {_text(issue.get('message'))} · Gates: {_text({key: value for key, value in issue.items() if key.startswith('blocks_')})}"
              for issue in plan.get('issues', [])]
    if not plan.get("warnings"):
        lines.append("No additional warnings were recorded. Human review is still required.")
    return "\n".join(lines) + "\n"


def export(plan, output, format="markdown"):
    """Atomically write an export and return the hash of its exact UTF-8 bytes."""
    content = render(plan, format).encode("utf-8")
    path = Path(output).expanduser().resolve()
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except OSError as error:
        raise DomainError("Report output cannot be written; check path and permissions") from error
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {
        "path": str(path),
        "content_hash": hashlib.sha256(content).hexdigest(),
        "format": format,
        "plan_id": plan["id"],
    }
