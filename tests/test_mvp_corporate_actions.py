"""Confirmed fictional corporate actions conserve cash, stable lots and basis."""

import copy
from decimal import Decimal

import pytest

from invest.ledger import Ledger
from invest.models import DomainError


@pytest.fixture
def ledger(tmp_path):
    instance = Ledger(tmp_path / 'fictional-corporate-actions.db')
    yield instance
    instance.connection.close()


def seed(ledger, *, first_basis='10', known_basis=True, complete_lots=True):
    bases = [first_basis, '20', '30'] if known_basis else [None, '20', '30']
    total = str(sum((Decimal(b) for b in bases), Decimal(0))) if known_basis else None
    lots = [{
        'id': f'lot-{index}', 'source_lot_id': f'broker-{index}',
        'identity_status': 'VERIFIED', 'identity_source': 'Reviewed fictional original broker lot',
        'security': 'FICTION', 'acquisition_date': f'2024-0{index + 1}-01',
        'quantity': '2', 'remaining_quantity': '1',
        'cost_basis': str(Decimal(basis) * 2) if basis is not None else None,
        'remaining_adjusted_basis': basis,
    } for index, basis in enumerate(bases)]
    ledger.apply({
        'account': {'id': 'taxable', 'name': 'Fictional corporate actions',
                    'tax_status': 'TAXABLE', 'history_complete': True},
        'positions': [{'security': 'FICTION', 'name': 'Fictional stock',
                       'asset_type': 'STOCK', 'quantity': '3', 'price': '100',
                       'market_value': '300', 'cost_basis': total,
                       'displayed_price_precision': 2, 'displayed_market_value_precision': 2}],
        'lots': lots, 'cash': '100', 'cash_known': True,
        'positions_complete': True, 'lots_complete': complete_lots,
        'source_timestamp': '2026-10-09', 'source_hash': 'fictional-reviewed-corporate-source',
        'data_environment': 'SYNTHETIC',
    })


def event(kind, **fields):
    return {'activity_id': 'fictional-' + kind, 'account_id': 'taxable', 'type': kind,
            'security': 'FICTION', 'date': '2026-10-10',
            'source': 'Reviewed fictional original corporate action notice', **fields}


def test_split_scales_original_and_remaining_quantities_without_resetting_lots(ledger):
    seed(ledger)
    before = copy.deepcopy(ledger.state())
    ledger.record_activity(event('STOCK_SPLIT', split_ratio='2'), yes=True)
    after = ledger.state()
    prior = {lot['id']: lot for lot in before['lots']}
    assert {lot['id'] for lot in after['lots']} == set(prior)
    for lot in after['lots']:
        old = prior[lot['id']]
        for key in ['source_lot_id', 'identity_status', 'identity_source', 'acquisition_date',
                    'cost_basis', 'remaining_adjusted_basis']:
            assert lot[key] == old[key]
        assert Decimal(lot['quantity']) == 4
        assert Decimal(lot['remaining_quantity']) == 2
    position = after['positions'][0]
    assert Decimal(position['quantity']) == 6
    assert Decimal(position['market_value']) == 300
    assert Decimal(position['cost_basis']) == 60
    assert position['source_timestamp'] == before['positions'][0]['source_timestamp']
    assert after['cash_balances'] == before['cash_balances']
    stored = after['activities'][0]
    assert stored['split_ratio'] == '2'


def test_reinvestment_fee_is_cash_expense_and_separate_acquisition_basis(ledger):
    seed(ledger)
    old_ids = {lot['id'] for lot in ledger.rows('lots')}
    ledger.record_activity(event('DIVIDEND_REINVESTMENT', amount='50', quantity='0.5',
                                 price='100', fee='2'), yes=True)
    state = ledger.state()
    assert Decimal(state['cash_balances'][0]['amount']) == 98
    assert Decimal(state['positions'][0]['quantity']) == Decimal('3.5')
    assert Decimal(state['positions'][0]['cost_basis']) == 112
    acquired = [lot for lot in state['lots'] if lot['id'] not in old_ids]
    assert len(acquired) == 1
    assert Decimal(acquired[0]['cost_basis']) == 52
    assert Decimal(acquired[0]['remaining_adjusted_basis']) == 52
    assert acquired[0]['acquisition_date'] == '2026-10-10'
    activity = state['activities'][0]
    assert activity['type'] == 'DIVIDEND_REINVESTMENT'
    assert activity['amount'] == '50' and activity['fee'] == '2' and activity['price'] == '100'
    assert not any(row['type'] in {'CASH_DEPOSIT', 'CASH_WITHDRAWAL'} for row in state['activities'])


def test_return_of_capital_conserves_allocated_basis_and_cash_exactly(ledger):
    seed(ledger)
    before = {lot['id']: lot for lot in ledger.rows('lots')}
    ledger.record_activity(event('RETURN_OF_CAPITAL', amount='21'), yes=True)
    state = ledger.state()
    assert Decimal(state['cash_balances'][0]['amount']) == 121
    assert Decimal(state['positions'][0]['cost_basis']) == 39
    assert Decimal(state['positions'][0]['quantity']) == 3
    assert sum((Decimal(lot['remaining_adjusted_basis']) for lot in state['lots']), Decimal(0)) == 39
    for lot in state['lots']:
        assert lot['id'] in before
        assert Decimal(lot['remaining_adjusted_basis']) == Decimal(before[lot['id']]['remaining_adjusted_basis']) - 7
        assert lot['cost_basis'] == before[lot['id']]['cost_basis']
        assert lot['remaining_quantity'] == before[lot['id']]['remaining_quantity']


@pytest.mark.parametrize('setup', ['unknown_basis', 'partial_lots', 'excess_per_lot'])
def test_uncertain_or_excess_return_of_capital_requires_atomic_manual_review(ledger, setup):
    seed(ledger, known_basis=setup != 'unknown_basis', complete_lots=setup != 'partial_lots',
         first_basis='1' if setup == 'excess_per_lot' else '10')
    before = copy.deepcopy(ledger.state())
    with pytest.raises(DomainError) as caught:
        ledger.record_activity(event('RETURN_OF_CAPITAL', amount='21'), yes=True)
    assert ledger.state() == before
    assert caught.value.code == 3, 'Recognized corporate action needs financial review, not unsupported-input rejection'
