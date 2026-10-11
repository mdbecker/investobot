import copy
import runpy
from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from invest.ledger import Ledger
from invest.market import MarketClient
from invest.plan_storage import load_plan, summaries
from invest.plans import generate, list_plans, persisted, show
from invest.reports import export
from invest.targets import save

scenarios("features/storage_stabilization.feature")


@pytest.fixture
def ctx(tmp_path):
    ledger = Ledger(tmp_path / "ledger.db")
    yield {"ledger": ledger, "directory": tmp_path}
    ledger.connection.close()


def snapshot(quantity, source_hash, source_date):
    return {
        "account": {"id": "ira", "name": "Synthetic IRA", "tax_status": "TAX_FREE"},
        "positions": [{"security": "SYN", "asset_type": "STOCK", "quantity": str(quantity),
                       "price": "100", "market_value": str(quantity * 100),
                       "cost_basis": str(quantity * 50), "as_of": source_date, 'displayed_price_precision': 0, 'displayed_market_value_precision': 0}],
        "lots": [{"id": "synthetic-lot", "security": "SYN", "quantity": str(quantity),
                  "remaining_quantity": str(quantity), "cost_basis": str(quantity * 50),
                  "acquisition_date": "2024-01-01"}],
        "cash": "100", "source_hash": source_hash, "source_timestamp": source_date,
        "positions_complete": True, "lots_complete": True,
    }


@given("a saved plan based on a dated synthetic portfolio")
def saved(ctx):
    ledger = ctx["ledger"]
    ledger.apply(snapshot(10, "synthetic-original", "2026-10-08"))
    identity = ledger.resolve("SYN")["id"]
    target = save(ledger, {
        "name": "Synthetic allocation", "target_allocations": {identity: ".5", "CASH": ".5"},
        "planning_constraints": {"eligible_accounts": ["ira"],
                                 "permitted_securities": {"ira": [identity]}},
    })
    ctx.update(identity=identity, target=target,
               client=MarketClient(ledger, fixture_path=Path("tests/fixtures/fmp-synthetic.json")))
    plan = generate(ledger, ctx["client"], target["id"], as_of="2026-10-08")
    ctx["original"] = copy.deepcopy(plan)


@when("a later snapshot changes the live holdings")
def changed(ctx):
    ctx["ledger"].apply(snapshot(12, "synthetic-later", "2026-10-09"))


@then("the saved plan retains its original inputs and source snapshot identifiers")
def retained(ctx):
    plan = persisted(ctx["ledger"], ctx["original"]["id"])
    assert plan == ctx["original"]
    identifiers = plan["source_snapshot_ids"]
    assert identifiers
    historical_ids = {row["id"] for row in ctx["ledger"].rows("snapshots")}
    assert set(identifiers) <= historical_ids
    assert plan["source_state"]["positions"][0]["quantity"] == "10"


@then("current inspection identifies the saved plan as stale")
def stale(ctx):
    assert show(ctx["ledger"], ctx["original"]["id"])["status"] == "STALE"


@given("its historical Markdown report has been exported")
def first_export(ctx):
    path = ctx["directory"] / "before.md"
    export(persisted(ctx["ledger"], ctx["original"]["id"]), path)
    ctx["report_bytes"] = path.read_bytes()


@then("exporting the persisted plan again produces identical bytes")
def same_export(ctx):
    path = ctx["directory"] / "after.md"
    export(persisted(ctx["ledger"], ctx["original"]["id"]), path)
    assert path.read_bytes() == ctx["report_bytes"]


@when("a second alternative uses a different explicit price assumption")
def alternative(ctx):
    ctx["second"] = generate(ctx["ledger"], ctx["client"], ctx["target"]["id"],
                             as_of="2026-10-08", prices={ctx["identity"]: {
                                 "price": "110", "as_of": "2026-10-08",
                                 "currency": "USD", "source": "synthetic assumption"}})
    ctx["second"] = copy.deepcopy(ctx["second"])


@when("the database is closed and reopened")
def reopened(ctx):
    ctx["ledger"].connection.close()
    ctx["ledger"] = Ledger(ctx["directory"] / "ledger.db")


@then("both plans retain their independent prices and original inputs")
def independent(ctx):
    assert len(list_plans(ctx["ledger"])["plans"]) == 2
    assert persisted(ctx["ledger"], ctx["original"]["id"]) == ctx["original"]
    assert persisted(ctx["ledger"], ctx["second"]["id"]) == ctx["second"]
    identity = ctx["identity"]
    assert ctx["original"]["assumptions"]["prices"][identity]["price"] == "100"
    assert ctx["second"]["assumptions"]["prices"][identity]["price"] == "110"


@given("ten accounts with one thousand positions two thousand lots and twenty snapshots each")
def workload(ctx):
    script = Path(__file__).resolve().parents[1] / "scripts" / "benchmark_plan_storage.py"
    ctx["benchmark"] = runpy.run_path(str(script))
    ctx["workload"] = ctx["benchmark"]["build_fixture"](ctx["ledger"])
    state = ctx["ledger"].state()
    assert len(state["accounts"]) == 10
    assert len(state["positions"]) == 1000
    assert len(state["lots"]) == 2000
    assert len(state["snapshots"]) == 200
    assert all(sum(s["account"]["id"] == a["id"] for s in state["snapshots"]) == 20
               for a in state["accounts"])


@when("twenty independent alternative plans are saved")
def workload_plans(ctx):
    ctx["measurements"] = ctx["benchmark"]["measure"](
        ctx["ledger"], ctx["workload"], ctx["directory"])


@then("all twenty plans can be listed retrieved and exported")
def accessible(ctx):
    result = ctx["measurements"]
    assert result["plan_count"] == 20
    assert result["listed_plan_count"] == 20
    assert result["retrieved_plan_id"] in {p["id"] for p in [load_plan(ctx["ledger"], row['id']) for row in summaries(ctx["ledger"])]}
    assert (ctx["directory"] / "benchmark-report.md").read_text().startswith("# ")


@then("storage measurements cover database growth plan size and access times")
def measurements(ctx):
    result = ctx["measurements"]
    assert result["database_bytes_after"] > result["database_bytes_before"] > 0
    assert result["average_serialized_plan_bytes"] > 0
    for key in ("list_seconds", "retrieve_seconds", "markdown_export_seconds"):
        assert result[key] >= 0
    assert result["listed_response_bytes"] < 128 * 1024
    assert result["compared_response_bytes"] < 128 * 1024
    assert result["compared_plan_count"] == 20
    assert result["compare_seconds"] >= 0
