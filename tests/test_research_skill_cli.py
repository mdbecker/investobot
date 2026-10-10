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
    assert len(json.loads(ctx['list'].stdout)['skills']) == 2


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
