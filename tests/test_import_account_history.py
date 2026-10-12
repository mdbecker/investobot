"""Import history is selected in SQLite without dropping provenance or chronology."""
import copy

import pytest

from benchmarks.financial_fixtures import build
from benchmarks.runner import manifest
from invest.models import DomainError


def candidate(snapshot, day, tag):
    value = copy.deepcopy(snapshot)
    value.update(source_timestamp=day, source_hash='fictional-reviewed-' + tag)
    for position in value['positions']:
        position['as_of'] = day
    return value


@pytest.fixture
def fixture(tmp_path):
    value = build(tmp_path, dict(manifest()['profiles']['test'], accounts=2,
                                 positions=8, lots=16, accepted_snapshots=8))
    try:
        yield value
    finally:
        value.close()


def test_selected_history_preserves_all_source_evidence_and_retry_identity(fixture):
    ledger = fixture.ledger
    previous = ledger.rows('snapshots')
    value = candidate(fixture.snapshots[0], '2026-10-10', 'accepted-source')
    preview = ledger.reconcile(value)
    assert preview['latest_known_source_date'] == '2026-10-09'
    assert preview['source_date_status'] == 'KNOWN_CURRENT'
    accepted = ledger.apply(value)
    assert accepted['status'] == 'APPLIED'
    assert ledger.apply(value) == dict(status='UNCHANGED', snapshot_id=accepted['snapshot_id'],
                                      account_id=fixture.accounts[0], warnings=value['warnings'])
    after = ledger.rows('snapshots')
    original_by_id = {row['id']: row for row in previous}
    assert {row['id']: row for row in after if row['id'] in original_by_id} == original_by_id
    imported = next(row for row in after if row['id'] == accepted['snapshot_id'])
    assert imported['source_hash'] == value['source_hash']
    assert imported['source_timestamp'] == '2026-10-10'
    assert imported['data_environment'] == 'SYNTHETIC'
    assert imported['fingerprint']
    older = candidate(fixture.snapshots[0], '2026-10-08', 'older-source')
    assert ledger.reconcile(older)['latest_known_source_date'] == '2026-10-10'
    with pytest.raises(DomainError, match='Older|override'):
        ledger.apply(older)
    assert ledger.rows('snapshots') == after


def test_history_is_fresh_per_command_and_isolated_between_accounts(fixture):
    ledger = fixture.ledger
    first = candidate(fixture.snapshots[0], '2026-10-10', 'first-account')
    second = candidate(fixture.snapshots[1], '2026-10-11', 'second-account')
    assert ledger.reconcile(first)['latest_known_source_date'] == '2026-10-09'
    assert ledger.apply(first)['status'] == 'APPLIED'
    assert ledger.reconcile(second)['latest_known_source_date'] == '2026-10-09'
    assert ledger.apply(second)['status'] == 'APPLIED'
    assert ledger.reconcile(first)['latest_known_source_date'] == '2026-10-10'
    assert ledger.reconcile(second)['latest_known_source_date'] == '2026-10-11'
    second_newer = candidate(fixture.snapshots[1], '2026-10-12', 'second-newer')
    assert ledger.apply(second_newer)['status'] == 'APPLIED'
    assert ledger.reconcile(second)['latest_known_source_date'] == '2026-10-12'
    assert ledger.reconcile(first)['latest_known_source_date'] == '2026-10-10'
    assert ledger.apply(first)['status'] == 'UNCHANGED'
