from decimal import Decimal

import pytest
from pytest_bdd import given, scenarios, then, when

from invest.ledger import Ledger

scenarios('features/mvp/quarterly_backtest.feature')


@pytest.fixture
def ctx(tmp_path):
    ledger = Ledger(tmp_path / 'fictional.db')
    yield {'ledger': ledger}
    ledger.connection.close()


@given('two fictional dated total-return series cross a quarterly boundary')
def evidence(ctx):
    ids = []
    for ticker in ['FAKEA', 'FAKEB']:
        ids.append(ctx['ledger'].register_security({'ticker': ticker, 'name': ticker,
            'asset_type': 'STOCK', 'currency': 'USD', 'source': 'Fictional reviewed fixture'})['id'])
    sessions = ['2026-02-27', '2026-03-02', '2026-03-03']
    ctx['weights'] = dict.fromkeys(ids, '0.5')
    ctx['manifest'] = {'id': 'quarterly-fixture', 'data_environment': 'SYNTHETIC',
        'sessions': sessions, 'series': {
            ids[0]: [{'date': day, 'total_return_index': value}
                     for day, value in zip(sessions, ['100', '200', '400'])],
            ids[1]: [{'date': day, 'total_return_index': '100'} for day in sessions]}}
    ctx['before'] = ctx['ledger'].state()


@when('the quarterly historical policy is simulated')
def calculate(ctx):
    from invest.backtest import run

    ctx['result'] = run(ctx['ledger'], portfolio=ctx['weights'], start='2026-02-27',
        end='2026-03-03', policy={'starting_value': '1000', 'fee_per_trade': '0',
            'contribution_schedule': [], 'rebalance_frequency': 'QUARTERLY',
            'drift_trigger': '0.05'}, manifest=ctx['manifest'])


@then('only the first qualifying March session rebalances and facts remain unchanged')
def verified(ctx):
    assert ctx['result']['status'] == 'AVAILABLE'
    assert Decimal(ctx['result']['final_value']) == 2250
    assert Decimal(ctx['result']['total_return']) == Decimal('1.25')
    assert ctx['result']['assumptions']['rebalance_frequency'] == 'QUARTERLY'
    assert ctx['ledger'].state() == ctx['before']
