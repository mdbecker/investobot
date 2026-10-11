from decimal import Decimal

import pytest
from pytest_bdd import given, scenarios, then, when

from invest.ledger import Ledger
from invest.models import DomainError

scenarios('features/activity_v2.feature')


@pytest.fixture
def ctx(tmp_path):
    return {'ledger': Ledger(tmp_path / 'db')}


@given('a dated taxable position with two lots')
def accepted(ctx):
    ctx['ledger'].apply({
        'account': {'id': 'a', 'name': 'Synthetic'},
        'positions': [{'security': 'AAA', 'quantity': '10', 'market_value': '1000',
                       'price': '100', 'cost_basis': '800', 'as_of': '2026-10-08', 'displayed_price_precision': 0, 'displayed_market_value_precision': 0}],
        'lots': [{'id': name, 'security': 'AAA', 'quantity': '5', 'remaining_quantity': '5',
                  'cost_basis': basis, 'acquisition_date': acquired}
                 for name, basis, acquired in [('old', '300', '2024-01-01'),
                                               ('new', '500', '2026-09-01')]],
        'cash': '1000', 'source_hash': 'activity-fixture', 'source_timestamp': '2026-10-08',
        'positions_complete': True, 'lots_complete': True})
    ctx['activity'] = {'activity_id': 'executed-1', 'account_id': 'a', 'security': 'AAA',
                       'type': 'BUY', 'quantity': '2', 'price': '120', 'fee': '1',
                       'date': '2026-10-08', 'source': 'human confirmation'}
    ctx['before'] = ctx['ledger'].state()


def record(ctx):
    try:
        ctx['result'] = ctx['ledger'].record_activity(ctx['activity'], yes=True)
    except DomainError as exc:
        ctx['error'] = exc


@when('a partial sale selects the newer lot')
def explicit(ctx):
    ctx['activity'].update(type='SELL', lot_allocations=[{'lot_id': 'new', 'quantity': '2'}])
    record(ctx)


@then('only the newer lot decreases and remaining valuation uses the accepted market price')
def remaining(ctx):
    state = ctx['ledger'].state()
    assert {l['id']: l['remaining_quantity'] for l in state['lots']} == {'old': '5', 'new': '3'}
    assert state['positions'][0]['price'] == '100'
    assert Decimal(state['positions'][0]['market_value']) == 800
    assert Decimal(state['positions'][0]['cost_basis']) == 600
    assert Decimal(state['cash_balances'][0]['amount']) == 1239


@when('a confirmed sale has no lot allocations')
def unknown(ctx):
    ctx['activity']['type'] = 'SELL'
    record(ctx)


@then('shares and cash update but lots remain unresolved')
def unresolved(ctx):
    state = ctx['ledger'].state()
    assert state['positions'][0]['quantity'] == '8'
    assert state['positions'][0]['lot_state'] == 'UNRESOLVED'
    assert state['positions'][0]['cost_basis'] is None
    assert state['lots'] == ctx['before']['lots']


@when('the same confirmed purchase is recorded twice')
def duplicate(ctx):
    record(ctx)
    record(ctx)


@then('only one purchase changes shares and cash')
def once(ctx):
    state = ctx['ledger'].state()
    assert len(state['activities']) == 1
    assert state['positions'][0]['quantity'] == '12'
    assert Decimal(state['cash_balances'][0]['amount']) == 759


@when('an existing activity ID is reused with different content')
def conflicting(ctx):
    record(ctx)
    ctx['before'] = ctx['ledger'].state()
    ctx['activity']['quantity'] = '3'
    record(ctx)


@then('the activity conflict leaves state unchanged')
def atomic(ctx):
    assert isinstance(ctx.get('error'), DomainError)
    assert ctx['ledger'].state() == ctx['before']


@when('a purchase with fees executes above market price')
def buy(ctx):
    record(ctx)


@then('basis includes fees and market valuation preserves the accepted price')
def valuation(ctx):
    p = ctx['ledger'].state()['positions'][0]
    assert Decimal(p['cost_basis']) == 1041
    assert p['price'] == '100'
    assert Decimal(p['market_value']) == 1200


@when('a purchase is confirmed without an activity ID')
def no_id(ctx):
    del ctx['activity']['activity_id']
    record(ctx)


@when('sale allocations do not equal sold shares')
def incorrect(ctx):
    ctx['activity'].update(type='SELL', lot_allocations=[{'lot_id': 'new', 'quantity': '1'}])
    record(ctx)


@when('an unclassified security transfer is confirmed')
def transfer(ctx):
    ctx['activity']['type'] = 'TRANSFER_OUT'
    record(ctx)
