"""Explicit cleanup removes abandoned managed staging, never accepted evidence."""

import hashlib
import json

from typer.testing import CliRunner

from invest.analytics_store import snapshot
from invest.cli import app
from invest.ledger import Ledger


def test_cleanup_preview_then_confirm_preserves_referenced_and_user_files(tmp_path, monkeypatch):
    path = tmp_path / 'fictional.db'
    monkeypatch.setenv('INVEST_DB', str(path))
    root = tmp_path / 'artifacts'
    root.mkdir()
    abandoned = root / '.artifact-abandoned'
    abandoned.write_bytes(b'fictional interrupted publication')
    referenced = root / '.artifact-referenced'
    referenced.write_bytes(b'fictional accepted evidence')
    user_file = root / 'notes.txt'
    user_file.write_bytes(b'user-owned notes')
    ledger = Ledger(path)
    try:
        accepted = snapshot(ledger, {'data_environment': 'SYNTHETIC',
            'artifacts': [{'kind': 'PUBLIC_DOCUMENT', 'provider': 'FICTIONAL_SOURCE',
                'observed_at': '2026-10-01', 'relative_path': referenced.name,
                'sha256': hashlib.sha256(referenced.read_bytes()).hexdigest()}]},
            confirm=True, artifact_root=root)
        assert accepted['committed'] is True
        before = ledger.planning_state()
    finally:
        ledger.connection.close()
    runner = CliRunner()
    args = ['db', 'cleanup-artifacts', '--artifact-root', str(root)]
    preview = runner.invoke(app, args)
    assert preview.exit_code == 0, preview.output
    assert json.loads(preview.stdout)['committed'] is False
    assert abandoned.exists() and referenced.exists() and user_file.exists()
    confirmed = runner.invoke(app, [*args, '--confirm'])
    assert confirmed.exit_code == 0, confirmed.output
    assert json.loads(confirmed.stdout)['committed'] is True
    assert not abandoned.exists()
    assert referenced.read_bytes() == b'fictional accepted evidence'
    assert user_file.read_bytes() == b'user-owned notes'
    ledger = Ledger(path)
    try:
        assert ledger.planning_state() == before
    finally:
        ledger.connection.close()


def test_cleanup_rejects_symlink_staging_without_deleting_target(tmp_path, monkeypatch):
    monkeypatch.setenv('INVEST_DB', str(tmp_path / 'fictional.db'))
    root = tmp_path / 'artifacts'
    root.mkdir()
    target = tmp_path / 'private.txt'
    target.write_bytes(b'user-owned evidence')
    (root / '.artifact-symlink').symlink_to(target)
    result = CliRunner().invoke(app, ['db', 'cleanup-artifacts', '--artifact-root', str(root), '--confirm'])
    assert result.exit_code == 3, result.output
    assert 'symlink' in result.stderr.lower()
    assert target.read_bytes() == b'user-owned evidence'
