"""Account-local inventory reads preserve exact rows and global lot ownership."""
import copy
import re

import pytest

from benchmarks.financial_fixtures import build
from benchmarks.runner import manifest
from invest import db
from invest.models import DomainError


@pytest.fixture
def fixture(tmp_path):
    value = build(tmp_path, dict(manifest()['profiles']['test'], accounts=2,
                                 positions=8, lots=16, accepted_snapshots=8))
    try:
        yield value
    finally:
        value.close()


def candidate(snapshot, tag, *, complete=True):
    value = copy.deepcopy(snapshot)
    value.update(source_timestamp='2026-10-10', source_hash='fictional-reviewed-' + tag,
                 positions_complete=complete, lots_complete=complete)
    for position in value['positions']:
        position['as_of'] = '2026-10-10'
    if not complete:
        value['positions'] = value['positions'][:1]
        value['positions'][0]['cost_basis'] = None
        value['lots'] = []
    return value


@pytest.mark.parametrize('table', ['positions', 'lots', 'cash_balances'])
def test_account_row_filter_preserves_full_decoded_rows_order_and_key_intersection(fixture, table):
    ledger = fixture.ledger
    all_rows = db.rows(ledger.connection, table)
    account = fixture.accounts[0]
    expected = [row for row in all_rows if row['account_id'] == account]
    assert expected
    assert db.rows(ledger.connection, table, account_id=account) == expected
    assert db.rows(ledger.connection, table, expected[0]['id'], account_id=account) == [expected[0]]
    assert db.rows(ledger.connection, table, expected[0]['id'],
                   account_id=fixture.accounts[1]) == []
    assert db.rows(ledger.connection, table, account_id='fictional-absent-account') == []
    assert db.rows(ledger.connection, table) == all_rows


@pytest.mark.parametrize('table', ['accounts', 'securities', 'snapshots', 'target_versions'])
def test_account_filter_rejects_unsupported_storage_tables(fixture, table):
    with pytest.raises(ValueError, match='(?i)account|filter|supported'):
        db.rows(fixture.ledger.connection, table, account_id=fixture.accounts[0])


@pytest.mark.parametrize('operation', ['reconcile', 'apply'])
@pytest.mark.parametrize('complete', [True, False], ids=['complete', 'partial'])
def test_import_inventory_queries_filter_before_decoding(fixture, operation, complete):
    ledger = fixture.ledger
    value = candidate(fixture.snapshots[0], operation + str(complete), complete=complete)
    statements = []
    ledger.connection.set_trace_callback(statements.append)
    try:
        result = getattr(ledger, operation)(value)
    finally:
        ledger.connection.set_trace_callback(None)
    if operation == 'apply':
        assert result['status'] == 'APPLIED'
    reads = [sql for sql in statements if re.search(r'\bSELECT\b', sql, re.I)
             and re.search(r'\bFROM\s+(position_balances|tax_lots)\b', sql, re.I)]
    assert reads
    for sql in reads:
        assert re.search(r'\bWHERE\b', sql, re.I), sql
        if re.search(r'\baccount_id\s*=', sql, re.I):
            assert fixture.accounts[0] in sql, sql
        else:
            # Global identity lookups are allowed only for one indexed lot ID.
            assert re.search(r'\bFROM\s+tax_lots\b', sql, re.I), sql
            assert re.search(r'\bWHERE\s+id\s*=', sql, re.I), sql


def test_cross_account_lot_identity_collision_is_rejected_atomically(fixture):
    ledger = fixture.ledger
    tables = ('accounts', 'positions', 'lots', 'cash_balances', 'snapshots', 'activities')
    before = {table: ledger.rows(table) for table in tables}
    other_lot = next(row for row in before['lots'] if row['account_id'] == fixture.accounts[1])
    value = candidate(fixture.snapshots[0], 'foreign-lot-collision')
    value['lots'][0]['id'] = other_lot['id']
    with pytest.raises(DomainError, match='Lot identifier belongs to another account/security'):
        ledger.apply(value)
    assert {table: ledger.rows(table) for table in tables} == before


def test_complete_reimport_refreshes_rows_without_requerying_known_account_lot_ids(fixture):
    ledger = fixture.ledger
    value = candidate(fixture.snapshots[0], 'known-ownership')
    before = {row['id']: row for row in ledger.rows('lots')}
    statements = []
    ledger.connection.set_trace_callback(statements.append)
    try:
        assert ledger.apply(value)['status'] == 'APPLIED'
    finally:
        ledger.connection.set_trace_callback(None)
    assert not any(re.search(r'\bSELECT\b.*\bFROM\s+tax_lots\s+WHERE\s+id\s*=', sql, re.I)
                   for sql in statements), 'Known account ownership needs no repeated global lookup'
    after = {row['id']: row for row in ledger.rows('lots')}
    assert set(after) == set(before)
    for lot_id, row in after.items():
        expected = dict(before[lot_id])
        if row['account_id'] == fixture.accounts[0]:
            expected['data_environment'] = 'SYNTHETIC'
        assert row == expected


def test_repeated_complete_and_partial_imports_preserve_inventory_and_other_account(fixture):
    ledger = fixture.ledger
    original = {table: ledger.rows(table) for table in ('positions', 'lots', 'cash_balances')}
    other = {table: [row for row in rows if row['account_id'] == fixture.accounts[1]]
             for table, rows in original.items()}
    original_lots = {row['id']: row for row in original['lots']}
    complete_seen = False
    for complete in (False, True, False):
        complete_seen |= complete
        value = candidate(fixture.snapshots[0], 'repeat-' + str(complete), complete=complete)
        assert ledger.apply(value)['status'] in {'APPLIED', 'UNCHANGED'}
        assert ledger.apply(value)['status'] == 'UNCHANGED'
        for table, rows in other.items():
            assert [row for row in ledger.rows(table)
                    if row['account_id'] == fixture.accounts[1]] == rows
        for lot in ledger.rows('lots'):
            expected = dict(original_lots[lot['id']])
            if complete_seen and lot['account_id'] == fixture.accounts[0]:
                expected['data_environment'] = 'SYNTHETIC'
            assert lot == expected
        assert all(row['quantity'] == '10' and row['cost_basis'] == '1200'
                   and row['lot_state'] == 'RESOLVED' for row in ledger.rows('positions'))
        assert [(row['id'], row['account_id'], row['amount'])
                for row in ledger.rows('cash_balances')] == [
                    (row['id'], row['account_id'], row['amount'])
                    for row in original['cash_balances']]
    # A later command must see actual writes to the second account, never a stale index.
    second = candidate(fixture.snapshots[1], 'second-account-later')
    second['cash'] = '10001'
    assert ledger.apply(second)['status'] == 'APPLIED'
    assert next(row for row in ledger.rows('cash_balances')
                if row['account_id'] == fixture.accounts[1])['amount'] == '10001'
    assert ledger.apply(candidate(fixture.snapshots[0], 'final-first'))['status'] == 'APPLIED'
    assert next(row for row in ledger.rows('cash_balances')
                if row['account_id'] == fixture.accounts[1])['amount'] == '10001'
