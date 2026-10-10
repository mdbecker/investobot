"""Portable fund review guidance, installation and authoritative contracts."""

import pytest

from invest.contracts import schema_contract, tools_describe, tools_list
from invest.models import DomainError
from invest.research_skills import install_skills, list_skills, show_skill


NAME = 'investobot-fund-diligence'
EXISTING = {
    'investobot-earnings': '1.0.0',
    'investobot-political-contributions': '1.0.0',
    'investobot-news': '1.0.1',
    'investobot-competitive': '1.0.0',
    'investobot-management-insiders': '1.1.0',
}


def test_fund_skill_discovery_preserves_existing_versions():
    discovered = {item['name']: item for item in list_skills()['skills']}
    assert set(discovered) == {*EXISTING, NAME}
    for name, version in EXISTING.items():
        assert discovered[name]['skill_version'] == version
    assert discovered[NAME]['skill_version'] == '1.0.0'
    assert discovered[NAME]['schema_version'] == '1.0'
    assert discovered[NAME]['research_command'] == 'research.funds'


@pytest.mark.parametrize('agent,directory', [('codex', '.agents'), ('claude-code', '.claude')])
def test_fund_guidance_installs_without_overwriting_custom_skills(tmp_path, agent, directory):
    before = {name: show_skill(name) for name in EXISTING}
    root = tmp_path / directory / 'skills'
    custom = root / 'personal-review/SKILL.md'
    custom.parent.mkdir(parents=True)
    custom.write_text('Personal source review\n')
    install_skills(agent, tmp_path)
    target = root / NAME / 'SKILL.md'
    assert target.exists(), 'Fund diligence guidance must be installed for both agents'
    for filename, text in show_skill(NAME)['files'].items():
        assert (root / NAME / filename).read_text() == text
    assert custom.read_text() == 'Personal source review\n'
    target.write_text('Human customized fund workflow\n')
    with pytest.raises(DomainError, match='modified'):
        install_skills(agent, tmp_path)
    assert target.read_text() == 'Human customized fund workflow\n'
    for name, bundle in before.items():
        assert show_skill(name) == bundle


def test_fund_skill_uses_authoritative_contract_and_explicit_source_review():
    assert NAME in {item['name'] for item in list_skills()['skills']}
    bundle = show_skill(NAME)['files']
    assert set(bundle) == {'SKILL.md', 'references/research-method.md',
                           'references/fees-and-tax.md', 'references/holdings-liquidity.md',
                           'references/json-contract.md'}
    assert bundle['SKILL.md'].startswith(f'---\nname: {NAME}\n')
    assert 'version: "1.0.0"' in bundle['SKILL.md']
    for reference in ('research-method.md', 'fees-and-tax.md', 'holdings-liquidity.md',
                      'json-contract.md'):
        assert f'(references/{reference})' in bundle['SKILL.md']
    text = '\n'.join(bundle.values())
    for requirement in ('invest schema', 'research.funds.import', 'invest research funds validate',
                        'invest research funds import', 'explicit human approval',
                        'registrant_cik', 'series_id', 'class_id', 'local-data',
                        'external agent', 'UNSUPPORTED_FUND_STRUCTURE'):
        assert requirement in text


def test_fund_tool_discovery_exposes_real_schema_and_research_only_acceptance():
    commands = {item['name']: item for item in tools_list()['tools']}
    expected = {f'research.funds.{operation}' for operation in
                ('validate', 'import', 'list', 'show', 'summary', 'holdings')}
    assert expected <= set(commands), 'All diligence tools must be discoverable'
    contract = tools_describe('research.funds.import')
    assert contract['mutation_scope'] == 'research'
    assert contract['json_input_schema']['title'] == 'FundDiligenceInput'
    for operation in ('validate', 'list', 'show', 'summary', 'holdings'):
        assert not commands[f'research.funds.{operation}']['mutates_persistent_state']
    schema = schema_contract()
    assert any(value == contract['json_input_schema'] for value in schema.values()
               if isinstance(value, dict))
