import json
import threading
from http.client import HTTPConnection
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from pytest_bdd import given, scenarios, then, when

scenarios("features/web.feature")
HTML = "<p>PRIVATE_ACCOUNT_12345</p><table><tr><th>Symbol</th><th>Description</th><th>Quantity</th><th>Market Value</th><th>Price</th></tr><tr><td>VTI</td><td>Synthetic ETF</td><td>10</td><td>1000</td><td>100</td></tr></table>"


@pytest.fixture
def context(tmp_path):
    from invest.web import create_server

    server = create_server(tmp_path / "ledger.db", host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield {
        "server": server,
        "base": f"http://127.0.0.1:{server.server_port}",
        "path": tmp_path / "ledger.db",
    }
    server.shutdown()
    server.server_close()
    thread.join()


def request(context, path, body=None, origin=None):
    headers = {"Content-Type": "application/json"}
    if body is not None:
        headers["Origin"] = origin or context["base"]
    data = json.dumps(body).encode() if body is not None else None
    req = Request(context["base"] + path, data=data, headers=headers)
    try:
        with urlopen(req) as response:
            raw = response.read()
            return response.status, json.loads(raw) if path.startswith("/api") else raw.decode()
    except HTTPError as error:
        return error.code, json.loads(error.read())


@given("a local inspection server with an empty ledger")
def server(context):
    pass


@when("I inspect the portfolio summary")
def summary(context):
    context["summary"] = request(context, "/api/summary")[1]
    context["page"] = request(context, "/")[1]


@then("the summary reports zero and the page provides an import workflow")
def empty(context):
    assert context["summary"]["total_value"] == "0"
    assert "Preview import" in context["page"]
    assert "No accounts yet" in context["page"]


@when("I preview a synthetic account page")
def preview(context):
    context["preview"] = request(
        context,
        "/api/import",
        {
            "html": HTML,
            "account_id": "synthetic",
            "institution": "vanguard",
            "tax_status": "TAXABLE",
        },
    )


@then("the normalized preview is available and the ledger is unchanged")
def preview_only(context):
    assert context["preview"][0] == 200
    assert context["preview"][1]["positions"][0]["security"] == "VTI"
    assert request(context, "/api/summary")[1]["total_value"] == "0"


@when("I reconcile and explicitly apply the preview")
def apply(context):
    snapshot = context["preview"][1]
    assert request(context, "/api/reconcile", {"snapshot": snapshot})[1]["changes"]
    assert request(context, "/api/apply", {"snapshot": snapshot})[0] == 400
    assert request(context, "/api/apply", {"snapshot": snapshot, "confirm": True})[0] == 200


@then("the portfolio summary reflects the accepted snapshot")
def applied(context):
    summary = request(context, "/api/summary")[1]
    assert summary['total_value'] is None
    assert summary['known_value_subtotal'] == '1000'
    assert summary['status'] == 'PARTIAL'


@then("the raw page has not been stored")
def private(context):
    assert b"PRIVATE_ACCOUNT_12345" not in context["path"].read_bytes()


@when("a foreign origin posts an account page")
def foreign(context):
    context["response"] = request(
        context, "/api/import", {"html": HTML}, origin="https://foreign.example"
    )


@then("the request is rejected without importing it")
def forbidden(context):
    assert context["response"][0] == 403
    assert request(context, "/api/summary")[1]["total_value"] == "0"


@when("an oversized body is submitted")
def oversized(context, monkeypatch):
    connection = HTTPConnection("127.0.0.1", context["server"].server_port, timeout=5)
    sent = bytearray()
    original_send = connection.send

    def record_send(data):
        sent.extend(data)
        original_send(data)

    monkeypatch.setattr(connection, "send", record_send)
    try:
        connection.putrequest("POST", "/api/import")
        connection.putheader("Origin", context["base"])
        connection.putheader("Content-Type", "application/json")
        connection.putheader("Content-Length", "2100000")
        connection.endheaders()
        context["body_bytes_sent"] = len(sent.partition(b"\r\n\r\n")[2])
        # Keep the connection open: a body read would time out instead of returning 413.
        response = connection.getresponse()
        context["response"] = response.status, json.loads(response.read())
    finally:
        connection.close()


@then("the request is rejected before parsing")
def too_large(context):
    assert context["response"][0] == 413


@then("no oversized request body was transmitted")
def no_oversized_body(context):
    assert context["body_bytes_sent"] == 0


@when("I request tax lots analysis")
def tax_lots_request(context):
    context["response"] = request(
        context, "/api/analyze", {"tool": "tax_lots", "input": {"as_of": "2026-10-08"}}
    )


@then("the workbench returns structured lot analysis")
def lots_result(context):
    assert context["response"][0] == 200
    assert context["response"][1]["lots"] == []
    assert "warnings" in context["response"][1]


@when("I request an arbitrary execution tool")
def unknown_tool(context):
    context["response"] = request(
        context, "/api/analyze", {"tool": "shell", "input": {"command": "echo unsafe"}}
    )


@then("the workbench rejects the tool as invalid input")
def unknown_rejected(context):
    assert context["response"][0] == 400
    assert context["response"][1]["code"] == 1


@given("a synthetic accepted cash-funded account")
def cash_funded(context):
    snapshot = request(
        context,
        "/api/import",
        {
            "html": HTML
            + "<table><tr><th>Symbol</th><th>Market Value</th></tr><tr><td>CASH</td><td>500</td></tr></table>",
            "account_id": "synthetic",
        },
    )[1]
    assert request(context, "/api/apply", {"snapshot": snapshot, "confirm": True})[0] == 200
    context["before_bytes"] = context["path"].read_bytes()


@when("I simulate buying an existing security through the workbench")
def simulate_request(context):
    context["response"] = request(
        context,
        "/api/analyze",
        {
            "tool": "simulate",
            "input": {
                "actions": [
                    {
                        "type": "BUY",
                        "account_id": "synthetic",
                        "security": "VTI",
                        "quantity": "1",
                        "price": "100",
                        "date": "2026-10-08",
                        "fee": "0",
                    }
                ]
            },
        },
    )


@then("the simulation reports the changed cash")
def simulation_cash(context):
    assert context["response"][0] == 200
    assert context["response"][1]["after"]["cash"] == "400"


@then("the database bytes are unchanged")
def db_unchanged(context):
    assert context["before_bytes"] == context["path"].read_bytes()


@given("a household with unsupported mixed currencies")
def mixed_currency(context):
    from invest.ledger import Ledger

    ledger = Ledger(context["path"])
    for alias, currency in [("dollars", "USD"), ("euros", "EUR")]:
        ledger.apply(
            {
                "account": {"id": alias, "name": alias, "currency": currency},
                "positions": [],
                "cash": "100",
                "source_hash": "SYNTHETIC",
            }
        )
    ledger.connection.close()


@when("I inspect that household summary")
def mixed_summary(context):
    try:
        context["response"] = request(context, "/api/summary")
    except Exception as exc:
        context["connection_error"] = exc


@then("the API returns a JSON inconsistent-state error")
def mixed_error(context):
    assert "connection_error" not in context
    assert context["response"][0] == 409
    assert context["response"][1]["code"] == 3
