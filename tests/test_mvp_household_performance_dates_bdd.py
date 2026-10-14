"""Public actual-performance acceptance; synthetic expectations use exact arithmetic."""

import json
import math
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from typer.testing import CliRunner

from invest.cli import app
from invest.ledger import Ledger

scenarios('features/mvp/household_performance_dates.feature')


@pytest.fixture
def household(tmp_path, monkeypatch):
    path = tmp_path / 'household.db'
    monkeypatch.setenv('INVEST_DB', str(path))
    ledger = Ledger(path)
    yield {'ledger': ledger, 'runner': CliRunner()}
    ledger.connection.close()


def observe(household, account, timestamp, value, *, cash_known=True, cash='0'):
    invested = str(Decimal(value) - Decimal(cash))
    return household['ledger'].apply({
        'account': {'id': account, 'name': account, 'tax_status': 'TAX_FREE',
                    'currency': 'USD', 'history_complete': True},
        'data_environment': 'SYNTHETIC', 'positions': [
            {'security': 'SYN', 'asset_type': 'STOCK', 'quantity': '1',
             'price': invested, 'market_value': invested,
             'displayed_price_precision': 0, 'displayed_market_value_precision': 0}],
        'positions_complete': True, 'cash': cash,
        'cash_known': cash_known, 'source_timestamp': timestamp,
        'source_hash': f'synthetic-{account}-{timestamp}-{value}',
    })


def endpoints(household):
    for day, amounts in [('2026-01-01', ('1000', '2000')),
                         ('2026-01-03', ('1100', '2200'))]:
        for account, minute, cash in zip(('alpha', 'beta'), ('00', '01'), amounts, strict=True):
            observe(household, account, f'{day}T16:{minute}:00Z', cash)


@given('two complete synthetic accounts observed one minute apart on each endpoint')
def complete(household):
    endpoints(household)


@given(parsers.parse('household observations with {evidence} around an external deposit'))
def flow_evidence(household, evidence):
    for account, cash in [('alpha', '1000'), ('beta', '2000')]:
        observe(household, account, '2026-01-01T16:00:00Z', cash)
    moments = {
        'opposite timestamps': ('2026-01-02T15:59:00Z', '2026-01-02T16:01:00Z'),
        'date only timestamps': ('2026-01-02', '2026-01-02'),
        'missing event time': ('2026-01-02T16:01:00Z', '2026-01-02T16:02:00Z'),
        'common after timestamps': ('2026-01-02T16:01:00Z', '2026-01-02T16:02:00Z'),
    }[evidence]
    activity = {'activity_id': 'deposit', 'account_id': 'alpha', 'type': 'CASH_DEPOSIT',
                'amount': '100', 'date': '2026-01-02'}
    if evidence != 'missing event time':
        activity['event_timestamp'] = '2026-01-02T16:00:00Z'
    if evidence == 'common after timestamps':
        household['ledger'].record_activity(activity, yes=True)
    for account, timestamp in zip(('alpha', 'beta'), moments, strict=True):
        value = '1100' if account == 'alpha' and evidence == 'common after timestamps' else (
            '1000' if account == 'alpha' else '2000')
        observe(household, account, timestamp, value,
                cash='100' if account == 'alpha' and evidence == 'common after timestamps' else '0')
    if evidence != 'common after timestamps':
        household['ledger'].record_activity(activity, yes=True)
    for account, value in [('alpha', '1210'), ('beta', '2200')]:
        observe(household, account, '2026-01-03T16:00:00Z', value,
                cash='100' if account == 'alpha' else '0')


@given('two complete synthetic accounts with conflicting same date valuations')
def conflict(household):
    endpoints(household)
    observe(household, 'alpha', '2026-01-03T16:02:00Z', '1200')


@given('two synthetic accounts with unknown cash in one endpoint')
def incomplete(household):
    for account, cash in [('alpha', '1000'), ('beta', '2000')]:
        observe(household, account, '2026-01-01T16:00:00Z', cash)
    observe(household, 'alpha', '2026-01-03T16:00:00Z', '1100')
    observe(household, 'beta', '2026-01-03T16:01:00Z', '2200', cash_known=False)


def request(household, account=None):
    household['before'] = household['ledger'].state()
    arguments = ['portfolio', 'performance', '--from', '2026-01-01', '--to', '2026-01-03']
    if account:
        arguments += ['--account', account]
    result = household['runner'].invoke(app, arguments)
    assert result.exit_code == 0, result.output
    household['result'] = json.loads(result.stdout)
    repeated = household['runner'].invoke(app, arguments)
    assert repeated.exit_code == 0, repeated.output
    assert json.loads(repeated.stdout) == household['result']


@when('actual household performance is requested twice')
def household_report(household):
    request(household)


@when('actual performance for account alpha is requested')
def account_report(household):
    request(household, 'alpha')


@then('the household return is exactly ten percent on three thousand dollars')
def household_return(household):
    result = household['result']
    assert result['status'] == 'AVAILABLE'
    # Independent oracle: (1100 + 2200) / (1000 + 2000) - 1 = 0.1.
    assert Decimal(result['twr']['return']) == Decimal('0.1')
    assert result['issues'] == []
    assert Decimal(result['net_external_contributions']) == 0
    assert result['xirr']['status'] == 'AVAILABLE'


@then('the account return is exactly ten percent')
def account_return(household):
    assert household['result']['scope'] == 'ACCOUNT'
    assert household['result']['status'] == 'AVAILABLE'
    assert Decimal(household['result']['twr']['return']) == Decimal('0.1')


@then('the household return excludes the one hundred dollar deposit')
def flow_return(household):
    result = household['result']
    assert result['status'] == 'AVAILABLE'
    # Pre-flow household 3000, post-flow 3100, ending 3410: (3000/3000)*(3410/3100)-1.
    assert Decimal(result['twr']['return']) == Decimal('0.1')
    assert Decimal(result['net_external_contributions']) == 100


@then(parsers.parse('TWR is unavailable with {code}'))
def blocked(household, code):
    result = household['result']
    assert result['status'] in {'UNAVAILABLE', 'PARTIAL'}
    assert result['twr']['status'] == 'UNAVAILABLE'
    assert result['twr']['return'] is None
    issue = next(item for item in result['issues'] if item['code'] == code)
    assert issue['blocks_calculation'] is True


@then('reporting preserves every accepted fact')
def preserved(household):
    assert household['ledger'].state() == household['before']


@then('complete endpoints and dated cash flows still support money weighted return')
def money_weighted(household):
    result = household['result']
    assert result['xirr']['status'] == 'AVAILABLE'
    # Independent positive quadratic root: 3000*q**2 + 100*q - 3410 = 0.
    daily_growth = (-100 + math.sqrt(100**2 + 4 * 3000 * 3410)) / 6000
    expected = math.expm1(math.log(daily_growth) * 365.25)
    assert result['xirr']['annualized_return'] == pytest.approx(expected, rel=1e-8)
