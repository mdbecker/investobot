import copy
import json
from decimal import Decimal

import pytest
from pytest_bdd import given, scenarios, then, when

from invest.ledger import Ledger
from invest.models import DomainError

scenarios("features/household_targets.feature")


@pytest.fixture
def ctx(tmp_path):
    ledger = Ledger(tmp_path / "ledger.db")
    yield {"ledger": ledger}
    ledger.connection.close()


@given("an accepted household holds two canonical securities and cash")
def household(ctx):
    ledger = ctx["ledger"]
    ledger.apply({
        "account": {"id": "ira", "name": "IRA", "tax_status": "TAX_DEFERRED"},
        "positions": [
            {"security": "AAA", "asset_type": "ETF", "quantity": "6", "price": "100",
             "market_value": "600", "as_of": "2026-10-08", 'displayed_price_precision': 0, 'displayed_market_value_precision': 0},
            {"security": "BBB", "asset_type": "ETF", "quantity": "3", "price": "100",
             "market_value": "300", "as_of": "2026-10-08", 'displayed_price_precision': 0, 'displayed_market_value_precision': 0},
        ],
        "cash": "100", "cash_known": True, "source_hash": "synthetic-target-household",
        "source_timestamp": "2026-10-08", "positions_complete": True,
    })
    ctx["aaa"] = ledger.resolve("AAA")["id"]
    ctx["bbb"] = ledger.resolve("BBB")["id"]
    ctx["before"] = copy.deepcopy(ledger.state())
    ctx["payload"] = {
        "name": "Balanced", "description": "Synthetic comparison",
        "target_allocations": {ctx["aaa"]: "0.5", ctx["bbb"]: "0.4", "CASH": "0.1"},
        "planning_constraints": {
            "eligible_accounts": ["ira"],
            "permitted_securities": {"ira": [ctx["aaa"], ctx["bbb"]]},
            "cash_minimums": {"ira": "50"},
        },
    }


@when("a balanced target is saved")
def balanced(ctx):
    from invest.targets import save

    ctx["target"] = save(ctx["ledger"], ctx["payload"])


@then("its security weights and account constraints are retained")
def retained(ctx):
    target = ctx["target"]
    assert target["version"] == 1
    assert target["status"] == "DRAFT"
    assert target["version_id"]
    assert target["created_at"] and target["updated_at"]
    assert Decimal(target["target_allocations"][ctx["aaa"]]) == Decimal("0.5")
    assert target["planning_constraints"]["eligible_accounts"] == ["ira"]
    assert Decimal(target["planning_constraints"]["cash_minimums"]["ira"]) == Decimal("50")


@then("accepted portfolio state remains unchanged")
def unchanged(ctx):
    assert ctx["ledger"].state() == ctx["before"]


@when("a target with incomplete weights is saved")
def invalid_weights(ctx):
    from invest.targets import save

    payload = copy.deepcopy(ctx["payload"])
    payload["target_allocations"][ctx["aaa"]] = "0.3"
    with pytest.raises((DomainError, ValueError)) as error:
        save(ctx["ledger"], payload)
    ctx["error"] = error.value


@then("the target request fails without persistent changes")
def no_target(ctx):
    from invest.targets import list_targets

    assert ctx["error"]
    assert list_targets(ctx["ledger"])["targets"] == []
    assert ctx["ledger"].state() == ctx["before"]


@when("two differently named targets are saved")
def two(ctx):
    from invest.targets import save

    ctx["first"] = save(ctx["ledger"], ctx["payload"])
    payload = dict(ctx["payload"], name="Conservative")
    ctx["second"] = save(ctx["ledger"], payload)


@then("both draft targets remain available")
def both(ctx):
    from invest.targets import list_targets

    targets = list_targets(ctx["ledger"])["targets"]
    assert {t["name"] for t in targets} == {"Balanced", "Conservative"}
    assert all(t["status"] == "DRAFT" for t in targets)


@when("its allocation is edited")
def edit(ctx):
    from invest.targets import save

    payload = dict(ctx["payload"], id=ctx["target"]["id"], target_allocations={
        ctx["aaa"]: "0.2", ctx["bbb"]: "0.7", "CASH": "0.1",
    })
    ctx["edited"] = save(ctx["ledger"], payload)


