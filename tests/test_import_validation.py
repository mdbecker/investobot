import pytest
from pytest_bdd import given, scenarios, then, when

scenarios("features/import_validation.feature")


@pytest.fixture
def ctx(tmp_path):
    from invest.ledger import Ledger

    return {"ledger": Ledger(tmp_path / "db")}


def page(
    rows,
    header="<th>Symbol</th><th>Quantity</th><th>Market Value</th><th>Cost Basis</th><th>Acquisition Date</th><th>Asset Type</th>",
):
    return "<table><tr>" + header + "</tr>" + rows + "</table>"


def base_snapshot():
    from invest.parsers.generic import parse_html

    return parse_html(
        page(
            "<tr><td>VTI</td><td>10</td><td>1000</td><td>1200</td><td>2025-01-01</td><td>ETF</td></tr><tr><td>CASH</td><td></td><td>500</td><td></td><td></td><td></td></tr>"
        ),
        "example",
    )


@given("a synthetic lot table")
def lot_table(ctx):
    ctx["snapshot"] = base_snapshot()


@when("the lot table is parsed")
def parsed(ctx):
    pass


@then("acquisition dates and basis are preserved")
def basis(ctx):
    assert ctx["snapshot"]["lots"][0]["cost_basis"] == "1200"
    assert ctx["snapshot"]["lots"][0]["acquisition_date"] == "2025-01-01"


@given("a normalized snapshot with a negative quantity")
def negative(ctx):
    ctx["snapshot"] = base_snapshot()
    ctx["snapshot"]["positions"][0]["quantity"] = "-1"


@when("the snapshot is applied")
def applied(ctx):
    try:
        ctx["ledger"].apply(ctx["snapshot"])
    except Exception as exc:
        ctx["error"] = exc


@then("the application rejects it and leaves no accounts")
def rejected(ctx):
    assert "error" in ctx
    assert not ctx["ledger"].state()["accounts"]


@given("a synthetic derivative position table")
def derivative(ctx):
    from invest.parsers.generic import parse_html

    ctx["snapshot"] = parse_html(
        page("<tr><td>OPTION</td><td>1</td><td>500</td><td></td><td></td><td>OPTION</td></tr>"),
        "example",
    )


@when("the derivative table is parsed")
def derivative_parsed(ctx):
    pass


@then("the asset is OTHER with a warning")
def unsupported(ctx):
    assert ctx["snapshot"]["positions"][0]["asset_type"] == "OTHER"
    assert any("unsupported" in w for w in ctx["snapshot"]["warnings"])


@given("a normalized snapshot with a known account")
def known(ctx):
    ctx["snapshot"] = base_snapshot()
    ctx["ledger"].apply(ctx["snapshot"])


@when("I record a purchase and apply a later snapshot")
def activity(ctx):
    ctx["ledger"].record_activity(
        {
            "account_id": "example",
            "activity_id": "synthetic-buy",
            "type": "BUY",
            "security": "VTI",
            "quantity": "1",
            "price": "100",
            "date": "2026-10-08",
        },
        yes=True,
    )
    ctx["ledger"].apply(ctx["snapshot"])


@then("the activity history remains available")
def retained(ctx):
    assert len(ctx["ledger"].state()["activities"]) == 1


@given("a normalized snapshot with excess lot quantities")
def excess(ctx):
    ctx["snapshot"] = base_snapshot()
    ctx["snapshot"]["lots"][0]["remaining_quantity"] = "20"
    ctx["snapshot"]["lots"][0]["quantity"] = "20"


@given("a page without a cash table")
def missing_cash(ctx):
    ctx["snapshot"] = base_snapshot()
    ctx["snapshot"]["cash_known"] = False


@when("I apply that page and preview a buy")
def missing_buy(ctx):
    ctx["ledger"].apply(ctx["snapshot"])
    try:
        ctx["ledger"].record_activity(
            {
                "account_id": "example",
                "activity_id": "synthetic-buy",
            "type": "BUY",
                "security": "VTI",
                "quantity": "1",
                "price": "100",
                "date": "2026-10-08",
            }
        )
    except Exception as exc:
        ctx["error"] = exc


@then("the preview fails for unknown cash")
def missing_rejected(ctx):
    assert "Cash balance is unknown" in str(ctx["error"])
