"""Discovery offers supported database operations without speculative upgrades."""

import json

from typer.testing import CliRunner

from invest.cli import app


def test_database_discovery_exposes_only_supported_operations():
    runner = CliRunner()
    result = runner.invoke(app, ['tools', 'list'])
    assert result.exit_code == 0, result.output
    names = {tool['name'] for tool in json.loads(result.stdout)['tools']}
    assert {'db.status', 'db.backup', 'db.verify', 'db.restore'} <= names
    assert 'db.migrate' not in names
    help_result = runner.invoke(app, ['db', '--help'])
    assert help_result.exit_code == 0
    assert 'migrate' not in help_result.output


def test_unsupported_database_upgrade_is_rejected_without_creating_state(tmp_path, monkeypatch):
    path = tmp_path / 'absent.db'
    monkeypatch.setenv('INVEST_DB', str(path))
    result = CliRunner().invoke(app, ['db', 'migrate'])
    assert result.exit_code != 0
    assert 'No such command' in result.output
    assert not path.exists()
