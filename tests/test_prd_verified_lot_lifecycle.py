"""Reviewed lot identity and exhausted history survive real public reimports."""

import copy

import pytest
from test_prd_confirmed_accounting_audit import event, observation

from invest.ledger import Ledger
from invest.models import DomainError


@pytest.fixture
def ledger(tmp_path):
    selected = Ledger(tmp_path / 'lot-lifecycle.db')
    yield selected
    selected.connection.close()


def executed_sale(ledger, quantity):
    return ledger.record_activity(event('SELL', security='FICT', quantity=quantity,
        price='100', fee='0', lot_allocations=[{'lot_id': 'original-lot', 'quantity': quantity}]), yes=True)


def test_complete_zero_inventory_reimport_retains_exhausted_allocation_history(ledger):
    ledger.apply(observation())
    executed_sale(ledger, '10')
    original_activity = copy.deepcopy(ledger.rows('activities'))
    candidate = observation(day='2026-03-03', cash='2000', quantity='0', basis='0')
    candidate['positions'] = []
    candidate['lots'] = []
    assert ledger.apply(candidate)['status'] == 'APPLIED'
    assert ledger.rows('activities') == original_activity
    retained = next(row for row in ledger.rows('lots') if row['id'] == 'original-lot')
    assert retained['remaining_quantity'] == '0'
    assert retained['remaining_adjusted_basis'] == '0'
    assert retained['source_lot_id'] == 'fictional-original-001'
    assert ledger.connection.execute('PRAGMA foreign_key_check').fetchall() == []
    allocation = ledger.rows('activities')[0]['lot_allocations'][0]
    assert allocation['basis_removed'] == '800'
    assert allocation['realized_gain'] == '200'


def test_partial_lot_reimport_retains_stable_identity_basis_and_confirmed_allocation(ledger):
    ledger.apply(observation())
    executed_sale(ledger, '2')
    original_activity = copy.deepcopy(ledger.rows('activities'))
    candidate = observation(day='2026-03-03', cash='1200', quantity='8', basis='640')
    candidate['lots'][0].update(quantity='10', remaining_quantity='8', cost_basis='800',
                               remaining_adjusted_basis='640')
    assert ledger.apply(candidate)['status'] == 'APPLIED'
    assert ledger.rows('activities') == original_activity
    retained = ledger.rows('lots')[0]
    assert retained['id'] == 'original-lot'
    assert retained['remaining_quantity'] == '8'
    assert retained['remaining_adjusted_basis'] == '640'
    assert retained['identity_status'] == 'VERIFIED'
    assert ledger.connection.execute('PRAGMA foreign_key_check').fetchall() == []


@pytest.mark.parametrize('missing', ['all', 'source_lot_id', 'identity_source', 'identity_status', 'saleable'])
def test_real_specific_sale_needs_verified_source_identity_and_saleability(ledger, missing):
    candidate = observation(environment='REAL')
    keys = ('source_lot_id', 'identity_source', 'identity_status', 'saleable') if missing == 'all' else (missing,)
    for key in keys:
        candidate['lots'][0].pop(key)
    ledger.apply(candidate)
    before = copy.deepcopy(ledger.state())
    with pytest.raises(DomainError) as failure:
        executed_sale(ledger, '1')
    assert failure.value.code == 3
    assert any(issue['code'] == 'UNVERIFIED_LOT_IDENTITY'
               for issue in failure.value.result['issues'])
    assert ledger.state() == before
