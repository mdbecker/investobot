"""Offline plan-storage assessment; run only inside the project's Docker runtime.

The fixture seeds validated normalized records directly to measure saved-plan storage,
not repeated HTML import performance. Financial inputs, IDs and source dates are fixed;
production plan IDs and creation timestamps retain their normal behavior.
"""

import argparse
import hashlib
import json
import platform
import tempfile
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from time import perf_counter

from invest.ledger import Ledger
from invest.market import MarketClient
from invest.models import SecurityInput, Snapshot
from invest.plans import compare, generate, list_plans, show
from invest.reports import export
from invest.targets import save


def build_fixture(ledger):
    """Seed 10 accounts, 1000 positions, 2000 lots and 200 dated snapshots."""
    if any(ledger.state().values()) or ledger.connection.execute("SELECT id FROM plans LIMIT 1").fetchone():
        raise ValueError("Benchmark requires an empty disposable ledger")
    security_ids = [f"synthetic-security-{i:03d}" for i in range(100)]
    account_ids = [f"synthetic-account-{i:02d}" for i in range(10)]
    with ledger.connection:
        for index, identity in enumerate(security_ids):
            security = SecurityInput.model_validate({
                "ticker": f"SYN{index:03d}", "name": f"Synthetic stock {index}",
                "asset_type": "STOCK", "currency": "USD", "source": "synthetic benchmark",
            }).model_dump(mode="json")
            ledger.put("securities", identity, dict(security, id=identity))
        for account_id in account_ids:
            positions = [{
                "security": f"SYN{i:03d}", "name": f"Synthetic stock {i}",
                "asset_type": "STOCK", "quantity": "10", "price": "100",
                "market_value": "1000", "cost_basis": "500", "as_of": "2026-10-08",
            } for i in range(100)]
            lots = [{
                "id": f"{account_id}:lot:{i:03d}:{part}", "security": f"SYN{i:03d}",
                "quantity": "5", "remaining_quantity": "5", "cost_basis": "250",
                "acquisition_date": "2024-01-01" if part == 0 else "2025-01-01",
            } for i in range(100) for part in range(2)]
            latest = None
            for observation in range(20):
                source_date = (date(2026, 9, 19) + timedelta(days=observation)).isoformat()
                payload = Snapshot.model_validate({
                    "account": {"id": account_id, "name": account_id, "institution": "Synthetic",
                                "account_type": "IRA", "tax_status": "TAX_FREE",
                                "currency": "USD", "history_complete": True},
                    "positions": [dict(p, as_of=source_date) for p in positions], "lots": lots,
                    "cash": "100", "positions_complete": True, "lots_complete": True,
                    "source_timestamp": source_date, "imported_at": source_date + "T12:00:00Z",
                    "source_hash": f"synthetic:{account_id}:{source_date}",
                }).model_dump(mode="json")
                fingerprint = hashlib.sha256(json.dumps({
                    k: v for k, v in payload.items() if k not in {"imported_at", "status", "warnings"}
                }, sort_keys=True).encode()).hexdigest()
                identity = f"{account_id}:snapshot:{observation:02d}"
                ledger.put("snapshots", identity, dict(payload, id=identity, fingerprint=fingerprint,
                                                       override_justification=None))
                latest = payload
            ledger.put("accounts", account_id, latest["account"])
            for i, position in enumerate(latest["positions"]):
                identity = f"{account_id}:{security_ids[i]}"
                ledger.put("positions", identity, dict(position, id=identity, account_id=account_id,
                           security_id=security_ids[i], source_timestamp="2026-10-08",
                           lot_state="RESOLVED"))
            for i, lot in enumerate(latest["lots"]):
                ledger.put("lots", lot["id"], dict(lot, account_id=account_id,
                                                  security_id=security_ids[i // 2]))
            ledger.put("cash_balances", account_id, {
                "id": account_id, "account_id": account_id, "amount": "100",
                "as_of": "2026-10-08", "imported_at": "2026-10-08T12:00:00Z",
            })
    return {"security_ids": security_ids, "account_ids": account_ids}


def measure(ledger, fixture, directory):
    """Generate real alternatives and return byte sizes plus elapsed wall times."""
    directory = Path(directory)
    securities = fixture["security_ids"]
    weights = {identity: ".00999" for identity in securities}
    target = save(ledger, {
        "name": "Synthetic storage assessment", "target_allocations": dict(weights, CASH=".001"),
        "planning_constraints": {"eligible_accounts": fixture["account_ids"],
                                 "permitted_securities": {a: securities for a in fixture["account_ids"]}},
    })
    ledger.connection.commit()
    before = ledger.path.stat().st_size
    client = MarketClient(ledger, fixture_path=Path("tests/fixtures/fmp-synthetic.json"))
    plan_ids = []
    generation_started = perf_counter()
    for alternative in range(20):
        plan = generate(ledger, client, target["id"], as_of="2026-10-08",
                        name=f"Synthetic alternative {alternative:02d}", prices={securities[0]: {
                            "price": str(Decimal("100") + Decimal(alternative) / 10),
                            "as_of": "2026-10-08", "currency": "USD",
                            "source": "explicit synthetic alternative assumption"}})
        plan_ids.append(plan["id"])
        del plan
    generation_seconds = perf_counter() - generation_started
    ledger.connection.commit()
    after = ledger.path.stat().st_size
    count, average = ledger.connection.execute(
        "SELECT COUNT(*), AVG(LENGTH(CAST(details_json AS BLOB))) FROM plans"
    ).fetchone()
    started = perf_counter()
    listed = list_plans(ledger)
    list_seconds = perf_counter() - started
    listed_count = len(listed["plans"])
    listed_bytes = len(json.dumps(listed).encode())
    del listed
    started = perf_counter()
    compared = compare(ledger, *plan_ids)
    compare_seconds = perf_counter() - started
    compared_count = len(compared["plans"])
    compared_bytes = len(json.dumps(compared).encode())
    del compared
    first_id = plan_ids[0]
    started = perf_counter()
    retrieved = show(ledger, first_id)
    retrieve_seconds = perf_counter() - started
    started = perf_counter()
    export(retrieved, directory / "benchmark-report.md")
    export_seconds = perf_counter() - started
    return {
        "fixture": {"accounts": 10, "positions": 1000, "lots": 2000,
                    "snapshots_per_account": 20, "alternative_plans": 20},
        "database_bytes_before": before, "database_bytes_after": after,
        "database_growth_bytes": after - before, "average_serialized_plan_bytes": average,
        "plan_count": count, "listed_plan_count": listed_count, "retrieved_plan_id": first_id,
        "listed_response_bytes": listed_bytes, "compared_response_bytes": compared_bytes,
        "compared_plan_count": compared_count, "compare_seconds": compare_seconds,
        "generation_seconds": generation_seconds, "list_seconds": list_seconds,
        "retrieve_seconds": retrieve_seconds, "markdown_export_seconds": export_seconds,
        "python_version": platform.python_version(), "platform": platform.platform(),
        "timing_method": "single cold application call per operation; no external APIs",
        "baseline": "after fixture and target creation, immediately before saving alternatives",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Optional JSON result file; stdout is always JSON")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="investobot-storage-") as directory:
        ledger = Ledger(Path(directory) / "benchmark.db")
        try:
            result = measure(ledger, build_fixture(ledger), directory)
        finally:
            ledger.connection.close()
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered)
    print(rendered, end="")


if __name__ == "__main__":
    main()
