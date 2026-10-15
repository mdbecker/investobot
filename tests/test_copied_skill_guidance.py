"""Installed host skills keep repository guidance usable from either agent folder."""

import json
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from invest.cli import app


@pytest.mark.parametrize('agent', ['codex', 'claude-code'])
def test_copied_skills_resolve_local_resources_and_explain_repository_paths(tmp_path, agent):
    # Given a checkout with its operational walkthrough and project-local skills,
    walkthrough = tmp_path / 'docs' / 'workflows.md'
    walkthrough.parent.mkdir()
    walkthrough.write_text('# Operational walkthrough\n')
    result = CliRunner().invoke(app, [
        'research', 'skills', 'install', '--agent', agent, '--workspace', str(tmp_path),
    ])
    assert result.exit_code == 0, result.output
    destination = Path(json.loads(result.stdout)['destination'])

    # When the host agent follows copied Markdown links, every local resource exists.
    for document in destination.rglob('*.md'):
        content = document.read_text()
        for target in re.findall(r'\]\(([^)]+)\)', content):
            if '://' not in target and not target.startswith('#'):
                assert (document.parent / target.split('#', 1)[0]).is_file(), (
                    f'{document.relative_to(destination)} has an unusable link: {target}'
                )

    # Then cross-bundle guidance names a path opened from the repository root.
    for name in ['investobot-monthly-investing', 'investobot-portfolio-strategy']:
        content = (destination / name / 'SKILL.md').read_text()
        assert '`docs/workflows.md`' in content
        assert 'repository root' in content
