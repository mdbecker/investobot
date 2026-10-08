import pytest
from pytest_bdd import given, scenarios, then, when

from invest.tax import analyze

scenarios("features/tax_hardening.feature")


@pytest.fixture
def ctx():
    return {
        "state": {
            "accounts": [{"id": "account", "tax_status": "TAXABLE", "history_complete": False}],
            "securities": [{"id": "sec", "ticker": "VTI"}],
            "positions": [
                {
                    "account_id": "account",
                    "security_id": "sec",
                    "security": "VTI",
                    "quantity": "10",
                    "price": "90",
                    "market_value": "900",
                    "source_timestamp": "2026-10-08",
                }
            ],
            "lots": [],
            "activities": [],
            "cash_balances": [],
        }
    }


@given("a taxable holding whose lot has no acquisition date field")
def missing(ctx):
    ctx["state"]["lots"] = [
        {
            "id": "lot",
            "account_id": "account",
            "security_id": "sec",
            "security": "VTI",
            "quantity": "10",
            "remaining_quantity": "10",
            "cost_basis": "1000",
        }
    ]


@given("an IRA holding without lots and incomplete household history")
def retirement(ctx):
    ctx["state"]["accounts"][0]["tax_status"] = "TAX_FREE"
    ctx["state"]["positions"][0]["source_timestamp"] = None


@when("five shares are analyzed for a loss sale")
def sale(ctx):
    ctx["result"] = analyze(ctx["state"], "account", "VTI", "5", "90", "2026-10-08")


@then("tax analysis reports insufficient data without inventing gains")
def unavailable(ctx):
    assert ctx["result"]["status"] == "INSUFFICIENT_DATA"
    assert ctx["result"]["realized_gain_loss"] is None


@then("missing purchase dates are disclosed in wash-sale warnings")
def missing_date(ctx):
    assert any("unavailable date" in warning for warning in ctx["result"]["wash_sale"]["warnings"])


@then("the sale is non-taxable with lot inventory not required")
def exempt(ctx):
    assert ctx["result"]["status"] == "NOT_TAXABLE"
    assert ctx["result"]["realized_gain_loss"] == "0"
    assert ctx["result"]["tax_data_completeness"]["lot_inventory"] == "NOT_REQUIRED"


@then("no bogus unresolved-basis warning is reported")
def basis(ctx):
    assert not any("Lot/basis state unresolved" in warning for warning in ctx["result"]["warnings"])


@then("actual source freshness and household history limitations remain disclosed")
def honest(ctx):
    completeness = ctx["result"]["tax_data_completeness"]
    assert completeness["source_freshness"] == "UNKNOWN"
    assert completeness["household_history"] == "INCOMPLETE"
    assert any("Source timestamp unknown" in warning for warning in ctx["result"]["warnings"])
    assert "Household purchase history is incomplete" in ctx["result"]["wash_sale"]["warnings"]
