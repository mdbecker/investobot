"""Source amounts beyond fixed Decimal precision survive public calculations."""

import copy
from decimal import Decimal

import pytest

from invest.ledger import Ledger
from invest.performance_ledger import report
from invest.simulations import simulate


@pytest.fixture
def ledger(tmp_path):
    instance = Ledger(tmp_path / 'fictional-exact.db')
    yield instance
    instance.connection.close()


def cash_observation(account, amount, date):
    return {
        'account': {'id': account, 'name': 'Fictional exact ' + account,
                    'tax_status': 'TAX_FREE', 'history_complete': True},
        'positions': [], 'lots': [], 'cash': str(amount), 'cash_known': True,
        'positions_complete': True, 'lots_complete': True,
        'source_timestamp': date, 'source_hash': f'fictional:{account}:{date}:{amount}',
        'data_environment': 'SYNTHETIC',
    }


def test_no_action_simulation_preserves_exact_large_household_sum(ledger):
    first = 10 ** 110 + 7
    second = 13
    ledger.apply(cash_observation('first', first, '2026-10-09'))
    ledger.apply(cash_observation('second', second, '2026-10-09'))
    baseline = copy.deepcopy(ledger.state())
    result = simulate(baseline, [])
    assert ledger.state() == baseline
    assert result['after'] == baseline
    assert Decimal(result['household_value_after']) == Decimal(str(first + second))


def test_buy_simulation_preserves_large_cash_residue_and_total(ledger):
    amount = 10 ** 110 + 7
    ledger.apply(cash_observation('first', amount, '2026-10-09'))
    ledger.register_security({'ticker': 'FICTIONAL', 'name': 'Fictional exact security',
                              'asset_type': 'STOCK', 'currency': 'USD',
                              'source': 'Reviewed fictional security identity'})
    baseline = copy.deepcopy(ledger.state())
    result = simulate(baseline, [{'type': 'BUY', 'account_id': 'first',
                                'security': 'FICTIONAL', 'quantity': '1', 'price': '3',
                                'fee': '0', 'date': '2026-10-10'}])
    assert ledger.state() == baseline
    assert Decimal(result['after']['cash_balances'][0]['amount']) == Decimal(str(amount - 3))
    assert Decimal(result['household_value_after']) == Decimal(str(amount))


def test_historical_household_checkpoint_sum_retains_source_low_digits(ledger):
    # The small account contributes a source-provided residual above exactly 100% growth.
    # Summing with default Decimal precision erases it before the return calculator runs.
    large = 10 ** 110
    for date, multiple, small in [('2025-10-10', 1, 1), ('2026-10-10', 2, 3)]:
        ledger.apply(cash_observation('large', large * multiple, date))
        ledger.apply(cash_observation('small', small, date))
    baseline = copy.deepcopy(ledger.state())
    result = report(ledger.connection, from_date='2025-10-10', to_date='2026-10-10')
    assert ledger.state() == baseline
    assert result['twr']['status'] == 'AVAILABLE'
    assert Decimal(result['twr']['return']) > Decimal('1')
