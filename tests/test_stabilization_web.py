"""Offline HTTP acceptance scenarios for snapshot stabilization."""

import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from pytest_bdd import given, scenarios, then, when

scenarios("features/stabilization_web.feature")


@pytest.fixture
def context(tmp_path):
    from invest.web import create_server

    server = create_server(tmp_path / "ledger.db", host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield {"base": f"http://127.0.0.1:{server.server_port}"}
    server.shutdown()
    server.server_close()
    thread.join()


def request(context, path, body=None):
    headers = {"Content-Type": "application/json", "Origin": context["base"]}
    req = Request(
        context["base"] + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers=headers,
    )
    try:
        with urlopen(req) as response:
            raw = response.read().decode()
            return response.status, json.loads(raw) if path.startswith("/api/") else raw
    except HTTPError as error:
        return error.code, json.loads(error.read())


def snapshot(quantity="10", source_timestamp="2026-10-08", tax_status="TAX_FREE"):
    return {
        "account": {
            "id": "retirement", "name": "Verified Roth IRA", "account_type": "Roth IRA",
            "tax_status": tax_status, "history_complete": True,
        },
        "positions": [{"security": "VTI", "quantity": quantity, "market_value": "1000"}],
        "source_timestamp": source_timestamp,
        "source_hash": f"synthetic-{quantity}-{source_timestamp}-{tax_status}",
    }


@given("a local inspection interface")
def interface(context):
    pass


@given("the inspection ledger has accepted dated retirement holdings")
def dated(context):
    assert request(context, "/api/apply", {"snapshot": snapshot(), "confirm": True})[0] == 200


@when("a changed snapshot with taxable metadata is reconciled through the interface")
def metadata(context):
    context["result"] = request(
        context, "/api/reconcile", {"snapshot": snapshot("11", tax_status="TAXABLE")}
    )[1]


@then("reconciliation explains that account configuration is preserved")
def preserved(context):
    assert context["result"]["account_metadata_discrepancies"]
    assert any("account update" in warning for warning in context["result"]["warnings"])


@when("a changed undated snapshot is reconciled through the interface")
def undated(context):
    context["incoming"] = snapshot("11", source_timestamp=None)
    context["result"] = request(context, "/api/reconcile", {"snapshot": context["incoming"]})[1]


@then("the interface reports an unknown source date requiring an override")
def unknown(context):
    assert context["result"]["source_date_status"] == "UNKNOWN_SOURCE_DATE"
    assert context["result"]["latest_known_source_date"] == "2026-10-08"
    assert context["result"]["override_required"] is True


@then("ordinary acceptance leaves the holdings unchanged")
def blocked(context):
    assert request(context, "/api/apply", {"snapshot": context["incoming"], "confirm": True})[0] == 409
    assert request(context, "/api/overview")[1]["state"]["positions"][0]["quantity"] == "10"
    assert request(context, "/api/apply", {
        "snapshot": context["incoming"], "confirm": True, "allow_older": True,
        "justification": "   ",
    })[0] == 400


@when("the update is accepted with an explained override")
def override(context):
    assert request(context, "/api/apply", {
        "snapshot": context["incoming"], "confirm": True, "allow_older": True,
        "justification": "Reviewed the undated synthetic statement manually",
    })[0] == 200


@then("the undated holdings are accepted without inventing a source date")
def accepted(context):
    overview = request(context, "/api/overview")[1]
    assert overview["state"]["positions"][0]["quantity"] == "11"
    assert overview["data_freshness"][0]["source_timestamp"] is None


@when("the import interface is inspected")
def inspect(context):
    context["page"] = request(context, "/")[1]
    context["script"] = request(context, "/app.js")[1]


@then("acceptance depends on reconciliation and a required override explanation")
def controls(context):
    assert "older or undated" in context["page"]
    assert "account configuration" in context["page"]
    assert "override_required" in context["script"]
    assert "justification" in context["script"]
    assert "updateSnapshotAcceptance" in context["script"]
