import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from invest.models import DomainError
from invest.parsers.generic import parse_html

scenarios("features/import_hardening.feature")


@pytest.fixture
def ctx():
    return {"options": {}}


def page(row, headers=None):
    headers = headers or ["Symbol", "Quantity", "Price", "Market Value", "Cost Basis", "Acquisition Date"]
    return (
        "<table><tr>" + "".join(f"<th>{cell}</th>" for cell in headers) + "</tr><tr>"
        + "".join(f"<td>{cell}</td>" for cell in row) + "</tr></table>"
    )


@given("a page repeating the same cash row in two tables")
def cash(ctx):
    ctx["html"] = page(["CASH", "", "", "500", "", ""]) * 2


@given(parsers.parse("a complete page containing {problem}"))
def omitted(ctx, problem):
    ctx["options"] = {"positions_complete": True, "lots_complete": True}
    lot = ["VTI", "2", "100", "200", "140", "2024-01-01"]
    if problem == "malformed cash value":
        ctx["html"] = page(lot) + page(["CASH", "", "", "unreadable", "", ""])
        return
    if problem == "invalid acquisition date":
        lot[5] = "not-a-date"
    elif problem == "missing acquisition date":
        lot[5] = ""
    elif problem == "missing lot basis":
        lot[4] = ""
    else:
        raise AssertionError(problem)
    ctx["html"] = page(lot)


@given("a page with two market value columns")
def columns(ctx):
    ctx["html"] = page(["VTI", "2", "200", "300"], ["Symbol", "Quantity", "Market Value", "Value"])


@when("I normalize the hardened import")
def normalized(ctx):
    try:
        ctx["snapshot"] = parse_html(ctx["html"], "synthetic", **ctx["options"])
    except DomainError as exc:
        ctx["error"] = exc


@then("the contradictory source is rejected")
def rejected(ctx):
    assert "snapshot" not in ctx
    assert isinstance(ctx.get("error"), DomainError)
    assert ctx["error"].code == 2


@given("a known lot imported at two valuations")
def valued(ctx):
    ctx["old"] = parse_html(page(["VTI", "2", "100", "200", "140", "2024-01-01"]), "synthetic")
    ctx["new"] = parse_html(page(["VTI", "2", "110", "220", "140", "2024-01-01"]), "synthetic")


@when("I compare the normalized lot identities")
def compared(ctx):
    ctx["ids"] = [ctx[key]["lots"][0]["id"] for key in ("old", "new")]


@then("the lot identity is unchanged")
def stable(ctx):
    assert ctx["ids"][0] == ctx["ids"][1]
