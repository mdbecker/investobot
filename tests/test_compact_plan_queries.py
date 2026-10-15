import copy
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from pytest_bdd import given, scenarios, then, when

from invest import plans
from invest.backup import logical_fingerprint
from invest.ledger import Ledger, snapshot_fingerprint
from invest.models import Snapshot
from invest.plan_storage import load_plan, save_plan

scenarios('features/compact_plan_queries.feature')


@pytest.fixture
def ctx(tmp_path):
    ledger = Ledger(tmp_path / 'synthetic.db')
    yield {'ledger': ledger}
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


@given('a fresh schema 1 household with two saved alternatives')
def household(ctx):
    ledger = ctx['ledger']
    ledger.apply({'data_environment': 'SYNTHETIC', 'account': {'id': '00123', 'name': 'Synthetic IRA',
                             'tax_status': 'TAX_FREE'},
                  'positions': [], 'cash_known': True, 'cash': '100', 'source_hash': 'accepted',
                  'source_timestamp': '2026-10-08'})
    ctx['state'] = ledger.planning_state()
    ctx['original'] = alternative('first', ctx['state'])
    ctx['original']['storage_identity'] = {
        'schema_version': 1, 'manifest_hash': ledger.connection.execute(
            "SELECT checksum FROM schema_migrations WHERE id='001'").fetchone()[0]}
    for identity in ('first', 'second'):
        save_plan(ledger, alternative(identity, ctx['state']))


@when('saved alternatives are listed and compared')
def compact_queries(ctx):
    ledger = ctx['ledger']
    before = logical_fingerprint(ledger.connection)
    ctx['listed'] = plans.list_plans(ledger)
    ctx['compared'] = plans.compare(ledger, 'first', 'second')
    assert logical_fingerprint(ledger.connection) == before
    assert load_plan(ledger, 'first') == ctx['original']


@then('compact ordered summaries preserve saved metrics without changing accepted facts')
def summaries(ctx):
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
        assert summary['warning_count'] == 1
        assert summary['warnings_preview'] == ['Synthetic review']
        assert 'source_state' not in summary
        assert 'proposed_actions' not in summary
    assert len(json.dumps(ctx['listed']).encode()) < 128 * 1024
    assert len(json.dumps(compared).encode()) < 128 * 1024


@when('the first saved plan is retrieved after current cash changes')
def retrieve(ctx):
    ledger = ctx['ledger']
    ctx['before'] = load_plan(ledger, 'first')
    with ledger.connection:
        cash = ledger.rows('cash_balances')[0]
        cash['amount'] = '101'
        ledger.put('cash_balances', cash['id'], cash)
        # An unrelated corrupt detail must never be decoded by selected retrieval.
        ledger.connection.execute("UPDATE plan_runs SET details_json='invalid-json' WHERE id='second'")
    ctx['accepted_before_inspection'] = logical_fingerprint(ledger.connection)
    ctx['retrieved'] = load_plan(ledger, 'first')
    ctx['shown'] = plans.show(ledger, 'first')


@then('its full details and source state remain unchanged')
def preserved(ctx):
    assert ctx['retrieved'] == ctx['before'] == ctx['original']
    assert ctx['shown']['status'] == 'STALE'
    assert ctx['shown']['source_state'] == ctx['state']
    assert ctx['shown']['proposed_actions'] == ctx['original']['proposed_actions']
    assert logical_fingerprint(ctx['ledger'].connection) == ctx['accepted_before_inspection']


@when('an older large observation is added')
def old_history(ctx):
    ledger = ctx['ledger']
    # Preserve a valid accepted observation shape; only its age and source lexeme differ.
    old = Snapshot.model_validate({
        'account': {'id': '00123', 'name': 'Synthetic IRA', 'tax_status': 'TAX_FREE'},
        'positions': [], 'cash_known': True, 'cash': '100',
        'source_timestamp': '2020-01-01', 'data_environment': 'SYNTHETIC',
        'source_hash': 'fictional-old-history-' + 'x' * 100000,
    }).model_dump(mode='json')
    old.update(fingerprint=snapshot_fingerprint(old), id='old', imported_at='2020-01-01')
    with ledger.connection:
        ledger.put('snapshots', 'old', old)
    ctx['current'] = ledger.planning_state()


@then('the planning fingerprint stays unchanged and current evidence stays compact')
def compact_state(ctx):
    assert plans.state_hash(ctx['current']) == plans.state_hash(ctx['state'])
    assert len(ctx['current']['snapshots']) == 1
    assert 'positions' not in ctx['current']['snapshots'][0]
    assert len(json.dumps(ctx['current']).encode()) < 128 * 1024


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
    assert connection.execute('SELECT count(*) FROM plan_runs').fetchone()[0] == 4
    assert connection.execute('PRAGMA foreign_key_check').fetchall() == []
    for identity in ('first', 'second', 'third', 'fourth'):
        expected = alternative(identity, ctx['state'])
        expected['storage_identity'] = ctx['original']['storage_identity']
        assert load_plan(ctx['ledger'], identity) == expected
