"""Pure performance fixtures retain real SQLite guards without repeated restores."""
import inspect
import sqlite3

import pytest

from benchmarks import financial_workloads, runner

PURE_CASES = ('P05.household-performance', 'P05.account-performance',
              'P05.linked-flow-metrics', 'P05.incomplete-coverage')
DIMENSIONS = runner.manifest()['profiles']['test']


def live_connection(prepared):
    """Inspect the real operation's captured ledger; never replace its dependencies."""
    return inspect.getclosurevars(prepared.close).nonlocals['ledger'].connection


def assert_native_proofs(prepared):
    output = prepared.operation()
    proofs = prepared.verify(output)
    assert set(proofs) == {'independent-dated-flow-results', 'account-scope-correct',
                           'missing-coverage-typed'}
    assert all(proof['passed'] and proof['expected'] == proof['observed']
               for proof in proofs.values())
    return output


@pytest.mark.parametrize('case', PURE_CASES)
def test_pure_performance_reset_never_rewrites_database_and_preserves_native_proofs(tmp_path, case):
    prepared = financial_workloads.prepare(case, tmp_path, DIMENSIONS)
    observer = sqlite3.connect(tmp_path / 'financial.db')
    try:
        version = observer.execute('PRAGMA data_version').fetchone()[0]
        first = assert_native_proofs(prepared)
        for _ in range(3):
            prepared.reset()
            assert observer.execute('PRAGMA data_version').fetchone()[0] == version
            assert assert_native_proofs(prepared) == first
    finally:
        observer.close()
        prepared.close()


@pytest.mark.parametrize('case', PURE_CASES)
def test_pure_performance_uses_sqlite_readonly_guard(tmp_path, case):
    prepared = financial_workloads.prepare(case, tmp_path, DIMENSIONS)
    connection = live_connection(prepared)
    try:
        assert connection.execute('PRAGMA query_only').fetchone()[0] == 1
        with pytest.raises(sqlite3.OperationalError, match='readonly'):
            connection.execute('UPDATE accounts SET name=name')
        assert_native_proofs(prepared)
    finally:
        prepared.close()


def test_disabling_readonly_guard_is_rejected_before_another_operation(tmp_path):
    prepared = financial_workloads.prepare(PURE_CASES[0], tmp_path, DIMENSIONS)
    connection = live_connection(prepared)
    try:
        connection.execute('PRAGMA query_only=OFF')
        with pytest.raises(ValueError, match='(?i)read.only|guard|changed|mutat'):
            prepared.reset()
    finally:
        connection.execute('PRAGMA query_only=ON')
        prepared.close()


def test_same_connection_write_even_after_guard_restoration_is_rejected(tmp_path):
    prepared = financial_workloads.prepare(PURE_CASES[0], tmp_path, DIMENSIONS)
    connection = live_connection(prepared)
    connection.execute('PRAGMA query_only=OFF')
    connection.execute('UPDATE accounts SET name=name')
    connection.commit()
    connection.execute('PRAGMA query_only=ON')
    try:
        with pytest.raises(ValueError, match='(?i)changed|mutat|guard'):
            prepared.reset()
    finally:
        with pytest.raises(ValueError, match='(?i)changed|mutat|guard'):
            prepared.close()
        with pytest.raises(sqlite3.ProgrammingError, match='closed'):
            connection.execute('SELECT 1')


def test_external_committed_write_is_rejected_without_restoring_it(tmp_path):
    prepared = financial_workloads.prepare(PURE_CASES[0], tmp_path, DIMENSIONS)
    connection = live_connection(prepared)
    external = sqlite3.connect(tmp_path / 'financial.db')
    initial_version = connection.execute('PRAGMA data_version').fetchone()[0]
    account_id, original_name = external.execute('SELECT id,name FROM accounts ORDER BY id').fetchone()
    # A no-op may change zero pages and leaves SQLite data_version unchanged.
    # Commit a real change and its reversal: final state equality must not hide writes.
    external.execute('UPDATE accounts SET name=? WHERE id=?',
                     (original_name + ' transient benchmark mutation', account_id))
    external.commit()
    external.execute('UPDATE accounts SET name=? WHERE id=?', (original_name, account_id))
    external.commit()
    external.close()
    assert connection.execute('SELECT name FROM accounts WHERE id=?', (account_id,)).fetchone()[0] == original_name
    assert connection.execute('PRAGMA data_version').fetchone()[0] != initial_version
    try:
        with pytest.raises(ValueError, match='(?i)changed|mutat|guard'):
            prepared.reset()
    finally:
        with pytest.raises(ValueError, match='(?i)changed|mutat|guard'):
            prepared.close()
        with pytest.raises(sqlite3.ProgrammingError, match='closed'):
            connection.execute('SELECT 1')


def test_close_checks_actual_inventory_and_closes_after_final_mutation_failure(tmp_path):
    prepared = financial_workloads.prepare(PURE_CASES[0], tmp_path, DIMENSIONS)
    connection = live_connection(prepared)
    assert_native_proofs(prepared)
    external = sqlite3.connect(tmp_path / 'financial.db')
    external.execute('DELETE FROM position_balances')
    external.commit()
    external.close()
    with pytest.raises(ValueError, match='(?i)changed|mutat|guard|inventory'):
        prepared.close()
    with pytest.raises(sqlite3.ProgrammingError, match='closed'):
        connection.execute('SELECT 1')
