import pytest
from pytest_bdd import parsers, scenarios, then, when

from invest.contracts import tools_describe

scenarios("features/audit_contracts.feature")


@pytest.fixture
def ctx():
    return {}


@when(parsers.parse('the agent describes the audit tool "{tool}"'))
def describe(ctx, tool):
    ctx["result"] = tools_describe(tool)


@then(parsers.parse('its response detail is "{detail}"'))
def detail(ctx, detail):
    output = ctx["result"]["output_contract"]
    assert output["response_detail"] == detail
    if detail == "compact_summary":
        assert "tax_summary" in output["summary_fields"]
        assert "drift_summary" in output["summary_fields"]
        assert output["full_details_tool"] == "plan.show"
    else:
        assert output["potentially_large_response"] is True


@then('its contract identifies explicit classification reviews')
def classification_reviews(ctx):
    result = ctx["result"]
    output = result["output_contract"]
    assert output["classification_reviews"] == {
        "fields": ["security_id", "ticker", "canonical_type", "observed_type", "action_required"],
        "action_required": "EXPLICIT_CLASSIFICATION",
        "correction_tool": "security.classify",
    }
    assert result["mutation_scope"] == "none"