@then("the original allocation remains available as version one")
def original(ctx):
    from invest.targets import show

    first = show(ctx["ledger"], ctx["target"]["id"], version=1)
    assert first["version_id"] == ctx["target"]["version_id"]
    assert Decimal(first["target_allocations"][ctx["aaa"]]) == Decimal("0.5")


@then("the latest target is version two")
def latest(ctx):
    from invest.targets import show

    target = show(ctx["ledger"], ctx["target"]["id"])
    assert target["version"] == 2
    assert Decimal(target["target_allocations"][ctx["aaa"]]) == Decimal("0.2")
    assert len(target["versions"]) == 2


@when("each target is activated in sequence")
def activate_two(ctx):
    from invest.targets import activate

    activate(ctx["ledger"], ctx["first"]["id"])
    activate(ctx["ledger"], ctx["second"]["id"])


@then("only the second target is active")
def active(ctx):
    from invest.targets import list_targets

    targets = list_targets(ctx["ledger"])["targets"]
    assert [t["id"] for t in targets if t["status"] == "ACTIVE"] == [ctx["second"]["id"]]


@when("its household allocation differences are requested")
def differences(ctx):
    from invest.targets import diff

    try:
        ctx["diff"] = diff(ctx["ledger"], ctx["target"]["id"])
    except DomainError as error:
        ctx["error"] = error


@then("current and target dollars and drift are exact")
def exact(ctx):
    result = ctx["diff"]
    rows = {row["security_id"]: row for row in result["allocations"]}
    assert Decimal(result["total_value"]) == Decimal("1000")
    assert Decimal(rows[ctx["aaa"]]["current_value"]) == Decimal("600")
    assert Decimal(rows[ctx["aaa"]]["target_value"]) == Decimal("500")
    assert Decimal(rows[ctx["aaa"]]["difference_value"]) == Decimal("-100")
    assert Decimal(rows[ctx["aaa"]]["current_weight"]) == Decimal("0.6")
    assert Decimal(rows[ctx["aaa"]]["difference_weight"]) == Decimal("-0.1")
    assert Decimal(rows["CASH"]["difference_value"]) == 0
    json.dumps(result)


@when("a target restricts the retirement account to one permitted security")
def restricted(ctx):
    from invest.targets import save

    payload = copy.deepcopy(ctx["payload"])
    payload["planning_constraints"]["permitted_securities"] = {"ira": [ctx["bbb"]]}
    ctx["target"] = save(ctx["ledger"], payload)


@then("the saved constraints preserve that restriction")
def restriction(ctx):
    assert ctx["target"]["planning_constraints"]["permitted_securities"] == {"ira": [ctx["bbb"]]}


@then("missing account permissions remain unknown")
def unknown_permission(ctx):
    assert "unloaded-account" not in ctx["target"]["planning_constraints"]["permitted_securities"]


@when("that target is archived")
def archive(ctx):
    from invest.targets import archive

    archive(ctx["ledger"], ctx["target"]["id"])


@then("its latest status is archived and historical allocation survives")
def archived(ctx):
    from invest.targets import show

    target = show(ctx["ledger"], ctx["target"]["id"])
    assert target["status"] == "ARCHIVED"
    assert target["version_id"] == ctx["target"]["version_id"]
    assert target["target_allocations"] == ctx["target"]["target_allocations"]
    assert len(ctx["ledger"].rows("target_versions")) == 1


@when("a target names an unregistered security")
def missing_security(ctx):
    from invest.targets import save

    payload = dict(ctx["payload"], target_allocations={"INVENTED": "1"})
    with pytest.raises(DomainError) as error:
        save(ctx["ledger"], payload)
    ctx["error"] = error.value


@when("the household has incompatible currencies")
def currencies(ctx):
    ledger = ctx["ledger"]
    with ledger.connection:
        ledger.put("accounts", "eur", {"id": "eur", "name": "Euro", "currency": "EUR",
                                       "tax_status": "TAXABLE"})


@then("the difference request fails with inconsistent state")
def currency_error(ctx):
    assert ctx["error"].code == 3
