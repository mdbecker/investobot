import json

import pytest
from pytest_bdd import given, scenarios, then, when
from typer.testing import CliRunner

from invest.cli import app

scenarios('features/agent_cli.feature')


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.setenv('INVEST_DB', str(tmp_path / 'db'))
    return {'tmp': tmp_path, 'runner': CliRunner()}


@when('the agent invokes tools list')
def catalogue(ctx):
    ctx['result'] = ctx['runner'].invoke(app, ['tools', 'list'])


@then('the JSON catalogue includes portfolio.simulate')
def listed(ctx):
    assert ctx['result'].exit_code == 0
    assert any(t['name'] == 'portfolio.simulate' for t in json.loads(ctx['result'].stdout)['tools'])


@when('the agent describes portfolio.simulate through the CLI')
def describe(ctx):
    ctx['result'] = ctx['runner'].invoke(app, ['tools', 'describe', 'portfolio.simulate'])


@then('the JSON contract identifies simulation as read only')
def readonly(ctx):
    assert ctx['result'].exit_code == 0
    assert json.loads(ctx['result'].stdout)['mutates_persistent_state'] is False


@given('a synthetic saved holdings page')
def page(ctx):
    ctx['page'] = ctx['tmp'] / 'account.html'
    ctx['page'].write_text('<table><tr><th>Symbol</th><th>Quantity</th><th>Market Value</th><th>Cost Basis</th><th>Acquisition Date</th></tr>'
                          '<tr><td>AAA</td><td>10</td><td>1000</td><td>800</td><td>2024-01-01</td></tr></table>')


@when('the agent imports with a known date and confirmed complete coverage')
def imported(ctx):
    ctx['result'] = ctx['runner'].invoke(app, ['portfolio', 'import', str(ctx['page']),
        '--account', 'synthetic', '--as-of', '2026-10-08', '--positions-complete', '--lots-complete'])


@then('the normalized snapshot confirms source date and both completeness fields')
def dates(ctx):
    assert ctx['result'].exit_code == 0
    result = json.loads(ctx['result'].stdout)
    assert result['source_timestamp'] == '2026-10-08'
    assert result['positions_complete'] is True
    assert result['lots_complete'] is True
