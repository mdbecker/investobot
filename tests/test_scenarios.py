from decimal import Decimal
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("features/scenarios.feature")


@pytest.fixture
def ctx(tmp_path):
    from invest.ledger import Ledger
    from invest.market import MarketClient

    ledger = Ledger(tmp_path / "db")
    return {
        "ledger": ledger,
        "client": MarketClient(ledger, fixture_path=Path("tests/fixtures/fmp-synthetic.json")),
    }


def setup(ctx, tax_status):
    account = {
        "id": "primary",
        "name": "primary",
        "institution": "manual",
        "tax_status": tax_status,
        "history_complete": True,
    }
    snapshot = {
        "account": account,
        "positions": [
            {
                "security": "AAA",
                "asset_type": "ETF",
                "quantity": "10",
                "market_value": "1000",
                "price": "100",
                "as_of": "2026-10-08",
                "cost_basis": "1200",
            }
        ],
        "lots": [
            {
                "id": "old",
                "security": "AAA",
                "acquisition_date": "2024-01-01",
                "quantity": "10",
                "remaining_quantity": "10",
                "cost_basis": "1200",
            }
        ],
        "cash": "500",
        "source_hash": "synthetic",
        "source_timestamp": "2026-10-08",
    }
    ctx["ledger"].apply(snapshot)
    ctx["ledger"].apply(
        {
            "account": {
                "id": "other",
                "name": "other",
                "tax_status": "TAX_FREE",
                "history_complete": True,
            },
            "positions": [
                {
                    "security": "BBB",
                    "asset_type": "ETF",
                    "quantity": "0",
                    "market_value": "0",
                    "price": "100",
                    "as_of": "2026-10-08",
                }
            ],
            "cash": "0",
            "source_hash": "synthetic2",
        }
    )
    ctx["before"] = ctx["ledger"].path.read_bytes()


@given("a household with a taxable loss fund and known cash")
def household(ctx):
    setup(ctx, "TAXABLE")


@given("a household with a retirement fund and known cash")
def retirement(ctx):
    setup(ctx, "TAX_DEFERRED")


@when("I simulate a sale and replacement purchase")
def simulate(ctx):
    from invest.scenarios import simulate

    ctx["result"] = simulate(
        ctx["ledger"].state(),
        ctx["client"],
        [
            {
                "type": "SELL",
                "account_id": "primary",
                "security": "AAA",
                "quantity": "5",
                "price": "100",
                "date": "2026-10-08",
            },
            {
                "type": "BUY",
                "account_id": "primary",
                "security": "BBB",
                "quantity": "5",
                "price": "100",
                "date": "2026-10-08",
            },
        ],
    )


@then("taxable losses and selected lots are reported")
def loss(ctx):
    assert Decimal(ctx["result"]["realized_gain_loss"]) == -100
    assert ctx["result"]["tax_analyses"][0]["selected_lots"][0]["id"] == "old"


@then("the Apple exposure decreases")
def exposure_change(ctx):
    changes = ctx["result"]["exposure_changes"]
    assert Decimal(next(c for c in changes if c["ticker"] == "AAPL")["change"]) == -150


@then("the original ledger bytes remain unchanged")
def unchanged(ctx):
    assert ctx["ledger"].path.read_bytes() == ctx["before"]


@when(parsers.parse('I simulate an impossible "{action}"'))
def impossible(ctx, action):
    from invest.models import DomainError
    from invest.scenarios import simulate

    item = {
        "type": action,
        "account_id": "primary",
        "security": "AAA",
        "quantity": "20",
        "price": "100",
        "date": "2026-10-08",
        "amount": "1000",
        "to_account": "other",
    }
    try:
        simulate(ctx["ledger"].state(), ctx["client"], [item])
    except DomainError as exc:
        ctx["error"] = exc


@then("the simulation rejects inconsistent state")
def rejected(ctx):
    assert ctx["error"].code == 3


@then("no taxable gain is reported")
def zero(ctx):
    assert Decimal(ctx["result"]["realized_gain_loss"]) == 0


@when("I simulate a cash transfer to another account")
def transfer(ctx):
    from invest.scenarios import simulate
    # A classified transfer between accounts with the same tax treatment.
    with ctx["ledger"].connection:
        account = next(a for a in ctx["ledger"].rows("accounts") if a["id"] == "other")
        account["tax_status"] = "TAXABLE"
        ctx["ledger"].put("accounts", "other", account)

    ctx["result"] = simulate(
        ctx["ledger"].state(),
        ctx["client"],
        [{"type": "MOVE_CASH", "account_id": "primary", "to_account": "other", "amount": "100", "classification": "CASH_TRANSFER"}],
    )


@then("household value is unchanged and account cash changes")
def moved(ctx):
    assert ctx["result"]["before"]["total_value"] == ctx["result"]["after"]["total_value"]
    assert Decimal(ctx["result"]["after"]["by_account"]["other"]) == 100


@when("I compute historical portfolio risk")
def risk(ctx):
    from invest.analytics import risk

    ctx["result"] = risk(ctx["ledger"].state(), ctx["client"])


@then("the maximum drawdown includes the known cash weight")
def drawdown(ctx):
    assert ctx["result"]["maximum_drawdown"] == pytest.approx(-1 / 15)
    assert ctx["result"]["usable_period"]["start"] == "2026-09-28"
    assert ctx["result"]["usable_period"]["end"] == "2026-10-05"


@then("pairwise correlations and concentration are reported")
def concentration(ctx):
    assert ctx["result"]["position_concentration"]["largest_weight"] == pytest.approx(2 / 3)
    assert ctx["result"]["correlations"]["AAA"]["AAA"] == pytest.approx(1)
