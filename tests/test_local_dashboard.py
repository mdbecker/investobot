import copy
import json
import threading
from decimal import Decimal
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from bs4 import BeautifulSoup
from pytest_bdd import given, scenarios, then, when

from invest.ledger import Ledger
from invest.plan_storage import load_plan, summaries

scenarios("features/local_dashboard.feature")


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    from invest.web import create_server

    monkeypatch.setenv("INVEST_FIXTURES", "/app/tests/fixtures/fmp-synthetic.json")
    monkeypatch.setenv("INVEST_CONFIG", str(tmp_path / "config.toml"))
    monkeypatch.setenv("INVEST_PROMPTS_DIR", str(tmp_path / "prompts"))
    server = create_server(tmp_path / "ledger.db", host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield {"base": f"http://127.0.0.1:{server.server_port}", "path": tmp_path / "ledger.db"}
    server.shutdown()
    server.server_close()
    thread.join()


def request(ctx, path, payload=None):
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        headers["Origin"] = ctx["base"]
    req = Request(ctx["base"] + path, headers=headers,
                  data=json.dumps(payload).encode() if payload is not None else None)
    try:
        with urlopen(req) as response:
            raw = response.read().decode()
            content_type = response.headers.get("Content-Type", "")
            return response.status, json.loads(raw) if "application/json" in content_type else raw
    except HTTPError as error:
        return error.code, json.loads(error.read())


@when("the investor opens the local dashboard")
def opens(ctx):
    code, page = request(ctx, "/")
    assert code == 200
    ctx["page"] = BeautifulSoup(page, "html.parser")


@then("navigation offers Overview Targets Plans Prompt Library and Import & Reconcile")
def navigation(ctx):
    primary = ctx["page"].select("#primary-nav a")
    assert [(a.get("href"), a.get_text(strip=True)) for a in primary] == [
        ("#overview", "Overview"), ("#targets", "Targets"), ("#plans", "Plans"),
        ("#prompts", "Prompt Library"), ("#import", "Import & Reconcile"),
    ]


@then("the dashboard provides editable targets and manual-review plan controls")
def controls(ctx):
    page = ctx["page"]
    assert page.select_one("#target-input") is not None
    assert page.select_one("#target-save").get_text(strip=True) == "Save target version"
    assert page.select_one("#plan-generate").get_text(strip=True) == "Generate review plan"
    assert page.select_one("#plan-compare") is not None
    assert page.select_one("#prompt-copy").get_text(strip=True) == "Copy full prompt"
    assert "trades are never executed automatically" in page.get_text(" ", strip=True).lower()


@then("snapshot completeness is unchecked by default")
def coverage(ctx):
    for name in ("positions_complete", "lots_complete"):
        checkbox = ctx["page"].select_one(f'input[name="{name}"]')
        assert checkbox is not None and checkbox.get("type") == "checkbox"
        assert not checkbox.has_attr("checked")


@then("the activity example requires a stable activity ID")
def activity_id(ctx):
    example = json.loads(ctx["page"].select_one("#activity-input")["placeholder"])
    assert example["activity_id"]


@then("unsupported transfers are identified for manual review")
def transfers(ctx):
    text = ctx["page"].select_one("#activity").get_text(" ", strip=True).lower()
    assert "cross-account" in text and "unsupported" in text and "review" in text


@given("an accepted synthetic retirement household")
def household(ctx):
    ledger = Ledger(ctx["path"])
    ledger.apply({
        "account": {"id": "ira", "name": "Synthetic IRA", "tax_status": "TAX_FREE",
                    "history_complete": True},
        "positions": [
            {"security": "AAA", "asset_type": "STOCK", "quantity": "10", "price": "100",
             "market_value": "1000", "cost_basis": "500", "as_of": "2026-10-08", 'displayed_price_precision': 0, 'displayed_market_value_precision': 0},
            {"security": "BBB", "asset_type": "STOCK", "quantity": "0", "price": "100",
             "market_value": "0", "as_of": "2026-10-08", 'displayed_price_precision': 0, 'displayed_market_value_precision': 0},
        ],
        "lots": [{"id": "ira-old", "security": "AAA", "quantity": "10",
                  "remaining_quantity": "10", "cost_basis": "500",
                  "acquisition_date": "2024-01-01"}],
        "cash": "0", "source_hash": "synthetic-dashboard", "source_timestamp": "2026-10-08",
        "positions_complete": True, "lots_complete": True,
    })
    ctx["aaa"], ctx["bbb"] = ledger.resolve("AAA")["id"], ledger.resolve("BBB")["id"]
    ctx["before"] = copy.deepcopy(ledger.state())
    ctx["target_payload"] = {
        "name": "Replacement", "target_allocations": {ctx["aaa"]: "0", ctx["bbb"]: "1"},
        "planning_constraints": {"eligible_accounts": ["ira"],
                                 "permitted_securities": {"ira": [ctx["aaa"], ctx["bbb"]]}},
    }
    ledger.connection.close()


@when("a target is saved and explicitly activated through the dashboard API")
def activate(ctx):
    code, target = request(ctx, "/api/targets/save", {"target": ctx["target_payload"]})
    assert code == 200
    ctx["target"] = target
    code, _ = request(ctx, "/api/targets/activate", {"target_id": target["id"], "confirm": True})
    assert code == 200
    code, ctx["overview"] = request(ctx, "/api/overview")
    assert code == 200


@then("overview shows the active target and exact accepted value and target drift")
def overview(ctx):
    overview = ctx["overview"]
    assert Decimal(overview["summary"]["total_value"]) == 1000
    assert overview["active_target"]["id"] == ctx["target"]["id"]
    rows = {r["security_id"]: r for r in overview["target_diff"]["allocations"]}
    assert Decimal(rows[ctx["bbb"]]["difference_value"]) == 1000
    assert "exposure" in overview and "tax_lots" in overview and "data_freshness" in overview


@then("the saved target can be edited and its historical version inspected")
def edit(ctx):
    payload = dict(ctx["target_payload"], id=ctx["target"]["id"], target_allocations={
        ctx["aaa"]: "0.5", ctx["bbb"]: "0.5",
    })
    code, target = request(ctx, "/api/targets/save", {"target": payload})
    assert code == 200 and target["version"] == 2
    code, original = request(ctx, f'/api/targets/{target["id"]}?version=1')
    assert code == 200 and Decimal(original["target_allocations"][ctx["bbb"]]) == 1


@then("accepted holdings are unchanged")
def unchanged(ctx):
    ledger = Ledger(ctx["path"])
    assert ledger.state() == ctx["before"]
    ledger.connection.close()


@when("two alternative plans are generated through the dashboard API")
def plans(ctx):
    ctx["plans"] = []
    for weight in ("1", "0.5"):
        payload = dict(ctx["target_payload"], target_allocations={
            ctx["aaa"]: str(Decimal("1") - Decimal(weight)), ctx["bbb"]: weight,
        })
        code, target = request(ctx, "/api/targets/save", {"target": payload})
        assert code == 200
        code, plan = request(ctx, "/api/plans/generate", {
            "target_id": target["id"], "as_of": "2026-10-08",
        })
        assert code == 200
        ctx["plans"].append(plan["plan"])


@then("the plan views expose manual trades tax values drift and common assumptions")
def plans_view(ctx):
    code, comparison = request(ctx, "/api/plans/compare", {
        "plan_ids": [p["id"] for p in ctx["plans"]],
    })
    assert code == 200 and comparison["same_source_snapshot"] is True
    assert comparison["same_price_assumptions"] is True
    code, view = request(ctx, f'/api/plans/{ctx["plans"][0]["id"]}')
    assert code == 200
    assert [a["type"] for a in view["proposed_actions"]] == ["SELL", "BUY"]
    assert Decimal(view["tax_analysis"]["realized_gain_loss"]) == 0
    assert view["remaining_target_drift"] and view["assumptions"]


@then("the downloaded report matches the persisted plan")
def download(ctx):
    code, report = request(ctx, f'/api/plans/{ctx["plans"][0]["id"]}/report?format=json')
    assert code == 200 and report["id"] == ctx["plans"][0]["id"]
    ledger = Ledger(ctx["path"])
    try:
        assert report == next(p for p in [load_plan(ledger, row['id']) for row in summaries(ledger)] if p['id'] == report['id'])
    finally:
        ledger.connection.close()


@when("confirmed interest changes the source portfolio")
def interest(ctx):
    code, _ = request(ctx, "/api/activity", {"activity": {
        "activity_id": "dashboard-interest", "type": "INTEREST", "account_id": "ira",
        "amount": "1", "date": "2026-10-08",
    }, "confirm": True})
    assert code == 200


@then("the dashboard API displays stale plan status")
def stale_api(ctx):
    code, plan = request(ctx, f'/api/plans/{ctx["plans"][0]["id"]}')
    assert code == 200 and plan["status"] == "STALE"


@then("the dashboard includes a visible stale status treatment")
def stale_style(ctx):
    code, css = request(ctx, "/style.css")
    assert code == 200 and ".status-stale" in css
