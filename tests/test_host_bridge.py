"""Package A: the host shell contract, with Docker as the external boundary."""

import json
import os
import re
import shlex
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from invest.cli import app

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / 'scripts' / 'invest'


@pytest.fixture
def docker_boundary(tmp_path):
    """A disposable external executable; no application or storage is mocked."""
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    executable = bin_dir / 'docker'
    executable.write_text(
        '#!/bin/sh\n'
        'printf "%s\\0" "$PWD" "$@" > "$BRIDGE_CAPTURE"\n'
        '/bin/cat > "$BRIDGE_INPUT"\n'
        'printf "%s" "$BRIDGE_STDOUT"\n'
        'printf "%s" "$BRIDGE_STDERR" >&2\n'
        'exit "$BRIDGE_STATUS"\n'
    )
    executable.chmod(0o700)
    return {
        'PATH': str(bin_dir),
        'BRIDGE_CAPTURE': str(tmp_path / 'arguments'),
        'BRIDGE_INPUT': str(tmp_path / 'input'),
        'BRIDGE_STDOUT': '{"source":"container"}\n',
        'BRIDGE_STDERR': '',
        'BRIDGE_STATUS': '0',
    }


@pytest.mark.parametrize(
    ('arguments', 'payload', 'status', 'stdout', 'stderr'),
    [
        (['tools', 'list'], b'', 0, '{"tools":[]}\n', ''),
        (['tools', 'describe', 'research.earnings.import'], b'', 0, '{"name":"research.earnings.import"}', ''),
        (['research', 'earnings', 'validate', '-'], b'{"exact":"123.000", "source":"quoted\\ntext"}\n', 0, '{"valid":true}\n', ''),
        (['research', 'earnings', 'validate', '/app/local-data/input/a file.json', '', '$HOME; literal'], b'bad input\n', 3, '', '{"error":"blocked"}\n'),
    ],
)
def test_given_shell_only_host_when_bridge_runs_then_container_contract_is_preserved(
    tmp_path, docker_boundary, arguments, payload, status, stdout, stderr,
):
    # Given an ordinary host shell with no Python, uv or application on PATH.
    assert BRIDGE.is_file(), 'The host-to-Docker executable is missing'
    assert os.access(BRIDGE, os.X_OK), 'The host bridge must be executable'
    docker_boundary.update(
        BRIDGE_STATUS=str(status), BRIDGE_STDOUT=stdout, BRIDGE_STDERR=stderr,
    )
    # When called outside the checkout, including stdin and literal arguments.
    result = subprocess.run(
        [str(BRIDGE), *arguments], input=payload, capture_output=True,
        cwd=tmp_path, env=docker_boundary, check=False,
    )
    # Then Compose sees the canonical project root and byte-exact CLI arguments.
    captured = Path(docker_boundary['BRIDGE_CAPTURE']).read_bytes().split(b'\0')[:-1]
    assert captured == [str(ROOT).encode(), *[
        item.encode() for item in ['compose', 'run', '--rm', '-T', 'app', 'invest', *arguments]
    ]]
    assert Path(docker_boundary['BRIDGE_INPUT']).read_bytes() == payload
    assert result.returncode == status
    assert result.stdout == stdout.encode()
    assert result.stderr == stderr.encode()
    if stdout:
        assert isinstance(json.loads(result.stdout), dict)
    assert not (ROOT / '.venv').exists()


@pytest.mark.parametrize('skill', sorted((ROOT / 'skills').glob('*/SKILL.md')), ids=lambda p: p.parent.name)
def test_given_host_agent_when_reading_skills_then_commands_use_docker_bridge(skill):
    # Given canonical host-readable skills and their local references.
    text = skill.read_text()
    references = sorted((skill.parent / 'references').glob('*.md'))
    combined = '\n'.join([text, *[path.read_text() for path in references]])
    # Check executable syntax against public CLI metadata, not surrounding English.
    runner = CliRunner()
    result = runner.invoke(app, ['tools', 'list'])
    assert result.exit_code == 0, result.output
    commands = {tuple(item['name'].split('.')): item
                for item in json.loads(result.stdout)['tools']}
    examples = re.findall(r'\./scripts/invest\s+([^`\n]+)', combined)
    assert examples, 'A host skill must offer a callable command'
    described = {}
    for example in examples:
        args = shlex.split(example)
        matches = [path for path in commands if list(path) == args[:len(path)]]
        assert matches, f'{skill.parent.name}: unknown command {example}'
        path = max(matches, key=len)
        if path not in described:
            result = runner.invoke(app, ['tools', 'describe', '.'.join(path)])
            assert result.exit_code == 0, result.output
            described[path] = json.loads(result.stdout)
        descriptor = described[path]
        flags = {flag for option in descriptor['options'] for flag in option['flags']}
        for token in args[len(path):]:
            if token.startswith('--'):
                assert token.split('=', 1)[0] in flags | {'--help'}, example
        if path == ('tools', 'describe') and args[2] != 'TOOL':
            assert tuple(args[2].split('.')) in commands, example
        assert isinstance(descriptor['json_input_schema'], dict)
    assert not re.search(r'(?m)(?:`|^)invest\s', combined), 'Bare host CLI command remains'

