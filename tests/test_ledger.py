from decimal import Decimal

import pytest
from pytest_bdd import given, scenarios, then, when

scenarios("features/ledger.feature")
HTML = "<html><p>PRIVATE_ACCOUNT_12345</p><table><tr><th>Symbol</th><th>Description</th><th>Quantity</th><th>Price</th><th>Market Value</th></tr><tr><td>VTI</td><td>Total ETF</td><td>10</td><td>100</td><td>1000</td></tr><tr><td>CASH</td><td>Cash</td><td></td><td></td><td>500</td></tr></table></html>"


@pytest.fixture
def context(tmp_path):
    from invest.ledger import Ledger

    return {"ledger": Ledger(tmp_path / "ledger.db"), "path": tmp_path / "ledger.db"}


@given("a synthetic account page with positions and cash")
def page(context):
    context["html"] = HTML


@when("I import the page")
def parse(context):
    from invest.parsers.generic import parse_html

    context["snapshot"] = parse_html(
        context["html"], account_id="synthetic", institution="vanguard"
    )


@then("the ledger remains empty")
def empty(context):
    assert context["ledger"].summary()["total_value"] == "0"


@when("I explicitly apply the snapshot")
def apply(context):
    context["ledger"].apply(context["snapshot"])


@then("the summary contains the imported values")
def values(context):
    assert Decimal(context["ledger"].summary()["total_value"]) == 1500


@then("repeated reconciliation has no differences")
def unchanged(context):
    assert context["ledger"].reconcile(context["snapshot"])["changes"] == []


@then("the raw page is not persisted")
def private(context):
    assert b"PRIVATE_ACCOUNT_12345" not in context["path"].read_bytes()


@given("an applied synthetic account")
def existing(context):
    page(context)
    parse(context)
    apply(context)


@when("I preview a manual buy")
def preview(context):
    context["activity"] = {
        "account_id": "synthetic",
        "security": "VTI",
        "type": "BUY",
        "quantity": "2",
        "price": "100",
        "date": "2026-10-08",
        "fee": "0",
    }
    context["ledger"].record_activity(context["activity"], yes=False)


@then("cash is unchanged")
def no_change(context):
    assert context["ledger"].summary()["cash"] == "500"


@when("I confirm the manual buy")
def confirm(context):
    context["ledger"].record_activity(context["activity"], yes=True)


@then("cash and quantity reflect the buy")
def bought(context):
    assert context["ledger"].summary()["cash"] == "300"
    assert context["ledger"].state()["positions"][0]["quantity"] == "12"
    assert len(context["ledger"].state()["activities"]) == 1


@when("I reconcile a reduced share quantity")
def reduced(context):
    context["snapshot"]["positions"][0]["quantity"] = "8"
    context["diff"] = context["ledger"].reconcile(context["snapshot"])


@then("a quantity difference is reported")
def diff(context):
    assert any(c["kind"] == "quantity" for c in context["diff"]["changes"])


@then("no sale is inferred")
def no_sale(context):
    assert context["ledger"].state()["activities"] == []
