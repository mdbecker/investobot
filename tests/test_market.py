from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from pytest_bdd import given, scenarios, then, when

scenarios("features/market.feature")
FIXTURE = Path(__file__).parent / "fixtures/fmp-synthetic.json"


@pytest.fixture
def context(tmp_path):
    from invest.ledger import Ledger

    return {"ledger": Ledger(tmp_path / "market.db")}


@given("synthetic provider responses")
def provider(context):
    from invest.market import MarketClient

    context["client"] = MarketClient(context["ledger"], fixture_path=FIXTURE)


@when("I retrieve AAA holdings")
def holdings(context):
    context["result"] = context["client"].holdings("AAA")


@then("all available holdings have normalized identities and weights")
def normalized(context):
    rows = context["result"]["holdings"]
    assert len(rows) == 2
    assert rows[0]["ticker"] == "AAPL"
    assert Decimal(rows[0]["weight"]) == Decimal("0.6")
    assert context["result"]["status"] == "AVAILABLE"


@then("the response states source and observation dates")
def provenance(context):
    result = context["result"]
    assert result["source"] == "SYNTHETIC_FMP_FIXTURE"
    assert result["data_as_of"] == "2026-10-01"
    assert datetime.fromisoformat(result["retrieved_at"]).tzinfo


@when("I retrieve PART holdings")
def partial(context):
    context["result"] = context["client"].holdings("PART")


@then("partial coverage is explicitly warned")
def partial_warn(context):
    assert context["result"]["partial"] is True
    assert Decimal(context["result"]["weight_coverage"]) == Decimal("0.2")
    assert context["result"]["warnings"]


def seed_expired(context):
    context["ledger"].put(
        "fund_holdings_cache",
        "SYNTHETIC_FMP_FIXTURE:holdings:AAA",
        {
            "id": "SYNTHETIC_FMP_FIXTURE:holdings:AAA",
            "retrieved_at": "2000-01-01T00:00:00+00:00",
            "source": "SYNTHETIC_FMP_FIXTURE",
            "holdings": [{"ticker": "WRONG"}],
        },
    )
    context["ledger"].connection.commit()


@given("expired cached holdings")
def expired(context):
    seed_expired(context)


@then("refreshed holdings replace the expired cache")
def refresh(context):
    assert context["result"]["holdings"][0]["ticker"] == "AAPL"
    assert (
        context["ledger"]
        .rows("fund_holdings_cache")[0]["retrieved_at"]
        .startswith(str(datetime.now(UTC).year))
    )


@given("expired holdings and an unavailable provider")
def broken(context, monkeypatch):
    from invest.market import MarketClient

    context["client"] = MarketClient(context["ledger"], api_key="synthetic-key")
    context["ledger"].put(
        "fund_holdings_cache",
        "FMP:holdings:AAA",
        {"id": "FMP:holdings:AAA", "retrieved_at": "2000-01-01T00:00:00+00:00", "holdings": []},
    )

    def fail(*args, **kwargs):
        raise httpx.ConnectError("unavailable")

    monkeypatch.setattr(httpx, "get", fail)


@when("I retrieve holdings from the unavailable provider")
def unavailable(context):
    from invest.models import DomainError

    with pytest.raises(DomainError) as error:
        context["client"].holdings("AAA")
    context["error"] = error.value


@then("external unavailability is reported")
def error_code(context):
    assert context["error"].code == 2


@when("I compare AAA and BBB")
def comparison(context):
    from invest.market import compare

    context["result"] = compare(context["client"], "AAA", "BBB")


@then("overlap and active share reflect normalized weights")
def metrics(context):
    result = context["result"]
    assert Decimal(result["overlap"]) == Decimal("0.5")
    assert Decimal(result["active_share"]) == Decimal("0.5")
    assert result["shared_holdings_count"] == 2
    assert Decimal(result["shared_assets_a"]) == 1
    assert Decimal(result["shared_assets_b"]) == Decimal("0.5")


@then("historical return correlation and expense ratios are supplied")
def correlation(context):
    assert context["result"]["historical_return_correlation"] == pytest.approx(1)
    assert context["result"]["expense_ratios"] == {"AAA": "0.10", "BBB": "0.20"}


@when("I retrieve MISSING holdings")
def missing(context):
    context["result"] = context["client"].holdings("MISSING")


@then("missing holdings have unavailable status")
def missing_status(context):
    assert context["result"]["status"] == "DATA_UNAVAILABLE"
    assert context["result"]["holdings"] == []


@when("I retrieve AAA history")
def history(context):
    context["result"] = context["client"].history("AAA")


@then("adjusted history identifies its usable period and gap warnings")
def history_period(context):
    assert context["result"]["usable_period"] == {"start": "2026-09-28", "end": "2026-10-05"}
    assert context["result"]["warnings"]
    assert context["result"]["prices"][0]["adjusted_close"] == "100"
