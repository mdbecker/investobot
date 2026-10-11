from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from invest.analytics import exposure, risk
from invest.tax import analyze

scenarios("features/tax_v2.feature")


@pytest.fixture
def ctx():
    return {}


@given("a dated taxable household with two complete lots")
def household(ctx):
    ctx["state"] = {
        "accounts": [
            {"id": "tax", "tax_status": "TAXABLE", "history_complete": True},
            {"id": "ira", "tax_status": "TAX_FREE", "history_complete": True},
        ],
        "securities": [
            {"id": "sec", "ticker": "VTI", "isin": "US9229087690", "cusip": "922908769"}
        ],
        "positions": [
            {
                "account_id": "tax",
                "security_id": "sec",
                "security": "VTI",
                "quantity": "15",
                "price": "100",
                "market_value": "1500",
                "as_of": "2026-10-08",
                "source_timestamp": "2026-10-08",
                "lot_state": "RESOLVED",
            }
        ],
        "lots": [
            {
                "id": "old",
                "account_id": "tax",
                "security_id": "sec",
                "security": "VTI",
                "acquisition_date": "2024-10-08",
                "quantity": "10",
                "remaining_quantity": "10",
                "cost_basis": "1100",
            },
            {
                "id": "new",
                "account_id": "tax",
                "security_id": "sec",
                "security": "VTI",
                "acquisition_date": "2026-01-01",
                "quantity": "5",
                "remaining_quantity": "5",
                "cost_basis": "400",
            },
        ],
        "activities": [],
        "cash_balances": [],
        "snapshots": [],
    }


@given(parsers.parse('tax data has "{gap}"'))
def gap(ctx, gap):
    state = ctx["state"]
    position = state["positions"][0]
    if gap == "unresolved lots":
        position["lot_state"] = "UNRESOLVED"
    elif gap == "excess lot quantity":
        position["quantity"] = "12"
    elif gap == "missing date":
        state["lots"][0]["acquisition_date"] = None
    elif gap == "unknown source date":
        position["source_timestamp"] = None
    elif gap == "missing tax status":
        state["accounts"][0].pop("tax_status")
    elif gap == "incomplete history":
        state["accounts"][1]["history_complete"] = False
    elif gap == "legacy source date":
        position.pop("source_timestamp")
    elif gap == "older source date":
        position["source_timestamp"] = "2026-01-01"
    elif gap == "tax free account":
        state["accounts"][0]["tax_status"] = "TAX_FREE"


@when("the household sale is estimated")
def estimate(ctx):
    ctx["result"] = analyze(
        ctx["state"],
        "tax",
        "VTI",
        "5",
        "100",
        "2026-10-08",
        rates={"ordinary_income_rate": ".30", "long_term_capital_gains_rate": ".15"},
    )


@then("the sale has insufficient data and null gains")
def insufficient(ctx):
    result = ctx["result"]
    assert result["status"] == "INSUFFICIENT_DATA"
    assert result["realized_gain_loss"] is None
    assert result["estimated_current_tax_effect"] is None
    assert result["tax_data_completeness"]["lot_inventory"] == "INSUFFICIENT_DATA"


@when("both specified lots are sold with six dollars of fees")
def fees(ctx):
    ctx["result"] = analyze(
        ctx["state"],
        "tax",
        "VTI",
        "15",
        "100",
        "2026-10-08",
        method="SPECIFIC",
        lot_ids=["old", "new"],
        fee="6",
        rates={"ordinary_income_rate": ".30", "long_term_capital_gains_rate": ".15"},
    )


@then("short term gain is ninety eight and long term loss is one hundred four")
def terms(ctx):
    result = ctx["result"]
    assert Decimal(result["realized_short_term_gain_loss"]) == 98
    assert Decimal(result["realized_long_term_gain_loss"]) == -104
    assert Decimal(result["estimated_current_tax_effect"]) == Decimal("13.8")
    assert sum((Decimal(lot["fee"]) for lot in result["selected_lots"]), Decimal(0)) == 6


@then("the estimate discloses fees and conservative tax assumptions")
def assumptions(ctx):
    assert ctx["result"]["sale_fee"] == "6"
    assert ctx["result"]["assumptions"]
    assert any("not guaranteed" in warning for warning in ctx["result"]["warnings"])


@then("known gains remain available with incomplete household history")
def incomplete_history(ctx):
    assert ctx["result"]["realized_gain_loss"] == "-50"
    assert ctx["result"]["tax_data_completeness"]["household_history"] == "INCOMPLETE"
    assert any("incomplete" in warning for warning in ctx["result"]["wash_sale"]["warnings"])


@given("an IRA purchase uses a bridged canonical security")
def ira(ctx):
    state = ctx["state"]
    state["securities"].append({"id": "ira-sec", "ticker": "OTHER", "cusip": "922908769"})
    state["activities"].append(
        {
            "id": "replacement",
            "type": "BUY",
            "account_id": "ira",
            "security_id": "ira-sec",
            "security": "OTHER",
            "quantity": "1",
            "date": "2026-09-28",
        }
    )


