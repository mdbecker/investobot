"""Installed host skills keep repository guidance usable from either agent folder."""

import json
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from invest.cli import app
from invest.research_skills import list_skills, show_skill


@pytest.mark.parametrize('agent', ['codex', 'claude-code'])
def test_copied_skills_preserve_bundles_and_usable_resource_paths(tmp_path, agent):
    result = CliRunner().invoke(app, [
        'research', 'skills', 'install', '--agent', agent, '--workspace', str(tmp_path),
    ])
    assert result.exit_code == 0, result.output
    installed = json.loads(result.stdout)
    destination = Path(installed['destination'])
    discovered = {item['name']: item for item in list_skills()['skills']}
    assert len(discovered) == 13
    assert {item['name'] for item in installed['skills']} == set(discovered)
    for name, metadata in discovered.items():
        bundle = show_skill(name)
        assert bundle['skill_version'] == metadata['skill_version']
        copied = {path.relative_to(destination / name).as_posix(): path.read_text()
                  for path in (destination / name).rglob('*') if path.is_file()}
        # Exact copy fidelity is the installer contract, not a frozen prose snapshot.
        assert copied == bundle['files']

    # When the host agent follows copied Markdown links, every local resource exists.
    for document in destination.rglob('*.md'):
        content = document.read_text()
        for target in re.findall(r'\]\(([^)]+)\)', content):
            if '://' not in target and not target.startswith('#'):
                resource = (document.parent / target.split('#', 1)[0]).resolve()
                bundle_root = destination / document.relative_to(destination).parts[0]
                assert resource.is_relative_to(bundle_root) and resource.is_file(), (
                    f'{document.relative_to(destination)} has an unusable link: {target}'
                )

        for reference in re.findall(r'\bdocs/[\w./-]+\.md\b', content):
            assert (Path(__file__).resolve().parents[1] / reference).is_file()

    # Repository references are usable paths regardless of English explanation or backticks.
    for name in ['investobot-monthly-investing', 'investobot-portfolio-strategy']:
        content = (destination / name / 'SKILL.md').read_text()
        assert re.findall(r'\bdocs/[\w./-]+\.md\b', content)
