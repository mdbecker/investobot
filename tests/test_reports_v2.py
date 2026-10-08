import copy
import hashlib
import json

import pytest
from pytest_bdd import given, scenarios, then, when

from invest.models import DomainError

scenarios("features/reports_v2.feature")


@pytest.fixture
def ctx(tmp_path):
    return {"directory": tmp_path}


@given("an immutable synthetic trade plan with unresolved tax information")
def plan(ctx):
    ctx["plan"] = {
        "id": "plan-1",
        "name": "Diversify",
        "target_version_id": "target:2",
        "target": {
            "name": "Balanced",
            "description": "Reduce concentration",
            "version": 2,
            "version_id": "target:2",
            "target_allocations": [],
            "planning_constraints": {},
        },
        "source_snapshot_ids": ["snapshot-1"],
        "source_state_hash": "abc",
        "source_snapshot_dates": {"tax": "2026-10-08", "ira": None},
        "source_state": {
            "accounts": [{"id": "tax", "name": "Taxable"}],
            "securities": [{"id": "apple", "ticker": "AAPL", "name": "Apple"}],
        },
        "created_at": "2026-10-08T10:00:00Z",
        "as_of": "2026-10-08",
        "market_data_as_of": {"apple": "2026-10-08"},
        "assumptions": {
            "prices": {
                "apple": {
                    "price": "100",
                    "as_of": "2026-10-08",
                    "currency": "USD",
                    "source": "ledger",
                }
            },
            "tax_rates": None,
            "planning_constraints": {"long_term_gain_budget": "100"},
            "algorithm": "deterministic heuristic",
        },
        "proposed_actions": [
            {
                "type": "SELL",
                "account_id": "tax",
                "security": "apple",
                "quantity": "2",
                "price": "100",
                "date": "2026-10-08",
                "fee": "1",
                "lot_allocations": [{"lot_id": "old", "quantity": "2"}],
                "lot_ids": ["old"],
                "method": "SPECIFIC",
            }
        ],
        "tax_analysis": {
            "realized_gain_loss": "-21",
            "short_term_gain_loss": "0",
            "long_term_gain_loss": "-21",
            "estimated_tax_effect": None,
            "analyses": [
                {
                    "account_id": "tax",
                    "security_id": "apple",
                    "wash_sale": {
                        "status": "INSUFFICIENT_DATA",
                        "conflicts": [],
                        "warnings": ["Outside accounts unknown"],
                    },
                }
            ],
        },
        "exposure_analysis": {
            "before": {"unknown_exposure_value": "30"},
            "after": {},
            "changes": [],
        },
        "current_allocation": {
            "allocations": [
                {
                    "security_id": "apple",
                    "current_value": "1000",
                    "target_value": "800",
                    "current_weight": ".50",
                    "target_weight": ".40",
                    "difference_value": "-200",
                    "difference_weight": "-.10",
                }
            ]
        },
        "proposed_allocation": {
            "allocations": [
                {
                    "security_id": "apple",
                    "current_value": "800",
                    "target_value": "800",
                    "current_weight": ".40",
                    "target_weight": ".40",
                    "difference_value": "0",
                    "difference_weight": "0",
                }
            ]
        },
        "remaining_target_drift": [
            {"security_id": "apple", "difference_value": "0", "difference_weight": "0"}
        ],
        "cash_before": {"tax": "10"},
        "cash_after": {"tax": "209"},
        "warnings": ["Unknown household history", "Restricted account requires review"],
        "status": "REVIEW_REQUIRED",
    }
    ctx["original"] = copy.deepcopy(ctx["plan"])


@when("its Markdown report is exported")
def markdown(ctx):
    from invest.reports import export

    ctx["output"] = ctx["directory"] / "report.md"
    ctx["confirmation"] = export(ctx["plan"], ctx["output"])
    ctx["rendered"] = ctx["output"].read_text()


@when("its JSON report is exported")
def json_export(ctx):
    from invest.reports import export

    ctx["output"] = ctx["directory"] / "report.json"
    ctx["confirmation"] = export(ctx["plan"], ctx["output"], format="json")


@then("the report contains account trades lots allocations cash assumptions and warnings")
def sections(ctx):
    report = ctx["rendered"]
    for content in [
        "Balanced",
        "Reduce concentration",
        "target:2",
        "snapshot-1",
        "2026-10-08",
        "REVIEW_REQUIRED",
        "AAPL",
        "Taxable",
        "SELL",
        "old",
        "1000",
        "800",
        "209",
        "-21",
        "USD",
        "ledger",
        "long_term_gain_budget",
        "INSUFFICIENT_DATA",
        "Outside accounts unknown",
        "Unknown household history",
        "Restricted account requires review",
        "not executed automatically",
    ]:
        assert content in report
    assert "|" in report


@then("export confirmation hashes exactly the saved report bytes")
def confirmation(ctx):
    result = ctx["confirmation"]
    assert result["path"] == str(ctx["output"].resolve())
    assert result["content_hash"] == hashlib.sha256(ctx["output"].read_bytes()).hexdigest()
    assert result["plan_id"] == "plan-1"


@then("the original plan remains unchanged")
def unchanged(ctx):
    assert ctx["plan"] == ctx["original"]


@then("the report JSON exactly equals the persisted plan")
def roundtrip(ctx):
    assert json.loads(ctx["output"].read_text()) == ctx["plan"]
    assert ctx["confirmation"]["format"] == "json"


@when("a PDF report is requested")
def unsupported(ctx):
    from invest.reports import export

    ctx["output"] = ctx["directory"] / "report.pdf"
    with pytest.raises(DomainError) as caught:
        export(ctx["plan"], ctx["output"], format="pdf")
    ctx["error"] = caught.value


@then("the report request fails as invalid input without a file")
def rejected(ctx):
    assert ctx["error"].code == 1
    assert not ctx["output"].exists()


@when("its Markdown report is rendered")
def rendered(ctx):
    from invest.reports import render

    ctx["rendered"] = render(ctx["plan"])


@then("unknown tax effects are disclosed without guessed savings")
def unknown(ctx):
    assert "Estimated current tax effect: unknown" in ctx["rendered"]
    assert "not guaranteed" in ctx["rendered"]
    assert ctx["plan"] == ctx["original"]
