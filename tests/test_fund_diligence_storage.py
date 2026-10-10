"""Fund research storage boundaries with disposable, fictional ledgers only."""

import importlib
import json
import sqlite3
from pathlib import Path

import pytest

from invest.ledger import Ledger
from invest.models import DomainError
from invest.research_identity import read_ledger


@pytest.fixture
def payload():
    return json.loads((Path(__file__).parent / 'fixtures/fund_diligence.json').read_text())


def module(name):
    assert importlib.util.find_spec('invest.' + name), 'Required fund diligence behavior missing'
    return importlib.import_module('invest.' + name)


def test_fresh_schema_ten_and_schema_nine_preservation(tmp_path):
    path = tmp_path / 'old.db'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE private_data (value TEXT)')
        db.execute("INSERT INTO private_data VALUES ('preserve')")
        db.execute('PRAGMA user_version=9')
    before = path.read_bytes()
    with pytest.raises(DomainError) as error:
        Ledger(path)
    assert error.value.code == 3
    with pytest.raises(DomainError):
        with read_ledger(path):
            pass
    assert path.read_bytes() == before
    fresh = Ledger(tmp_path / 'new.db')
    assert fresh.connection.execute('PRAGMA user_version').fetchone()[0] == 10
    fresh.connection.close()


def test_failure_rolls_back_all_research_tables(tmp_path, payload):
    funds = module('fund_diligence')
    db = Ledger(tmp_path / 'new.db')
    with db.connection:
        db.connection.execute("CREATE TRIGGER fail_fund BEFORE INSERT ON research_fund_findings "
                              "BEGIN SELECT RAISE(ABORT, 'fictional failure'); END")
    with pytest.raises(sqlite3.IntegrityError):
        funds.import_research(db, payload, yes=True)
    for table in ['research_runs', 'research_sources', 'research_fund_profiles',
                  'research_fund_holdings', 'research_fund_metrics', 'research_fund_findings']:
        assert db.connection.execute(f'SELECT count(*) FROM {table}').fetchone()[0] == 0
    db.connection.close()


def test_compact_reports_do_not_read_packages_and_foreign_keys_are_run_scoped(tmp_path, payload):
    funds, queries = module('fund_diligence'), module('fund_diligence_queries')
    db = Ledger(tmp_path / 'new.db')
    first = funds.import_research(db, payload, yes=True)['run_id']
    payload['sources'][0]['id'] = 'other-identity'
    payload['limitations'].append('Second independent review')
    second = funds.import_research(db, payload, yes=True)['run_id']
    with pytest.raises(sqlite3.IntegrityError), db.connection:
        db.connection.execute('UPDATE research_fund_metrics SET source_id=? WHERE run_id=?',
                              ('other-identity', first))

    def authorize(action, table, column, *_):
        if action == sqlite3.SQLITE_READ and table == 'research_runs' and column == 'package_json':
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    db.connection.set_authorizer(authorize)
    assert len(queries.list_runs(db)['runs']) == 2
    assert queries.summary(db, first)
    assert queries.holdings(db, second)
    db.connection.close()


def test_tiny_plain_decimals_hash_identically_without_magnitude_loss(payload):
    funds = module('fund_diligence')
    payload['holdings_snapshot']['coverage'] = 'PARTIAL'
    payload['metrics'][0]['value'] = '0.000000000000000000000000000000000012300'
    data, _, run, _ = funds.canonical_package(payload)
    assert data['metrics'][0]['value'] == '0.0000000000000000000000000000000000123'
    payload['metrics'][0]['value'] = data['metrics'][0]['value']
    payload['sources'].reverse()
    payload['holdings'].reverse()
    assert funds.canonical_package(payload)[2] == run
