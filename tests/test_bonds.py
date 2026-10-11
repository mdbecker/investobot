from decimal import Decimal

import pytest
from pytest_bdd import given, scenarios, then, when

from invest.models import DomainError

scenarios("features/bonds.feature")


@pytest.fixture
def context():
    return {}


@given("a synthetic fixed-rate bond with known terms")
def fixed(context):
    context["terms"] = {
        "face_value": "1000",
        "coupon": "0.05",
        "maturity": "2031-01-15",
        "issue_date": "2021-01-15",
        "settlement_date": "2026-10-08",
        "frequency": 2,
        "clean_price": "98",
        "day_count": "ACTUAL_ACTUAL_BOND",
    }


@given("a supplied call date and redemption price")
def call(context):
    context["terms"]["call_schedule"] = [{"date": "2028-01-15", "price": "100"}]


@given("a bond without a known coupon or price")
def missing(context):
    context["terms"] = {"maturity": "2031-01-15", "settlement_date": "2026-10-08"}


@given("a bond with an invalid payment frequency")
def invalid(context):
    fixed(context)
    context["terms"]["frequency"] = 7


@when("I analyze the bond")
def analyze(context):
    from invest.bonds import analyze

    try:
        context["result"] = analyze(context["terms"])
    except DomainError as error:
        context["error"] = error


@then("yield accrued interest dirty price duration and convexity are calculable")
def metrics(context):
    result = context["result"]
    assert result["status"] == "CALCULATED"
    assert Decimal("0.05") < Decimal(result["yield_to_maturity"]) < Decimal("0.06")
    assert Decimal(result["accrued_interest"]) > 0
    assert Decimal(result["dirty_price"]) > Decimal("98")
    assert Decimal(result["modified_duration"]) > 0
    assert Decimal(result["convexity"]) > 0


@then("calculation conventions are disclosed")
def conventions(context):
    conventions = context["result"]["conventions"]
    assert conventions["day_count"] == "ACTUAL_ACTUAL_BOND"
    assert conventions["clean_price_units"] == "per 100 face value"
    assert conventions["calendar"] == "NullCalendar"


@then("callable bond measures are unavailable")
def worst(context):
    result = context["result"]
    assert result['status'] == 'UNAVAILABLE'
    assert result['issues'][0]['code'] == 'UNSUPPORTED_BOND_STRUCTURE'
    assert 'yield_to_worst' not in result and 'yield_to_maturity' not in result


@then("bond analysis reports insufficient data without guessed metrics")
def insufficient(context):
    assert context["result"]["status"] == "INSUFFICIENT_DATA"
    assert context["result"]["warnings"]
    assert "yield_to_maturity" not in context["result"]


@then("invalid bond input is rejected")
def rejected(context):
    assert context["error"].code == 1


@given("an issue date that creates an irregular coupon stub")
def irregular(context):
    context["terms"]["issue_date"] = "2021-03-10"
