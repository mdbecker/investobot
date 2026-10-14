import sqlite3

import pytest
from pytest_bdd import given, scenarios, then, when

from invest.ledger import Ledger
from invest.plans import list_plans, state_hash

scenarios('features/performance_verification.feature')


@pytest.fixture
def ctx(tmp_path):
    ledger = Ledger(tmp_path / 'benchmark.db')
    yield {'ledger': ledger, 'directory': tmp_path}
    ledger.connection.close()


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
