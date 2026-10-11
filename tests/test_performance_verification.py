import runpy
import sqlite3
from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from invest.ledger import Ledger
from invest.market import MarketClient
from invest.plan_storage import load_plan, summaries
from invest.plans import generate, list_plans, state_hash
from invest.reports import export

scenarios('features/performance_verification.feature')


@pytest.fixture
def ctx(tmp_path):
    ledger = Ledger(tmp_path / 'benchmark.db')
    yield {'ledger': ledger, 'directory': tmp_path}
    ledger.connection.close()


@given('the disposable benchmark contains the required synthetic household')
def household(ctx):
    script = Path(__file__).resolve().parents[1] / 'scripts' / 'benchmark_plan_storage.py'
    ctx['benchmark'] = runpy.run_path(str(script))
    ctx['fixture'] = ctx['benchmark']['build_fixture'](ctx['ledger'])
    state = ctx['ledger'].state()
    assert {key: len(state[key]) for key in ('accounts', 'positions', 'lots', 'snapshots')} == {
        'accounts': 10, 'positions': 1000, 'lots': 2000, 'snapshots': 200}
    ctx['accepted_state'] = state


@when('its twenty alternative plans are measured')
def measured(ctx):
    ctx['result'] = ctx['benchmark']['measure'](
        ctx['ledger'], ctx['fixture'], ctx['directory'])
    assert ctx['ledger'].state() == ctx['accepted_state']


@then('the measurement reports one baseline and separate stored JSON sizes')
def storage(ctx):
    result = ctx['result']
    assert result['baseline_count'] == 1
    assert result['plan_count'] == 20
    for key in ('average_baseline_json_bytes', 'average_summary_json_bytes',
                'average_details_json_bytes'):
        assert result[key] > 0


@then('plan storage growth is below forty four MiB with compact responses')
def small(ctx):
    result = ctx['result']
    assert 0 < result['database_growth_bytes'] < 44 * 1024 * 1024
    assert result['listed_response_bytes'] < 128 * 1024
    assert result['compared_response_bytes'] < 128 * 1024
    assert result['listed_plan_count'] == result['compared_plan_count'] == 20


@then('planning persistence and query verification measurements are available')
def timings(ctx):
    result = ctx['result']
    for key in ('planning_seconds', 'persistence_seconds', 'generation_seconds',
                'list_seconds', 'compare_seconds', 'retrieve_seconds', 'markdown_export_seconds'):
        assert result[key] >= 0
    assert result['planning_seconds'] + result['persistence_seconds'] == pytest.approx(
        result['generation_seconds'])
    queries = result['query_plans']
    assert set(queries) == {'list', 'compare', 'plan_lookup', 'baseline_lookup'}
    assert any('plans_created_idx' in line for line in queries['list'])
    assert any('INDEX' in line for line in queries['plan_lookup'])
    assert any('INDEX' in line for line in queries['baseline_lookup'])


@then('two selected historical reports survive a confirmed cash change')
def reproducible(ctx):
    ledger = ctx['ledger']
    rows = summaries(ledger)
    selected = [load_plan(ledger, row['id']) for row in rows[:2]]
    originals = []
    for index, plan in enumerate(selected):
        path = ctx['directory'] / f'selected-{index}.md'
        export(plan, path)
        originals.append(path.read_bytes())
    ledger.record_activity({'activity_id': 'synthetic-performance-deposit',
                            'account_id': ctx['fixture']['account_ids'][0],
                            'type': 'CASH_DEPOSIT', 'amount': '10', 'date': '2026-10-08'},
                           yes=True)
    assert all(plan['status'] == 'STALE' for plan in list_plans(ledger)['plans'])
    for index, plan in enumerate(selected):
        path = ctx['directory'] / f'selected-{index}-after.md'
        export(load_plan(ledger, plan['id']), path)
        assert path.read_bytes() == originals[index]
    new = generate(ledger, MarketClient(ledger, fixture_path=Path(
        'tests/fixtures/fmp-synthetic.json')), selected[0]['target']['id'], as_of='2026-10-08')
    assert new['source_state_hash'] != selected[0]['source_state_hash']
    assert ledger.connection.execute('SELECT COUNT(*) FROM plan_baselines').fetchone()[0] == 2


@given('a small saved synthetic alternative')
def small_saved(ctx):
    from invest.plan_storage import save_plan
    ledger = ctx['ledger']
    ledger.apply({'data_environment': 'SYNTHETIC', 'account': {'id': 'ira', 'name': 'Synthetic', 'tax_status': 'TAX_FREE'},
                  'positions': [{'security': 'SYN', 'asset_type': 'STOCK', 'quantity': '1',
                                 'price': '100', 'market_value': '100',
                                 'displayed_price_precision': 0,
                                 'displayed_market_value_precision': 0}],
                  'cash': '100', 'source_timestamp': '2026-10-08', 'source_hash': 'synthetic'})
    state = ledger.planning_state()
    ctx['fingerprint'] = state_hash(state)
    save_plan(ledger, {'id': 'synthetic-plan', 'source_state': state,
                      'source_state_hash': ctx['fingerprint'], 'created_at': '2026-10-08',
                      'as_of': '2026-10-08', 'status': 'REVIEW_REQUIRED', 'assumptions': {}})


@when('SQLite disallows comparison-only assumption hash reads')
def deny_hashes(ctx):
    def authorizer(action, table, column, database, trigger):
        if action == sqlite3.SQLITE_READ and table == 'plans' and column in {
            'price_assumptions_hash', 'tax_assumptions_hash'}:
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK
    ctx['ledger'].connection.set_authorizer(authorizer)


@then('listing the alternative still succeeds')
def listing(ctx):
    try:
        assert list_plans(ctx['ledger'])['plans'][0]['id'] == 'synthetic-plan'
    finally:
        ctx['ledger'].connection.set_authorizer(None)


@when('only account and security audit histories are appended')
def audit(ctx):
    ledger = ctx['ledger']
    with ledger.connection:
        for table, field in (('accounts', 'metadata_history'),
                             ('securities', 'classification_history')):
            row = ledger.rows(table)[0]
            row[field] = [{'changed_at': '2026-10-08', 'source': 'synthetic audit annotation'}]
            ledger.put(table, row['id'], row)


@then('its planning fingerprint and saved status remain current')
def current(ctx):
    state = ctx['ledger'].planning_state()
    assert state_hash(state) == ctx['fingerprint']
    assert all('metadata_history' not in row for row in state['accounts'])
    assert all('classification_history' not in row for row in state['securities'])
    assert list_plans(ctx['ledger'])['plans'][0]['status'] == 'REVIEW_REQUIRED'


@given('financial states containing large exact decimal cash balances')
def precise(ctx):
    ctx['decimal_states'] = [
        {'cash_balances': [{'id': 'ira', 'amount': amount}]}
        for amount in ('123456789012345678901234567890.01',
                       '123456789012345678901234567890.02',
                       '123456789012345678901234567890.0100')]


@then('distinct final cents have distinct fingerprints and trailing zeros do not')
def lossless(ctx):
    first, second, equivalent = [state_hash(state) for state in ctx['decimal_states']]
    assert first != second
    assert first == equivalent
