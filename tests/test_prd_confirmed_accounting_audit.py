"""Confirmed public accounting facts survive retries, precision and later evidence."""

import copy
from decimal import Decimal

import pytest

from invest.ledger import Ledger
from invest.models import DomainError


@pytest.fixture
def ledger(tmp_path):
    selected = Ledger(tmp_path / 'confirmed-audit.db')
    yield selected
    selected.connection.close()


def observation(*, day='2026-03-01', cash='1000', quantity='10', basis='800',
                environment='SYNTHETIC', verified=True):
    return {'account': {'id': 'tax', 'name': 'Fictional taxable account',
            'tax_status': 'TAXABLE', 'currency': 'USD', 'history_complete': True},
        'positions': [{'security': 'FICT', 'asset_type': 'STOCK', 'quantity': quantity,
            'price': '100', 'market_value': str(Decimal(quantity) * 100), 'cost_basis': basis,
            'as_of': day, 'displayed_price_precision': 0, 'displayed_market_value_precision': 0}],
        'lots': [{'id': 'original-lot', 'security': 'FICT', 'quantity': quantity,
            'remaining_quantity': quantity, 'cost_basis': basis, 'remaining_adjusted_basis': basis,
            'acquisition_date': '2024-01-01', 'source_lot_id': 'fictional-original-001',
            'identity_status': 'VERIFIED' if verified else 'UNRESOLVED', 'saleable': verified,
            'identity_source': 'Human-reviewed fictional original lot reference' if verified else None}],
        'cash': cash, 'cash_known': True, 'source_timestamp': day,
        'positions_complete': True, 'lots_complete': True, 'data_environment': environment,
        'source_hash': f'fictional:{day}:{cash}:{quantity}:{basis}:{environment}:{verified}'}


def event(kind, **facts):
    return {'activity_id': 'confirmed-' + kind, 'account_id': 'tax', 'type': kind,
            'date': '2026-03-02', 'event_timestamp': '2026-03-02T12:00:00Z',
            'source': 'Reviewed fictional executed record', **facts}


def assert_atomic_rejection(ledger, call):
    before = copy.deepcopy(ledger.state())
    with pytest.raises(DomainError):
        call()
    assert ledger.state() == before


@pytest.mark.parametrize('contradiction', ['cash', 'lot', 'omitted_position'])
def test_later_complete_observation_cannot_erase_confirmed_effects(ledger, contradiction):
    ledger.apply(observation())
    if contradiction == 'cash':
        ledger.record_activity(event('CASH_DEPOSIT', amount='100'), yes=True)
        candidate = observation(day='2026-03-03', cash='1000')
    elif contradiction == 'lot':
        ledger.record_activity(event('SELL', security='FICT', quantity='2', price='100', fee='0',
                                    lot_allocations=[{'lot_id': 'original-lot', 'quantity': '2'}]), yes=True)
        candidate = observation(day='2026-03-03', cash='1200', quantity='8', basis='800')
        candidate['lots'][0].update(quantity='10', remaining_quantity='8',
                                    cost_basis='800', remaining_adjusted_basis='800')
    else:
        ledger.register_security({'ticker': 'NEW', 'name': 'Fictional new position',
            'asset_type': 'STOCK', 'currency': 'USD', 'source': 'Reviewed fictional issuer'})
        ledger.record_activity(event('BUY', security='NEW', quantity='1', price='100', fee='0'), yes=True)
        candidate = observation(day='2026-03-03', cash='900')
    assert_atomic_rejection(ledger, lambda: ledger.apply(candidate))


def test_equivalent_activity_decimal_lexemes_and_zero_fee_retry_are_idempotent(ledger):
    ledger.apply(observation())
    original = event('BUY', security='FICT', quantity='1', price='100', fee='0')
    ledger.record_activity(original, yes=True)
    before = copy.deepcopy(ledger.state())
    retry = dict(original, quantity='1.0', price='100.00', fee='0.00')
    assert ledger.record_activity(retry, yes=True)['status'] == 'UNCHANGED'
    assert ledger.state() == before
    assert_atomic_rejection(ledger, lambda: ledger.record_activity(dict(original, quantity='2'), yes=True))


def test_explicit_and_omitted_zero_fee_repeat_is_semantically_identical(ledger):
    ledger.apply(observation())
    original = event('CASH_DEPOSIT', amount='1')
    ledger.record_activity(original, yes=True)
    before = copy.deepcopy(ledger.state())
    assert ledger.record_activity(dict(original, amount='1.00', fee='0'), yes=True)['status'] == 'UNCHANGED'
    assert ledger.state() == before


def test_high_precision_cash_deposit_is_conserved_exactly(ledger):
    cash = '1000.123456789012345678901234567890123456789'
    ledger.apply(observation(cash=cash))
    ledger.record_activity(event('CASH_DEPOSIT', amount='0.000000000000000000000000000000000000001'), yes=True)
    assert Decimal(ledger.rows('cash_balances')[0]['amount']) == Decimal(
        '1000.123456789012345678901234567890123456790')


def test_high_precision_final_lot_sale_removes_exact_remaining_basis(ledger):
    basis = '800.123456789012345678901234567890123456789'
    ledger.apply(observation(basis=basis))
    ledger.record_activity(event('SELL', security='FICT', quantity='10', price='100', fee='0',
        lot_allocations=[{'lot_id': 'original-lot', 'quantity': '10'}]), yes=True)
    allocation = ledger.rows('activities')[0]['lot_allocations'][0]
    assert allocation['basis_removed'] == basis
    assert allocation['realized_gain'] == '199.876543210987654321098765432109876543211'
    assert Decimal(ledger.rows('lots')[0]['remaining_adjusted_basis']) == 0


def test_unverified_unsaleable_lot_cannot_be_confirmed_selected_sale(ledger):
    ledger.apply(observation(verified=False))
    assert_atomic_rejection(ledger, lambda: ledger.record_activity(event('SELL', security='FICT',
        quantity='1', price='100', fee='0', lot_allocations=[{'lot_id': 'original-lot', 'quantity': '1'}]), yes=True))


@pytest.mark.parametrize('irrelevant', ['split_fee', 'cash_trade_fields'])
def test_irrelevant_supplied_activity_facts_are_rejected_instead_of_ignored(ledger, irrelevant):
    ledger.apply(observation())
    supplied = (event('STOCK_SPLIT', security='FICT', split_ratio='2', fee='1')
        if irrelevant == 'split_fee' else event('CASH_DEPOSIT', amount='1', security='FICT',
                                               quantity='1', price='100'))
    assert_atomic_rejection(ledger, lambda: ledger.record_activity(supplied, yes=True))


def test_real_trade_missing_executed_fee_requires_review_and_does_not_mutate(ledger):
    # Fictional data explicitly models a REAL provenance boundary; no live/private inputs.
    ledger.apply(observation(environment='REAL'))
    supplied = event('BUY', security='FICT', quantity='1', price='100')
    before = copy.deepcopy(ledger.state())
    with pytest.raises(DomainError) as failure:
        ledger.record_activity(supplied, yes=True)
    assert any(issue['code'] == 'UNKNOWN_EXECUTION_FEE'
               for issue in failure.value.result['issues'])
    assert ledger.state() == before


def test_explicit_reviewed_zero_fee_real_trade_is_accepted(ledger):
    ledger.apply(observation(environment='REAL'))
    result = ledger.record_activity(event('BUY', security='FICT', quantity='1', price='100', fee='0'), yes=True)
    assert result['status'] == 'RECORDED'
    assert ledger.rows('activities')[0]['fee'] == '0'
