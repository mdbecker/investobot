import json

import pytest
from pytest_bdd import given, scenarios, then, when
from typer.testing import CliRunner

from invest.cli import app
from invest.prompts import DEFAULTS, PromptLibrary

scenarios('features/research_skill_cli.feature')


@pytest.fixture
def ctx(tmp_path):
    return {'library': PromptLibrary(tmp_path / 'prompts'), 'runner': CliRunner()}


@when('research skill tools are discovered')
def discover(ctx):
    ctx['install'] = ctx['runner'].invoke(app, ['tools', 'describe', 'research.skills.install'])
    ctx['list'] = ctx['runner'].invoke(app, ['research', 'skills', 'list'])


@then('installation is scoped to project skill files and discovery is read only')
def scoped(ctx):
    assert ctx['install'].exit_code == 0
    assert json.loads(ctx['install'].stdout)['mutation_scope'] == 'project_skill_files'
    assert ctx['list'].exit_code == 0
    skills = json.loads(ctx['list'].stdout)['skills']
    assert len(skills) == 13
    assert {item['name'] for item in skills} == {
        'investobot-earnings',
        'investobot-political-contributions',
        'investobot-news',
        'investobot-competitive',
        'investobot-management-insiders',
        'investobot-fund-diligence',
        'investobot-portfolio-sync',
        'investobot-portfolio-performance',
        'investobot-monthly-investing',
        'investobot-tax-loss-harvesting',
        'investobot-investment-screening',
        'investobot-portfolio-research',
        'investobot-portfolio-strategy',
    }


@given('a user override of the legacy political prompt')
def override(ctx):
    ctx['library'].save('executive-political-contributions', '# Custom political workflow')


@when('bundled prompts are inspected')
def prompts(ctx):
    ctx['prompt'] = ctx['library'].show('executive-political-contributions')


@then('the political prompt is no longer bundled and the user override survives')
def survives(ctx):
    assert not (DEFAULTS / 'executive-political-contributions.md').exists()
    assert ctx['prompt']['source'] == 'user'
    assert not ctx['prompt']['bundled_available']
    assert ctx['prompt']['content'] == '# Custom political workflow'


def test_political_runs_pin_bundled_skill_identity(tmp_path):
    from test_political_import import package

    from invest.ledger import Ledger
    from invest.political import import_research
    from invest.political_queries import show
    db = Ledger(tmp_path / 'political.db')
    try:
        result = import_research(db, package(), yes=True)
        accepted = show(db, result['research_run_id'])
        assert accepted['skill_name'] == 'investobot-political-contributions'
        assert accepted['skill_version'] == '1.0.0'
    finally:
        db.connection.close()
