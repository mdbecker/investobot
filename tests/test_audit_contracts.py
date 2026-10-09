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
