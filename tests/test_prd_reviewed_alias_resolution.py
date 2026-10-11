"""Reviewed ticker aliases resolve consistently across public financial boundaries."""

import copy
from decimal import Decimal

import pytest

from invest.ledger import Ledger
from invest.models import DomainError
from invest.simulations import simulate
from invest.tax import analyze


@pytest.fixture
def ledger(tmp_path):
    instance = Ledger(tmp_path / 'fictional-reviewed-alias.db')
    instance.apply({
        'account': {'id': 'fictional', 'name': 'Fictional reviewed alias account',
                    'tax_status': 'TAXABLE', 'history_complete': True},
        'positions': [{'security': 'CURRENT', 'name': 'Fictional renamed security',
                       'asset_type': 'STOCK', 'cusip': '111111111', 'quantity': '2',
                       'price': '100', 'market_value': '200', 'cost_basis': '100',
                       'displayed_price_precision': 2, 'displayed_market_value_precision': 2}],
        'lots': [{'id': 'fictional-lot', 'source_lot_id': 'fictional-broker-lot',
                  'identity_status': 'VERIFIED', 'identity_source': 'Reviewed fictional original broker lot',
                  'security': 'CURRENT', 'acquisition_date': '2024-01-01', 'quantity': '2',
                  'remaining_quantity': '2', 'cost_basis': '100', 'remaining_adjusted_basis': '100'}],
        'cash': '100', 'cash_known': True, 'positions_complete': True, 'lots_complete': True,
        'source_timestamp': '2026-10-09', 'source_hash': 'fictional-reviewed-alias-source',
        'data_environment': 'SYNTHETIC',
    })
    original = instance.resolve('CURRENT')['id']
    registered = instance.register_security({
        'ticker': 'CURRENT', 'name': 'Fictional renamed security', 'asset_type': 'STOCK',
        'currency': 'USD', 'cusip': '111111111', 'source': 'Reviewed fictional original issuer rename notice',
        'ticker_aliases': [{'ticker': 'FORMER', 'source': 'Reviewed fictional dated issuer ticker rename'}],
    })
    assert registered['id'] == original
    assert instance.connection.execute(
        "SELECT count(*) FROM security_aliases WHERE value='FORMER' AND source IS NOT NULL").fetchone()[0] == 1
    yield instance
    instance.connection.close()


def action(kind='BUY'):
    return {'activity_id': 'fictional-alias-' + kind, 'account_id': 'fictional', 'security': 'FORMER',
            'type': kind, 'date': '2026-10-10', 'quantity': '1', 'price': '100', 'fee': '0',
            'source': 'Reviewed fictional broker activity with historical ticker'}


def test_ledger_resolve_accepts_reviewed_historical_ticker_without_new_identity(ledger):
    before = copy.deepcopy(ledger.state())
    assert ledger.resolve('FORMER')['id'] == ledger.resolve('CURRENT')['id']
    assert ledger.state() == before


def test_confirmed_activity_uses_reviewed_alias_canonical_position(ledger):
    sid = ledger.resolve('CURRENT')['id']
    ledger.record_activity(action(), yes=True)
    positions = ledger.rows('positions')
    assert len(positions) == 1
    assert positions[0]['security_id'] == sid
    assert Decimal(positions[0]['quantity']) == 3
    assert len(ledger.rows('securities')) == 1


def test_corporate_action_uses_same_reviewed_alias_identity(ledger):
    sid = ledger.resolve('CURRENT')['id']
    ledger.record_activity({'activity_id': 'fictional-alias-split', 'account_id': 'fictional',
                            'security': 'FORMER', 'type': 'STOCK_SPLIT', 'split_ratio': '2',
                            'date': '2026-10-10', 'source': 'Reviewed fictional issuer split notice'}, yes=True)
    assert ledger.rows('positions')[0]['security_id'] == sid
    assert Decimal(ledger.rows('positions')[0]['quantity']) == 4
    assert ledger.rows('lots')[0]['id'] == 'fictional-lot'


def test_authoritative_simulation_resolves_alias_and_does_not_mutate_baseline(ledger):
    baseline = copy.deepcopy(ledger.state())
    result = simulate(baseline, [action()])
    assert ledger.state() == baseline
    assert len(result['after']['positions']) == 1
    assert result['after']['positions'][0]['security_id'] == ledger.resolve('CURRENT')['id']
    assert Decimal(result['after']['positions'][0]['quantity']) == 3


def test_tax_alias_and_canonical_security_produce_identical_specific_lot_estimates(ledger):
    baseline = copy.deepcopy(ledger.state())
    arguments = {'account': 'fictional', 'quantity': '1', 'price': '100', 'sale_date': '2026-10-10',
                 'method': 'SPECIFIC', 'lot_ids': ['fictional-lot'],
                 'rates': {'ordinary_income_rate': '0.35', 'long_term_capital_gains_rate': '0.15'}}
    canonical = analyze(baseline, security=ledger.resolve('CURRENT')['id'], **arguments)
    historical = analyze(baseline, security='FORMER', **arguments)
    assert historical == canonical
    assert historical['security_id'] == ledger.resolve('CURRENT')['id']
    assert ledger.state() == baseline


def test_conflicting_strong_identity_never_replaces_reviewed_security(ledger):
    before = copy.deepcopy(ledger.state())
    with pytest.raises(DomainError):
        ledger.register_security({'ticker': 'CURRENT', 'name': 'Fictional identity conflict',
                                  'asset_type': 'STOCK', 'currency': 'USD', 'cusip': '999999999',
                                  'source': 'Reviewed fictional conflicting original identifier'})
    assert ledger.state() == before
