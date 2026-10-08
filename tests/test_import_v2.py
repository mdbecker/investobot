from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from invest.models import DomainError
from invest.parsers.generic import parse_html

scenarios("features/import_v2.feature")


@pytest.fixture
def ctx():
    return {}


def page(rows):
    headers = (
        "Symbol", "Quantity", "Price", "Market Value", "Cost Basis",
        "Acquisition Date", "Asset Type", "CUSIP", "ISIN",
    )
    return "<table><tr>" + "".join(f"<th>{h}</th>" for h in headers) + "</tr>" + "".join(
        "<tr>" + "".join(f"<td>{v}</td>" for v in row) + "</tr>" for row in rows
    ) + "</table>"


def rows():
    return [
        ["VTI", "2", "100", "200", "140", "2024-01-01", "ETF", "922908769", ""],
        ["VTI", "3", "100", "300", "240", "2025-01-01", "ETF", "922908769", "US9229087690"],
    ]


@given("two distinct lots of the same ETF")
def distinct(ctx):
    ctx["html"] = page(rows())


@given("two lots with one missing basis")
def unknown(ctx):
    entries = rows()
    entries[1][4] = ""
    ctx["html"] = page(entries)


@given(parsers.parse("an account page with {problem}"))
def contradictory(ctx, problem):
    entries = rows()
    if problem == "duplicate position rows":
        entries[0][5] = ""
        entries[1] = list(entries[0])
    elif problem == "duplicate lot rows":
        entries[1] = list(entries[0])
    elif problem == "conflicting security identities":
        entries[1][7] = "111111111"
    elif problem == "conflicting lot prices":
        entries[1][2] = "101"
    elif problem == "mixed summary and lot rows":
        entries[0][5] = ""
    else:
        raise AssertionError(problem)
    ctx["html"] = page(entries)


@given("an account page without a supported holdings table")
def unsupported(ctx):
    ctx["html"] = "<table><tr><th>Notice</th></tr><tr><td>Statement available</td></tr></table>"


def normalize(ctx, **kwargs):
    try:
        ctx["snapshot"] = parse_html(ctx["html"], "synthetic", **kwargs)
    except DomainError as exc:
        ctx["error"] = exc


@when("the account page is normalized")
def normalized(ctx):
    normalize(ctx)


@when("the complete account page is normalized with its source date")
def complete(ctx):
    normalize(ctx, positions_complete=True, lots_complete=True, as_of="2026-10-01")


@then("position totals equal the sum of both lots")
def totals(ctx):
    snapshot = ctx["snapshot"]
    assert len(snapshot["positions"]) == 1
    assert len(snapshot["lots"]) == 2
    position = snapshot["positions"][0]
    assert Decimal(position["quantity"]) == 5
    assert Decimal(position["market_value"]) == 500
    assert Decimal(position["cost_basis"]) == 380


@then("identifiers are preserved on positions and lots")
def identities(ctx):
    snapshot = ctx["snapshot"]
    assert snapshot["positions"][0]["cusip"] == "922908769"
    assert snapshot["positions"][0]["isin"] == "US9229087690"
    assert all(lot["cusip"] == "922908769" for lot in snapshot["lots"])


@then("aggregate basis remains unknown")
def unknown_basis(ctx):
    assert ctx["snapshot"]["positions"][0]["cost_basis"] is None
    assert any("basis" in w.lower() for w in ctx["snapshot"]["warnings"])


@then("normalization fails with a source conflict")
def conflict(ctx):
    assert "snapshot" not in ctx
    assert isinstance(ctx.get("error"), DomainError)
    assert ctx["error"].code == 2


@then("normalization fails without producing a snapshot")
def rejected(ctx):
    assert "snapshot" not in ctx
    assert isinstance(ctx.get("error"), DomainError)


@then("position and lot coverage are incomplete booleans")
def incomplete(ctx):
    assert ctx["snapshot"]["positions_complete"] is False
    assert ctx["snapshot"]["lots_complete"] is False


@then("the source timestamp is unknown")
def undated(ctx):
    assert ctx["snapshot"]["source_timestamp"] is None


@then("position and lot coverage are complete booleans")
def full_coverage(ctx):
    assert ctx["snapshot"]["positions_complete"] is True
    assert ctx["snapshot"]["lots_complete"] is True


@then("the supplied source date is distinct from import time")
def dated(ctx):
    assert ctx["snapshot"]["source_timestamp"] == "2026-10-01"
    assert ctx["snapshot"]["imported_at"] != "2026-10-01"
