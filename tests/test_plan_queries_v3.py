import copy
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from pytest_bdd import given, scenarios, then, when

from invest import plans
from invest.ledger import Ledger
from invest.plan_storage import load_plan, save_plan

scenarios('features/plan_queries_v3.feature')


@pytest.fixture
def ctx(tmp_path):
    ledger = Ledger(tmp_path / 'synthetic.db')
    yield {'ledger': ledger}
    ledger.connection.set_authorizer(None)
    ledger.connection.close()


def alternative(identity, state):
    return {'id': identity, 'name': identity, 'source_state': state,
            'source_state_hash': plans.state_hash(state),
            'created_at': '2026-10-08T12:00:00', 'as_of': '2026-10-08',
            'status': 'REVIEW_REQUIRED', 'trade_count': 1, 'turnover': '12.50',
            'proposed_actions': [{'type': 'BUY', 'quantity': '1.25'}],
            'tax_analysis': {'short_term_gain_loss': '0', 'long_term_gain_loss': '2',
                             'estimated_tax_effect': '.4'},
            'remaining_target_drift': [{'difference_weight': '.02'}],
            'target': {'planning_constraints': {'target_tolerance': '.01'}},
            'warnings': ['Synthetic review'],
            'assumptions': {'prices': {'00123': '10'}, 'tax_rates': {}}}


@given('a disposable schema three household with two saved alternatives')
def household(ctx):
    ledger = ctx['ledger']
    ledger.apply({'account': {'id': '00123', 'name': 'Synthetic IRA',
                             'tax_status': 'TAX_FREE'},
                  'positions': [], 'cash': '100', 'source_hash': 'accepted',
                  'source_timestamp': '2026-10-08'})
    ctx['state'] = ledger.planning_state()
    ctx['original'] = alternative('first', ctx['state'])
    for identity in ('first', 'second'):
        save_plan(ledger, alternative(identity, ctx['state']))


@when('plan list and comparison run with payload reads forbidden')
def guarded_queries(ctx, monkeypatch):
    ledger = ctx['ledger']
    calls = []
    original = plans.state_hash

    def counted(state):
        calls.append(state)
        return original(state)

    def authorize(action, table, column, database, trigger):
        if action == sqlite3.SQLITE_READ and (
            (table == 'plans' and column == 'details_json') or
            (table == 'plan_baselines' and column == 'state_json')
        ):
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    monkeypatch.setattr(plans, 'state_hash', counted)
    ledger.connection.set_authorizer(authorize)
    ctx['listed'] = plans.list_plans(ledger)
    ctx['list_hashes'] = len(calls)
    ctx['compared'] = plans.compare(ledger, 'first', 'second')
    ctx['compare_hashes'] = len(calls) - ctx['list_hashes']
    ledger.connection.set_authorizer(None)


@then('summaries preserve saved metrics and hash the household once per request')
def summaries(ctx):
    assert ctx['list_hashes'] == ctx['compare_hashes'] == 1
    assert [row['id'] for row in ctx['listed']['plans']] == ['second', 'first']
    compared = ctx['compared']
    assert [row['id'] for row in compared['plans']] == ['first', 'second']
    assert compared['same_source_snapshot'] is True
    assert compared['same_price_assumptions'] is True
    for summary in ctx['listed']['plans'] + compared['plans']:
        assert summary['status'] == summary['generated_status'] == 'REVIEW_REQUIRED'
        assert summary['turnover'] == '12.50'
        assert summary['tax_summary']['estimated_tax_effect'] == '.4'
        assert summary['drift_summary']['positions_outside_tolerance'] == 1
        assert 'source_state' not in summary
        assert 'proposed_actions' not in summary


@then('list ordering and selected lookup use SQLite indexes')
def indexed(ctx):
    connection = ctx['ledger'].connection
    listing = connection.execute('EXPLAIN QUERY PLAN SELECT summary_json FROM plans '
                                 'ORDER BY created_at DESC, id DESC').fetchall()
    lookup = connection.execute('EXPLAIN QUERY PLAN SELECT details_json FROM plans '
                                'WHERE id=?', ('first',)).fetchall()
    assert any('plans_created_idx' in row[3] for row in listing)
    assert not any('TEMP B-TREE' in row[3] for row in listing)
    assert any('SEARCH plans USING INDEX' in row[3] for row in lookup)


