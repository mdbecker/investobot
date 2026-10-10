import copy
import json
import sqlite3

import pytest
from pytest_bdd import given, scenarios, then, when
from test_earnings_models import package

from invest.ledger import Ledger
from invest.models import DomainError

scenarios('features/earnings_storage.feature')


@pytest.fixture
def ctx(tmp_path):
    db = Ledger(tmp_path / 'research.db')
    yield {'db': db, 'path': tmp_path / 'research.db', 'package': package()}
    db.connection.close()


@given('a fictional validated earnings package and a fresh ledger')
def fictional(ctx):
    ctx['before'] = ctx['db'].planning_state()
    ctx['bytes'] = ctx['path'].read_bytes()


@when('earnings import is previewed')
def preview(ctx):
    from invest.earnings import import_research
    ctx['preview'] = import_research(ctx['db'], ctx['package'])


@then('no persistent bytes or financial state change')
def no_change(ctx):
    assert not ctx['preview']['committed']
    assert ctx['bytes'] == ctx['path'].read_bytes()
    assert ctx['db'].planning_state() == ctx['before']


@when('earnings are confirmed and equivalent reordered input is confirmed again')
def confirm(ctx):
    from invest.earnings import import_research
    ctx['first'] = import_research(ctx['db'], ctx['package'], yes=True)
    reordered = copy.deepcopy(ctx['package'])
    reordered['metrics'][0]['value'] = '1250000000.00000'
    reordered['sources'].reverse()
    reordered = dict(reversed(list(reordered.items())))
    ctx['second'] = import_research(ctx['db'], reordered, yes=True)


@then('one immutable source-backed run exists with trusted skill provenance')
def immutable(ctx):
    assert ctx['first']['research_run_id'] == ctx['second']['research_run_id']
    assert ctx['first']['committed'] and ctx['second']['status'] == 'UNCHANGED'
    conn = ctx['db'].connection
    row = conn.execute('SELECT skill_name,skill_version,package_json FROM research_runs').fetchone()
    assert row[:2] == ('investobot-earnings', '1.0.0')
    assert json.loads(row[2])['metrics'][0]['value'] == '1250000000'
    assert conn.execute('SELECT COUNT(*) FROM research_earnings_metrics').fetchone()[0] == 1
    assert conn.execute('PRAGMA foreign_key_check').fetchall() == []
    assert ctx['db'].planning_state() == ctx['before']


def test_schema_five_rejects_four_without_reset(tmp_path):
    current = Ledger(tmp_path / 'fresh.db')
    assert current.connection.execute('PRAGMA user_version').fetchone()[0] == 5
    current.connection.close()
    old = tmp_path / 'schema-four.db'
    with sqlite3.connect(old) as connection:
        connection.execute('PRAGMA user_version=4')
        connection.execute('CREATE TABLE sentinel (id TEXT)')
    before = old.read_bytes()
    with pytest.raises(DomainError) as error:
        Ledger(old)
    assert error.value.code == 3
    assert old.read_bytes() == before


def test_storage_rollback_and_cross_run_source_integrity(ctx):
    from invest.earnings import import_research
    conn = ctx['db'].connection
    first = import_research(ctx['db'], ctx['package'], yes=True)
    modified = copy.deepcopy(ctx['package'])
    modified['limitations'].append('Independent second research run.')
    second = import_research(ctx['db'], modified, yes=True)
    before = conn.execute('SELECT COUNT(*) FROM research_runs').fetchone()[0]
    with conn:
        conn.execute("CREATE TRIGGER refuse_metrics BEFORE INSERT ON research_earnings_metrics BEGIN SELECT RAISE(ABORT,'synthetic failure'); END")
    modified['limitations'].append('Fail atomically.')
    with pytest.raises(sqlite3.IntegrityError):
        import_research(ctx['db'], modified, yes=True)
    assert conn.execute('SELECT COUNT(*) FROM research_runs').fetchone()[0] == before
    assert conn.execute('SELECT COUNT(*) FROM research_sources').fetchone()[0] == before
    with conn:
        conn.execute('DROP TRIGGER refuse_metrics')
        conn.execute('DELETE FROM research_earnings_metrics WHERE run_id=?', (second['research_run_id'],))
        conn.execute('DELETE FROM research_sources WHERE run_id=?', (second['research_run_id'],))
    with pytest.raises(sqlite3.IntegrityError), conn:
        conn.execute('UPDATE research_earnings_metrics SET run_id=? WHERE run_id=?',
                     (second['research_run_id'], first['research_run_id']))
    assert conn.execute('PRAGMA foreign_key_check').fetchall() == []


def test_research_preserves_real_saved_plan(ctx):
    from test_storage_stabilization import snapshot

    from invest.earnings import import_research
    from invest.market import MarketClient
    from invest.plans import generate, show
    from invest.targets import save
    db = ctx['db']
    db.apply(snapshot(10, 'synthetic-original', '2026-10-08'))
    security = db.resolve('SYN')['id']
    target = save(db, {'name': 'Synthetic allocation',
        'target_allocations': {security: '.5', 'CASH': '.5'},
        'planning_constraints': {'eligible_accounts': ['ira'], 'permitted_securities': {'ira': [security]}}})
    plan = generate(db, MarketClient(db, fixture_path='tests/fixtures/fmp-synthetic.json'),
                    target['id'], as_of='2026-10-08')
    state = copy.deepcopy(db.planning_state())
    saved = copy.deepcopy(show(db, plan['id']))
    import_research(db, ctx['package'], yes=True)
    assert db.planning_state() == state
    assert show(db, plan['id']) == saved


def test_unknown_or_contradictory_security_rejected_without_research(ctx):
    from invest.earnings import import_research
    ctx['package']['company']['security_id'] = 'missing'
    with pytest.raises(DomainError):
        import_research(ctx['db'], ctx['package'], yes=True)
    sec = ctx['db'].register_security({'ticker': 'UNRELATED', 'name': 'Another issuer',
                                      'asset_type': 'STOCK', 'currency': 'USD', 'source': 'Synthetic'})
    ctx['package']['company']['security_id'] = sec['id']
    with pytest.raises(DomainError):
        import_research(ctx['db'], ctx['package'], yes=True)
    assert ctx['db'].connection.execute('SELECT COUNT(*) FROM research_runs').fetchone()[0] == 0
