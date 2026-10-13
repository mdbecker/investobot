"""Host persistence scenarios use disposable synthetic ledgers, never operator data."""

from pathlib import Path

import pytest

from invest import backup
from invest.analytics_store import snapshot
from invest.ledger import Ledger
from invest.models import DomainError
from invest.plan_storage import load_plan, save_plan

ROOT = Path(__file__).resolve().parents[1]


def test_given_compose_when_started_then_authoritative_data_is_host_bound():
    compose = (ROOT / 'compose.yaml').read_text()
    assert '- ./local-data/state:/data' in compose
    assert '- .:/app' in compose
    assert 'ledger:/data' not in compose
    assert '\nvolumes:\n' not in compose
    assert '127.0.0.1:8765:8765' in compose
    assert 'INVEST_DB: /data/portfolio.db' in compose
    assert 'INVEST_PROMPTS' not in compose


@pytest.mark.parametrize('agent', ['.agents', '.claude'])
def test_given_generated_skill_copies_then_only_investobot_bundles_are_ignored(agent):
    rules = (ROOT / '.gitignore').read_text().splitlines()
    assert f'{agent}/skills/investobot-*/' in rules
    assert f'{agent}/' not in rules
    assert f'{agent}/skills/' not in rules


def test_given_private_files_then_build_and_git_exclude_private_storage():
    git = (ROOT / '.gitignore').read_text().splitlines()
    docker = (ROOT / '.dockerignore').read_text().splitlines()
    assert 'local-data/' in git
    assert any(rule.rstrip('/') == 'local-data' for rule in docker)
    assert '.env' in git and '.env' in docker
    assert '*.db*' in git and '*.db*' in docker
    assert '*.html' in git and '*.html' in docker
    assert '!src/invest/static/*.html' in git
    assert '!src/invest/static/*.html' in docker


@pytest.fixture
def old_storage(tmp_path):
    """A prior storage directory represents a disposable populated source volume."""
    directory = tmp_path / 'old-volume'
    directory.mkdir(mode=0o700)
    ledger = Ledger(directory / 'portfolio.db')
    ledger.apply({'account': {'id': 'fictional', 'name': 'Synthetic IRA',
                              'tax_status': 'TAX_FREE'},
                  'positions': [{'security': 'SYN', 'quantity': '10', 'price': '100',
                                 'market_value': '1000', 'displayed_price_precision': 2,
                                 'displayed_market_value_precision': 2}],
                  'cash': '100', 'cash_known': True, 'source_timestamp': '2026-10-09',
                  'source_hash': 'synthetic-storage', 'data_environment': 'SYNTHETIC'})
    save_plan(ledger, {'id': 'saved-synthetic', 'source_state': ledger.planning_state(),
                      'created_at': '2026-10-12T12:00:00Z', 'as_of': '2026-10-09',
                      'status': 'BLOCKED', 'data_environment': 'SYNTHETIC',
                      'issues': [], 'proposed_actions': []})
    artifact = directory / 'artifacts' / 'synthetic-source.json'
    artifact.parent.mkdir()
    artifact.write_bytes(b'{"data_environment":"SYNTHETIC"}')
    import hashlib
    assert snapshot(ledger, {'data_environment': 'SYNTHETIC', 'artifacts': [{
        'kind': 'SYNTHETIC_SOURCE', 'provider': 'synthetic',
        'observed_at': '2026-10-12T12:00:00Z', 'relative_path': 'artifacts/synthetic-source.json',
        'sha256': hashlib.sha256(artifact.read_bytes()).hexdigest(),
        'data_environment': 'SYNTHETIC'}]}, confirm=True)['committed']
    fingerprint = backup.logical_fingerprint(ledger.connection)
    plan = load_plan(ledger, 'saved-synthetic')
    ledger.connection.close()
    return directory, fingerprint, plan, artifact.read_bytes()


def test_given_populated_prior_storage_when_archived_and_restored_then_source_and_records_survive(
        old_storage, tmp_path):
    source, fingerprint, plan, artifact_bytes = old_storage
    source_bytes = (source / 'portfolio.db').read_bytes()
    archive = tmp_path / 'work' / 'pre-bind-volume.tar.gz'
    assert backup.create(source / 'portfolio.db', archive)['status'] == 'AVAILABLE'
    assert backup.verify(archive)['status'] == 'AVAILABLE'
    target = tmp_path / 'local-data' / 'state' / 'portfolio.db'
    target.parent.mkdir(parents=True, mode=0o700)
    assert backup.restore(archive, target, dry_run=True)['status'] == 'AVAILABLE'
    assert not target.exists()
    assert backup.restore(archive, target, confirm=True)['status'] == 'AVAILABLE'
    restored = Ledger(target)
    try:
        assert backup.logical_fingerprint(restored.connection) == fingerprint
        assert load_plan(restored, 'saved-synthetic') == plan
    finally:
        restored.connection.close()
    assert (target.parent / 'artifacts/synthetic-source.json').read_bytes() == artifact_bytes
    assert (source / 'portfolio.db').read_bytes() == source_bytes
    assert archive.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize('contents', [None, b'not an archive'])
def test_given_missing_or_invalid_archive_then_accepted_destination_is_preserved(
        old_storage, tmp_path, contents):
    source, _, _, _ = old_storage
    selected = source / 'portfolio.db'
    before = selected.read_bytes()
    archive = tmp_path / 'invalid.tar.gz'
    if contents is not None:
        archive.write_bytes(contents)
    try:
        result = backup.restore(archive, selected, confirm=True)
        assert result['status'] == 'BLOCKED'
    except DomainError:
        pass
    assert selected.read_bytes() == before
