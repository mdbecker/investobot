"""Portable news guidance remains explicit, local and evidence driven."""

import pytest
from pytest_bdd import given, scenarios, then, when

from invest.models import DomainError
from invest.research_skills import install_skills, list_skills, show_skill

scenarios('features/news_skill.feature')


@pytest.fixture
def ctx(tmp_path):
    return {'workspace': tmp_path}


@given('the existing political and earnings skill contents')
def existing(ctx):
    ctx['existing'] = {name: show_skill(name) for name in (
        'investobot-earnings', 'investobot-political-contributions')}


@when('news research skill discovery and project installation are requested')
def discover(ctx):
    ctx['names'] = {item['name'] for item in list_skills()['skills']}
    ctx['news'] = show_skill('investobot-news')
    ctx['installed'] = install_skills('codex', ctx['workspace'])


@then('news guidance and all existing bundles are available unchanged')
def available(ctx):
    assert ctx['names'] == {*ctx['existing'], 'investobot-news'}
    assert ctx['news']['skill_version'] == '1.0.1'
    expected = {'SKILL.md', 'references/research-method.md', 'references/event-identity.md',
                'references/json-contract.md', 'references/change-review.md'}
    assert set(ctx['news']['files']) == expected
    for name, original in ctx['existing'].items():
        assert show_skill(name) == original
    for name in ctx['names']:
        for filename, text in show_skill(name)['files'].items():
            assert (ctx['workspace'] / '.agents/skills' / name / filename).read_text() == text


@pytest.mark.parametrize('agent,directory', [('codex', '.agents'), ('claude-code', '.claude')])
def test_news_install_protects_modified_user_guidance(tmp_path, agent, directory):
    install_skills(agent, tmp_path)
    target = tmp_path / directory / 'skills/investobot-news/SKILL.md'
    assert target.exists()
    target.write_text('Human custom instructions\n')
    with pytest.raises(DomainError, match='modified'):
        install_skills(agent, tmp_path)
    assert target.read_text() == 'Human custom instructions\n'


def test_news_skill_points_to_authoritative_offline_contract_and_human_approval():
    bundle = show_skill('investobot-news')['files']
    text = '\n'.join(bundle.values())
    assert bundle['SKILL.md'].startswith('---\nname: investobot-news\n')
    for reference in ('research-method.md', 'event-identity.md', 'json-contract.md', 'change-review.md'):
        assert f'(references/{reference})' in bundle['SKILL.md']
    for command in ('invest schema', 'research.news.import', 'invest research news context',
                    'invest research news validate', 'invest research news import',
                    'invest research news changes', 'invest research news compare'):
        assert command in text
    for concept in ('explicit human approval', 'event_key', 'fact_key', 'catalyst_id', 'thesis_id',
                    'not_reobserved', 'publication', 'primary', 'copyright', 'local-data'):
        assert concept in text
    assert 'full articles' in text
