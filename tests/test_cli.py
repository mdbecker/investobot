import json
import pytest
from pytest_bdd import scenarios, given, when, then
from typer.testing import CliRunner
from invest.cli import app
scenarios('features/cli.feature')
@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.setenv('INVEST_DB', str(tmp_path/'db'))
    monkeypatch.setenv('INVEST_CONFIG', str(tmp_path/'config.toml'))
    monkeypatch.delenv('FMP_API_KEY', raising=False)
    monkeypatch.delenv('INVEST_FIXTURES', raising=False)
    return {'runner':CliRunner(),'tmp':tmp_path}
@when('I invoke apply with an invalid snapshot')
def invalid(ctx):
    path = ctx['tmp']/'invalid.json'
    path.write_text('{}')
    ctx['result'] = ctx['runner'].invoke(app, ['portfolio','apply',str(path)])
@then('the command exits one with JSON on stderr')
def code_one(ctx):
    assert ctx['result'].exit_code == 1
    assert json.loads(ctx['result'].stderr)['error']
    assert ctx['result'].stdout == ''
@when('I request fund holdings without credentials')
def holdings(ctx):
    ctx['result'] = ctx['runner'].invoke(app,['fund','holdings','VTI'])
@then('the command exits two with JSON on stderr')
def code_two(ctx):
    assert ctx['result'].exit_code == 2
    assert json.loads(ctx['result'].stderr)['error']
@given('an empty local ledger')
def empty(ctx):
    pass
@when('I request tax lots')
def lots(ctx):
    ctx['result'] = ctx['runner'].invoke(app,['tax','lots'])
@then('the command emits valid JSON on stdout')
def output(ctx):
    assert ctx['result'].exit_code == 0
    assert 'lots' in json.loads(ctx['result'].stdout)
    assert ctx['result'].stderr == ''
@when('I invoke an unknown subcommand')
def syntax(ctx):
    ctx['result'] = ctx['runner'].invoke(app, ['portfolio','does-not-exist'])
