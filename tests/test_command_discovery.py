import pytest
import typer
from pytest_bdd import given, scenarios, then, when

from invest.models import DomainError, Snapshot

scenarios("features/command_discovery.feature")


@pytest.fixture
def ctx():
    return {}


@when("the agent lists the tool catalogue")
def list_tools(ctx):
    from invest.contracts import tools_list

    ctx["result"] = tools_list()


@then("the catalogue identifies financial mutations and cache writes")
def mutations(ctx):
    tools = {tool["name"]: tool for tool in ctx["result"]["tools"]}
    assert tools["portfolio.apply"]["mutates_persistent_state"] is True
    assert tools["portfolio.apply"]["mutation_scope"] == "actual_portfolio"
    assert tools["portfolio.record-activity"]["mutation_scope"] == "actual_portfolio"
    assert tools["portfolio.summary"]["mutates_persistent_state"] is False
    assert tools["portfolio.simulate"]["mutates_persistent_state"] is False
    assert tools["market.quote"]["mutation_scope"] == "market_cache"


@when("the agent describes portfolio.simulate")
def describe_simulation(ctx):
    from invest.contracts import tools_describe

    ctx["result"] = tools_describe("portfolio.simulate")


@then("the contract describes inputs outputs and a read-only example")
def simulation_contract(ctx):
    contract = ctx["result"]
    assert contract["name"] == "portfolio.simulate"
    assert contract["input_schema"]["required"] == ["file"]
    assert contract["input_schema"]["properties"]["file"]["type"] == "string"
    assert contract["mutates_persistent_state"] is False
    assert contract["output_contract"]
    assert contract["purpose"]
    assert "invest portfolio simulate" in contract["examples"][0]


@when("the agent requests the complete discovery schema")
def complete(ctx):
    from invest.contracts import schema_contract

    ctx["result"] = schema_contract()


@then("snapshot commands expose the validated snapshot schema")
def snapshots(ctx):
    assert ctx["result"]["snapshot"] == Snapshot.model_json_schema()
    tools = {tool["name"]: tool for tool in ctx["result"]["tools"]}
    assert tools["portfolio.apply"]["json_input_schema"] == Snapshot.model_json_schema()
    assert tools["portfolio.reconcile"]["json_input_schema"] == Snapshot.model_json_schema()


@then("discovery documents structured error semantics")
def errors(ctx):
    contract = ctx["result"]["output_contract"]
    assert contract["diagnostics"] == "stderr JSON"
    assert set(contract["exit_codes"]) == {"0", "1", "2", "3", "4"}
    assert contract["error_schema"]["required"] == ["error"]


@given("an application with a newly registered target command")
def new_command(ctx):
    app = typer.Typer()
    target = typer.Typer()
    app.add_typer(target, name="target")

    @target.command("show")
    def show(target_id: str):
        pass

    ctx["app"] = app


@when("the agent lists that application's tool catalogue")
def list_custom(ctx):
    from invest.contracts import tools_list

    ctx["result"] = tools_list(ctx["app"])


@then("the target command is discovered without another schema registry")
def added(ctx):
    assert ctx["result"]["tools"][0]["name"] == "target.show"


@when("the agent describes an unknown tool")
def unknown(ctx):
    from invest.contracts import tools_describe

    with pytest.raises(DomainError) as error:
        tools_describe("broker.execute")
    ctx["error"] = error.value


@then("the request fails with input error code one")
def input_error(ctx):
    assert ctx["error"].code == 1
