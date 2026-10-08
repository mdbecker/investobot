import json
from decimal import Decimal
from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

scenarios("features/hardening.feature")


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    from invest.ledger import Ledger

    monkeypatch.setenv("INVEST_DB", str(tmp_path / "db"))
    monkeypatch.setenv("INVEST_CONFIG", str(tmp_path / "config.toml"))
    return {"ledger": Ledger(tmp_path / "db")}


def snapshot(cash_known=True):
    return {
        "account": {"id": "synthetic", "name": "synthetic"},
        "positions": [
            {
                "security": "OLD",
                "name": "Synthetic company",
                "asset_type": "STOCK",
                "cusip": "SYNTH0001",
                "quantity": "10",
                "market_value": "1000",
                "price": "100",
                "cost_basis": "1200",
                "as_of": "2026-10-08",
            }
        ],
        "cash": "500",
        "cash_known": cash_known,
        "source_hash": "synthetic",
    }


@given("a snapshot with a CUSIP identified stock")
def existing(ctx):
    ctx["ledger"].apply(snapshot())
    ctx["uuid"] = ctx["ledger"].state()["securities"][0]["id"]


@when("I apply the same CUSIP under a new ticker")
def rename(ctx):
    snap = snapshot()
    snap["positions"][0]["security"] = "NEW"
    ctx["ledger"].apply(snap)


@then("the security UUID remains the same")
def identity(ctx):
    assert len(ctx["ledger"].state()["securities"]) == 1
    assert ctx["ledger"].resolve("NEW")["id"] == ctx["uuid"]


@then("its CUSIP is stored")
def cusip(ctx):
    assert ctx["ledger"].resolve("SYNTH0001")["id"] == ctx["uuid"]


@when("I record a confirmed purchase")
def purchase(ctx):
    ctx["ledger"].record_activity(
        {
            "account_id": "synthetic",
            "security": "OLD",
            "activity_id": "synthetic-buy",
            "type": "BUY",
            "quantity": "2",
            "price": "100",
            "fee": "1",
            "date": "2026-10-08",
        },
        yes=True,
    )


@then("the summary includes the new known basis")
def basis(ctx):
    assert Decimal(ctx["ledger"].summary()["unrealized_gain_loss_known_basis"]) == -201


@given("a snapshot without known cash")
def missing(ctx):
    ctx["ledger"].apply(snapshot(False))


@when("I request a summary")
def summary(ctx):
    try:
        ctx["result"] = ctx["ledger"].summary()
    except Exception as exc:
        ctx["error"] = exc


@then("a missing cash warning is visible")
def warnings(ctx):
    assert any("cash" in w.lower() for w in ctx["result"]["warnings"])


@given("a synthetic market history source")
def synthetic(ctx, monkeypatch):
    monkeypatch.setenv("INVEST_FIXTURES", str(Path("tests/fixtures/fmp-synthetic.json")))


@when("I request security history from the CLI")
def history(ctx):
    from typer.testing import CliRunner

    from invest.cli import app

    ctx["command"] = CliRunner().invoke(app, ["market", "history", "AAA"])


@then("return volatility drawdown and rolling series are supplied")
def metrics(ctx):
    assert ctx["command"].exit_code == 0
    data = json.loads(ctx["command"].stdout)
    assert data["analytics"]["total_return"] == pytest.approx(0.089)
    assert data["analytics"]["maximum_drawdown"] == pytest.approx(-0.1)
    assert data["analytics"]["annualized_volatility"] > 0
    assert isinstance(data["analytics"]["rolling_returns"], list)


@given("accounts in two different currencies")
def currencies(ctx):
    first = snapshot()
    ctx["ledger"].apply(first)
    second = snapshot()
    second["account"] = {"id": "foreign", "name": "foreign", "currency": "EUR"}
    ctx["ledger"].apply(second)


@then("the summary rejects inconsistent currency state")
def currency_reject(ctx):
    from invest.models import DomainError

    assert isinstance(ctx.get("error"), DomainError)
    assert ctx["error"].code == 3


@given("direct and indirect holdings sharing explicit security aliases")
def aliased(ctx, tmp_path):
    from invest.market import MarketClient

    fixture = json.loads(Path("tests/fixtures/fmp-synthetic.json").read_text())
    fixture["holdings"]["ALIAS"] = [
        {"asset": "NEW", "isin": "SYNTHETICISIN", "cusip": "SYNTH0001", "weightPercentage": "100"}
    ]
    path = tmp_path / "fixture.json"
    path.write_text(json.dumps(fixture))
    ctx["client"] = MarketClient(ctx["ledger"], fixture_path=path)
    ctx["state"] = {
        "accounts": [],
        "securities": [
            {"id": "uuid", "ticker": "OLD", "cusip": "SYNTH0001", "asset_type": "STOCK"}
        ],
        "positions": [
            {
                "account_id": "synthetic",
                "security_id": "uuid",
                "security": "OLD",
                "market_value": "100",
                "asset_type": "STOCK",
            },
            {
                "account_id": "synthetic",
                "security": "ALIAS",
                "market_value": "1000",
                "asset_type": "ETF",
            },
        ],
        "cash_balances": [],
    }


@when("I compute aliased exposure")
def alias_exposure(ctx):
    from invest.analytics import exposure

    ctx["result"] = exposure(ctx["state"], ctx["client"])


@then("the direct and indirect values belong to one company")
def merged(ctx):
    assert len(ctx["result"]["exposures"]) == 1
    assert Decimal(ctx["result"]["exposures"][0]["total_value"]) == 1100
