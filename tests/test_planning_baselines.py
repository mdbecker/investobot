import sqlite3

import pytest
from pytest_bdd import given, scenarios, then, when

from invest import plans
from invest.ledger import Ledger
from invest.models import DomainError

scenarios('features/planning_baselines.feature')


@pytest.fixture
def ctx(tmp_path):
    ledger = Ledger(tmp_path / 'fresh.db')
    yield {'ledger': ledger, 'path': tmp_path / 'old.db'}
    ledger.connection.close()


@given('a disposable household with large historical observations')
def household(ctx):
    ledger = ctx['ledger']
    ledger.apply({'account': {'id': 'ira', 'name': 'IRA', 'tax_status': 'TAX_FREE'},
                  'positions': [], 'cash': '100', 'source_hash': 'accepted',
                  'source_timestamp': '2026-10-08'})
    with ledger.connection:
        ledger.put('snapshots', 'old', {'id': 'old', 'account': {'id': 'ira'},
            'imported_at': '2020-01-01', 'source_timestamp': '2020-01-01',
            'positions': [{'payload': 'x' * 100000}]})


@when('its planning state is read')
def read(ctx):
    ctx['state'] = ctx['ledger'].planning_state()


@then('only compact latest observation provenance is included')
def compact(ctx):
    state = ctx['state']
    assert len(state['snapshots']) == 1
    assert 'positions' not in state['snapshots'][0]
    assert state['snapshots'][0]['source_timestamp'] == '2026-10-08'
    reversed_state = {key: list(reversed(value)) for key, value in state.items()}
    assert plans.state_hash(state) == plans.state_hash(reversed_state)
    assert ctx['ledger'].connection.execute('PRAGMA user_version').fetchone()[0] == 3


@when('two alternatives are saved from identical planning inputs')
def alternatives(ctx):
    from invest.plan_storage import save_plan
    state = ctx['ledger'].planning_state()
    ctx['state'] = state
    for identity in ('first', 'second'):
        save_plan(ctx['ledger'], {'id': identity, 'source_state': state,
            'source_state_hash': plans.state_hash(state), 'created_at': '2026-10-08',
            'as_of': '2026-10-08', 'status': 'REVIEW_REQUIRED',
            'assumptions': {'prices': {}, 'tax_rates': None}})


@then('one baseline and two snapshot-free details records exist')
def shared(ctx):
    connection = ctx['ledger'].connection
    assert connection.execute('SELECT count(*) FROM plan_baselines').fetchone()[0] == 1
    rows = connection.execute('SELECT details_json FROM plans').fetchall()
    assert len(rows) == 2
    assert all('source_state"' not in row[0] and 'snapshots"' not in row[0] for row in rows)


@then('a failed third insertion leaves no orphan baseline')
def atomic(ctx):
    from invest.plan_storage import save_plan
    state = dict(ctx['state'], activities=[{'id': 'new'}])
    with pytest.raises(sqlite3.IntegrityError):
        save_plan(ctx['ledger'], {'id': 'first', 'source_state': state,
            'source_state_hash': plans.state_hash(state), 'created_at': '2026-10-08',
            'as_of': '2026-10-08', 'status': 'REVIEW_REQUIRED', 'assumptions': {}})
    assert ctx['ledger'].connection.execute('SELECT count(*) FROM plan_baselines').fetchone()[0] == 1


@given('an incompatible version two database')
def old(ctx):
    with sqlite3.connect(ctx['path']) as connection:
        connection.execute('CREATE TABLE preserved (id TEXT)')
        connection.execute('PRAGMA user_version=2')


@when('it is opened')
def opened(ctx):
    try:
        Ledger(ctx['path'])
    except DomainError as error:
        ctx['error'] = error


@then('reset instructions are reported without destroying data')
def rejected(ctx):
    assert ctx['error'].code == 3
    assert 'reset' in str(ctx['error']).lower()
    with sqlite3.connect(ctx['path']) as connection:
        assert connection.execute('PRAGMA user_version').fetchone()[0] == 2
        connection.execute('SELECT * FROM preserved')
