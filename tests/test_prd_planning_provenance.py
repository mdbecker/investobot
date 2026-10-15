"""Planning provenance and immutable calculation identity use public ledger facts."""

import copy
import json

import pytest

from invest.backtest import run
from invest.db import SCHEMA_VERSION
from invest.ledger import Ledger
from invest.planning import propose, save_policy
from invest.targets import save


@pytest.fixture
def context(tmp_path):
    ledger = Ledger(tmp_path / 'fictional-provenance.db')
    ledger.apply({
        'account': {'id': 'fictional', 'name': 'Fictional provenance contract account',
                    'tax_status': 'TAX_FREE', 'history_complete': True},
        'positions': [{'security': 'FICTION', 'name': 'Fictional provenance security',
                       'asset_type': 'STOCK', 'quantity': '1', 'price': '100',
                       'market_value': '100', 'displayed_price_precision': 2,
                       'displayed_market_value_precision': 2}],
        'lots': [], 'cash': '200', 'cash_known': True, 'positions_complete': True,
        'lots_complete': False, 'source_timestamp': '2026-10-09',
        'source_hash': 'fictional-real-label-contract-evidence', 'data_environment': 'REAL',
    })
    sid = ledger.resolve('FICTION')['id']
    policy = save_policy(ledger, {
        'version': 'fictional-approved-1', 'data_environment': 'REAL',
        'source': 'Human reviewed fictional policy fixture; REAL label exercises isolation only',
        'minimum_notional': '25', 'fee_per_trade': '0', 'cash_floors': {'fictional': '0'},
        'permissions': {'fictional': {sid: {'can_buy': True, 'can_sell': False,
                                           'can_hold': True, 'share_increment': '1'}}},
    }, confirm=True)
    yield {'ledger': ledger, 'sid': sid, 'policy': policy['id']}
    ledger.connection.close()


def target(ctx, *, environment='REAL', sid=None):
    identity = sid or ctx['sid']
    return save(ctx['ledger'], {
        'name': 'Fictional provenance target', 'data_environment': environment,
        'target_allocations': {identity: '1'},
        'planning_constraints': {'eligible_accounts': ['fictional']},
    })['id']


def price():
    return {'price': '100', 'as_of': '2026-10-10', 'currency': 'USD',
            'data_environment': 'REAL', 'source': 'Reviewed fictional source price',
            'manifest_id': 'fictional-explicit-price-source'}


def assert_blocked(ctx, target_id, prices, code):
    before = copy.deepcopy(ctx['ledger'].state())
    result = propose(ctx['ledger'], target_id, policy=ctx['policy'],
                     mode='contributions-only', as_of='2026-10-10', prices=prices)
    assert ctx['ledger'].state() == before
    assert result['status'] == 'BLOCKED'
    assert result['proposed_actions'] == []
    assert code in {issue['code'] for issue in result['issues']}
    return result


def test_confirmed_unmarked_purchase_returns_typed_missing_mark_outcome(context):
    ledger = context['ledger']
    ledger.register_security({'ticker': 'UNMARKED', 'name': 'Fictional unmarked stock',
                              'asset_type': 'STOCK', 'currency': 'USD',
                              'source': 'Reviewed fictional security identity'})
    ledger.record_activity({'activity_id': 'fictional-unmarked-buy', 'account_id': 'fictional',
                            'type': 'BUY', 'security': 'UNMARKED', 'quantity': '1',
                            'price': '10', 'fee': '0', 'date': '2026-10-10'}, yes=True)
    position = next(row for row in ledger.rows('positions') if row['security'] == 'UNMARKED')
    assert position['market_value'] is None
    # A purchase price remains execution evidence, not a fresh valuation checkpoint.
    assert_blocked(context, target(context), {context['sid']: price()}, 'MISSING_VALUATION_MARK')


def test_synthetic_target_cannot_cross_into_real_approved_proposal(context):
    assert_blocked(context, target(context, environment='SYNTHETIC'),
                   {context['sid']: price()}, 'MIXED_DATA_ENVIRONMENT')


@pytest.mark.parametrize('missing', ['currency', 'data_environment'])
def test_approved_price_observation_needs_explicit_currency_and_environment(context, missing):
    observation = price()
    observation.pop(missing)
    assert_blocked(context, target(context), {context['sid']: observation}, 'UNKNOWN_PRICE_PROVENANCE')


def test_persisted_backtest_pins_foundation_schema_identity(context):
    ledger, sid = context['ledger'], context['sid']
    before = copy.deepcopy(ledger.state())
    result = run(ledger, portfolio={sid: '1'}, start='2026-10-01', end='2026-10-02',
                 policy={'starting_value': '1000', 'cash_return': '0', 'fee_per_trade': '0'},
                 manifest={'id': 'fictional-history-identity', 'data_environment': 'REAL',
                           'sessions': ['2026-10-01', '2026-10-02'], 'series': {sid: [
                               {'date': '2026-10-01', 'total_return_index': '100'},
                               {'date': '2026-10-02', 'total_return_index': '101'}]}})
    assert ledger.state() == before
    stored = json.loads(ledger.connection.execute(
        'SELECT result_json FROM backtest_runs WHERE id=?', (result['id'],)).fetchone()[0])
    checksum = ledger.connection.execute(
        "SELECT checksum FROM schema_migrations WHERE id='001'").fetchone()[0]
    assert stored['storage_identity'] == {'schema_version': SCHEMA_VERSION, 'manifest_hash': checksum}
    assert result['storage_identity'] == stored['storage_identity']