@when('the first saved plan is retrieved after current cash changes')
def retrieve(ctx):
    ledger = ctx['ledger']
    ctx['before'] = load_plan(ledger, 'first')
    with ledger.connection:
        cash = ledger.rows('cash_balances')[0]
        cash['amount'] = '101'
        ledger.put('cash_balances', cash['id'], cash)
        # An unrelated corrupt detail must never be decoded by selected retrieval.
        ledger.connection.execute("UPDATE plans SET details_json='invalid-json' WHERE id='second'")
    ctx['retrieved'] = load_plan(ledger, 'first')
    ctx['shown'] = plans.show(ledger, 'first')


@then('its full details and source state remain unchanged')
def preserved(ctx):
    assert ctx['retrieved'] == ctx['before'] == ctx['original']
    assert ctx['shown']['status'] == 'STALE'
    assert ctx['shown']['source_state'] == ctx['state']
    assert ctx['shown']['proposed_actions'] == ctx['original']['proposed_actions']


@when('an older large observation is added and planning reads are guarded')
def old_history(ctx, monkeypatch):
    ledger = ctx['ledger']
    with ledger.connection:
        ledger.put('snapshots', 'old', {'id': 'old', 'account': {'id': '00123'},
            'imported_at': '2020-01-01', 'source_timestamp': '2020-01-01',
            'positions': [{'irrelevant': 'x' * 100000}]})
    original = ledger.rows

    def guarded(table):
        assert table != 'snapshots', 'Planning decoded full historical observation rows'
        return original(table)

    monkeypatch.setattr(ledger, 'rows', guarded)
    ctx['current'] = ledger.planning_state()


@then('the planning fingerprint stays unchanged and no snapshot rows are decoded')
def compact_state(ctx):
    assert plans.state_hash(ctx['current']) == plans.state_hash(ctx['state'])
    assert len(ctx['current']['snapshots']) == 1
    assert 'positions' not in ctx['current']['snapshots'][0]


@then('financial decimal spelling is normalized while identifiers and provenance matter')
def hash_semantics(ctx):
    state = ctx['current']
    equivalent = copy.deepcopy(state)
    equivalent['cash_balances'][0]['amount'] = '100.0000'
    assert plans.state_hash(equivalent) == plans.state_hash(state)
    renamed = copy.deepcopy(state)
    renamed['accounts'][0]['id'] = '123'
    assert plans.state_hash(renamed) != plans.state_hash(state)
    unknown = copy.deepcopy(state)
    unknown['snapshots'][0]['source_timestamp'] = None
    assert plans.state_hash(unknown) != plans.state_hash(state)
    incomplete = copy.deepcopy(state)
    incomplete['snapshots'][0]['positions_complete'] = not state['snapshots'][0]['positions_complete']
    assert plans.state_hash(incomplete) != plans.state_hash(state)


@when('independent connections concurrently save two more alternatives')
def concurrent(ctx):
    barrier = Barrier(2)

    def persist(identity):
        ledger = Ledger(ctx['ledger'].path)
        try:
            barrier.wait(timeout=5)
            save_plan(ledger, alternative(identity, ctx['state']))
        finally:
            ledger.connection.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(persist, ['third', 'fourth']))


@then('all alternatives reference one complete baseline')
def shared_baseline(ctx):
    connection = ctx['ledger'].connection
    assert connection.execute('SELECT count(*) FROM plan_baselines').fetchone()[0] == 1
    assert connection.execute('SELECT count(*) FROM plans').fetchone()[0] == 4
    assert connection.execute('PRAGMA foreign_key_check').fetchall() == []
    for identity in ('first', 'second', 'third', 'fourth'):
        assert load_plan(ctx['ledger'], identity) == alternative(identity, ctx['state'])
