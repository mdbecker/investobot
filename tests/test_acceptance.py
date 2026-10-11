import copy
import json
from decimal import Decimal
from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

scenarios("features/acceptance.feature")


@pytest.fixture
def ctx(tmp_path):
    from invest.ledger import Ledger
    from invest.market import MarketClient

    ledger = Ledger(tmp_path / "db")
    return {
        "ledger": ledger,
        "client": MarketClient(
            ledger, fixture_path=Path("tests/fixtures/discovery-synthetic.json")
        ),
    }


@given("the representative anonymized household fixture")
def household(ctx):
    from invest.market import MarketClient

    ctx["snapshots"] = json.loads(Path("tests/fixtures/household.json").read_text())
    for snapshot in ctx["snapshots"]:
        snapshot['data_environment'] = 'SYNTHETIC'
        ctx["ledger"].apply(snapshot)
    # Household holdings use the dedicated fund fixture; discovery comparison uses its own fixture.
    ctx["holdings_client"] = MarketClient(
        ctx["ledger"], fixture_path=Path("tests/fixtures/fmp-synthetic.json")
    )


@when("an agent checks concentration and a loss sale")
def check(ctx):
    from invest.analytics import exposure
    from invest.tax import analyze

    state = ctx["ledger"].state()
    ctx["exposure"] = exposure(state, ctx["holdings_client"])
    ctx["sale"] = analyze(state, "demo-taxable", "AAA", "5", "100", "2026-10-08", method="HIFO")


@then("direct and indirect exposure and IRA conflicts are reported")
def risk(ctx):
    apple = next(r for r in ctx["exposure"]["exposures"] if r["ticker"] == "AAPL")
    assert Decimal(apple["direct_value"]) == 200
    assert Decimal(apple["indirect_value"]) > 0
    assert ctx["sale"]["wash_sale"]["status"] == "POTENTIAL_CONFLICT"
    assert "demo-traditional" in ctx["sale"]["wash_sale"]["affected_accounts"]
    assert Decimal(ctx["sale"]["long_term_gain_loss"]) == -200


@when("an agent compares replacement funds and alternatives")
def alternatives(ctx):
    from invest.discovery import replacements
    from invest.market import compare
    from invest.scenarios import simulate

    ctx["comparison"] = compare(ctx["holdings_client"], "AAA", "BBB")
    ctx["replacements"] = replacements(ctx["client"], "ORIGINAL", ["ORIGINAL", "SAME"])
    before = ctx["ledger"].path.read_bytes()
    ctx["scenario"] = simulate(
        ctx["ledger"].state(),
        ctx["holdings_client"],
        [
            {
                "type": "SELL",
                "account_id": "demo-taxable",
                "security": "AAA",
                "quantity": "5",
                "price": "100",
                "date": "2026-10-08",
                "method": "HIFO",
            },
            {
                "type": "BUY",
                "account_id": "demo-taxable",
                "security": "BBB",
                "quantity": "5",
                "price": "100",
                "date": "2026-10-08",
            },
        ],
    )
    assert before == ctx["ledger"].path.read_bytes()


@then("raw similarity metrics and no-write scenario results are available")
def results(ctx):
    assert Decimal(ctx["comparison"]["overlap"]) == Decimal(".5")
    assert ctx["replacements"]["candidates"]
    assert Decimal(ctx["scenario"]["long_term_gain_loss"]) == -200


@when("a later normalized snapshot reduces a position")
def reconcile(ctx):
    ctx["next"] = copy.deepcopy(ctx["snapshots"][0])
    ctx["next"]["positions"][0]["quantity"] = "5"
    ctx["next"]["positions"][0]["market_value"] = "500"
    ctx["next"]["lots"] = ctx["next"]["lots"][1:]
    ctx["next"]["positions"][0]["cost_basis"] = ctx["next"]["lots"][0]["cost_basis"]
    ctx["reconciliation"] = ctx["ledger"].reconcile(ctx["next"])


@then("the discrepancy is reported without a transaction")
def changed(ctx):
    assert any(c["kind"] == "quantity" for c in ctx["reconciliation"]["changes"])
    assert ctx["ledger"].state()["activities"] == []


@when("I explicitly accept the later snapshot")
def apply(ctx):
    ctx["ledger"].apply(ctx["next"])


@then("the ledger and normalized audit trail reflect the snapshot")
def audit(ctx):
    position = next(
        p
        for p in ctx["ledger"].state()["positions"]
        if p["account_id"] == "demo-taxable" and p["security"] == "AAA"
    )
    assert position["quantity"] == "5"
    assert len(ctx["ledger"].state()["snapshots"]) == 5


@given("known synthetic fixed-rate bond terms")
def terms(ctx):
    ctx["terms"] = {
        "face_value": "1000",
        "coupon": "0.05",
        "maturity": "2031-01-15",
        "issue_date": "2021-01-15",
        "settlement_date": "2026-10-08",
        "frequency": 2,
        "clean_price": "98",
    }


@when("the agent analyzes those terms")
def bonds(ctx):
    from invest.bonds import analyze

    ctx["bond"] = analyze(ctx["terms"])


@then("yield accrual duration and convexity are available")
def bond_metrics(ctx):
    assert all(
        ctx["bond"][k] is not None
        for k in ["yield_to_maturity", "accrued_interest", "modified_duration", "convexity"]
    )
