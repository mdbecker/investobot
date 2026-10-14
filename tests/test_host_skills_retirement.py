"""Given host-owned skills, retired prompt commands cannot own operator notes."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from invest.cli import app


@pytest.mark.parametrize('command', ['list', 'show', 'save', 'delete'])
def test_retired_prompt_commands_leave_host_notes_untouched(tmp_path, monkeypatch, command):
    # Given operator notes preserved as ordinary host Markdown (untrusted input).
    notes = tmp_path / 'local-data' / 'agent-notes'
    notes.mkdir(parents=True)
    original = notes / 'concentration.md'
    original.write_text('# Operator note\nDo not merge this into trusted skills.\n')
    before = original.read_bytes()
    args = ['prompt', command]
    if command != 'list':
        args.append('concentration')
    if command == 'save':
        args.append('-')
    # When a retired command is requested, Then it is absent and notes survive.
    result = CliRunner().invoke(app, args, input='replacement')
    assert result.exit_code != 0
    assert 'No such command' in result.output
    assert original.read_bytes() == before
    assert list(notes.iterdir()) == [original]


def test_public_discovery_and_help_retire_prompt_interface():
    # Given canonical CLI discovery, When read, Then prompt CRUD is absent.
    runner = CliRunner()
    result = runner.invoke(app, ['tools', 'list'])
    assert result.exit_code == 0
    assert 'prompt.' not in json.dumps(json.loads(result.stdout))
    assert 'prompt' not in runner.invoke(app, ['--help']).output


@pytest.mark.parametrize('agent,folder', [('codex', '.agents'), ('claude-code', '.claude')])
def test_cli_installs_host_skills_without_prompt_volume(tmp_path, monkeypatch, agent, folder):
    # Given an ordinary project workspace and no prompt volume,
    # When the deterministic installer runs, Then all canonical resources are readable.
    monkeypatch.delenv('INVEST_PROMPTS', raising=False)
    runner = CliRunner()
    result = runner.invoke(app, ['research', 'skills', 'install', '--agent', agent,
                                 '--workspace', str(tmp_path)])
    assert result.exit_code == 0, result.output
    installed = json.loads(result.stdout)
    assert len(installed['skills']) == 13
    for item in installed['skills']:
        assert (tmp_path / folder / 'skills' / item['name'] / 'SKILL.md').is_file()
    assert not (tmp_path / 'prompts').exists()
    edited = tmp_path / folder / 'skills' / 'investobot-earnings' / 'SKILL.md'
    edited.write_text('Operator edit')
    result = runner.invoke(app, ['research', 'skills', 'install', '--agent', agent,
                                 '--workspace', str(tmp_path)])
    assert result.exit_code == 1
    assert edited.read_text() == 'Operator edit'


def test_supported_bond_research_guidance_survives_in_existing_skill():
    # Given the formerly prompt-only bond topic, When the canonical skill is read,
    # Then supported valuation and complex-instrument limitations are explicit.
    root = Path(__file__).resolve().parents[1]
    content = (root / 'skills/investobot-investment-screening/SKILL.md').read_text()
    assert 'bond value' in content
    assert 'call provisions' in content
    assert 'complex' in content.lower()