@then("the IRA appears in potential wash sale conflicts")
def conflict(ctx):
    assert ctx["result"]["potential_wash_sale_conflict"] is True
    assert ctx["result"]["wash_sale"]["affected_accounts"] == ["ira"]


@then("legacy freshness is explicitly unknown")
def legacy(ctx):
    assert ctx["result"]["tax_data_completeness"]["source_freshness"] == "LEGACY_UNKNOWN"
    assert ctx["result"]["realized_gain_loss"] == "-50"
    assert any("source" in warning.lower() for warning in ctx["result"]["warnings"])


@then("older source data is disclosed")
def stale(ctx):
    assert ctx["result"]["tax_data_completeness"]["source_freshness"] == "STALE"
    assert any("source" in warning.lower() for warning in ctx["result"]["warnings"])


@then("taxable short and long term gains are zero")
def taxfree(ctx):
    assert ctx["result"]["status"] == "NOT_TAXABLE"
    assert ctx["result"]["realized_short_term_gain_loss"] == "0"
    assert ctx["result"]["realized_long_term_gain_loss"] == "0"


class FundClient:
    def __init__(self):
        self.data = {
            "holdings": [
                {
                    "identifier": "ISIN:US0378331005",
                    "ticker": "AAPL",
                    "isin": "US0378331005",
                    "weight": ".20",
                }
            ],
            "source": "synthetic",
            "data_as_of": "2026-10-08",
            "weight_coverage": ".20",
            "warnings": [],
        }

    def holdings(self, ticker, refresh=False):
        return self.data


@given("direct shares and a partially reported fund holding the same security")
def lookthrough(ctx):
    ctx["client"] = FundClient()
    ctx["state"] = {
        "securities": [{"id": "apple", "ticker": "AAPL", "isin": "US0378331005"}],
        "cash_balances": [],
        "positions": [
            {
                "security_id": "apple",
                "security": "AAPL",
                "account_id": "tax",
                "market_value": "100",
                "asset_type": "STOCK",
            },
            {
                "security_id": "fund",
                "security": "FUND",
                "account_id": "ira",
                "market_value": "1000",
                "asset_type": "ETF",
            },
        ],
    }


@given("the fund security has a conflicting ISIN")
def identifiers(ctx):
    ctx["client"].data["holdings"][0].update(isin="US0000000001", identifier="ISIN:US0000000001")


@when("household look-through is computed")
def compute_exposure(ctx):
    ctx["result"] = exposure(ctx["state"], ctx["client"])


@then("direct and indirect exposure combine with strong identity confidence")
def merged(ctx):
    row = ctx["result"]["exposures"][0]
    assert Decimal(row["total_value"]) == 300
    assert row["identifier_confidence"] == "STRONG"
    assert len(row["contributions"]) == 2


@then("unresolved fund value and dated source coverage remain visible")
def coverage(ctx):
    assert Decimal(ctx["result"]["unknown_exposure_value"]) == 800
    source = ctx["result"]["fund_coverage"]["FUND"]
    assert Decimal(source["represented_weight"]) == Decimal(".20")
    assert source["source"] == "synthetic"
    assert source["data_as_of"] == "2026-10-08"


@then("two strong identities remain distinct")
def separate(ctx):
    assert len(ctx["result"]["exposures"]) == 2
    assert all(row["identifier_confidence"] == "STRONG" for row in ctx["result"]["exposures"])


class HistoryClient:
    ledger = None

    def history(self, ticker, refresh=False):
        return {
            "prices": [
                {"date": "2026-10-08", "adjusted_close": "99"},
                {"date": "2026-10-06", "adjusted_close": "100"},
                {"date": "2026-10-07", "adjusted_close": "110"},
            ],
            "warnings": [],
        }


@given("unsorted adjusted history and fifty percent household cash")
def historical(ctx):
    ctx["client"] = HistoryClient()
    ctx["state"] = {
        "positions": [{"security": "AAPL", "market_value": "100"}],
        "cash_balances": [{"amount": "100"}],
    }


@when("hypothetical historical risk is computed")
def historical_risk(ctx):
    ctx["result"] = risk(ctx["state"], ctx["client"])


@then("maximum drawdown is five percent with zero cash return disclosed")
def drawdown(ctx):
    assert ctx["result"]["maximum_drawdown"] == pytest.approx(-0.05)
    assert ctx["result"]["usable_period"]["start"] == "2026-10-06"
    assert ctx["result"]["mode"] == "HYPOTHETICAL_CURRENT_ALLOCATION"
    assert ctx["result"]["assumptions"]["cash_return"] == "0"
    assert ctx["result"]["assumptions"]["fees"] == "0"
    assert ctx["result"]["assumptions"]["modeled_taxes"] is False
