"""Independent exact arithmetic for hypothetical sales, never execution reconstruction."""
import copy
from fractions import Fraction

import pytest
from pytest_bdd import given, scenarios, then, when

from invest.tax import analyze

scenarios('features/mvp/sale_estimates.feature')


@pytest.fixture
def sale_context():
    return {}


def portfolio(ctx, quantities, bases):
    ctx['state'] = {'accounts': [{'id': 'tax', 'tax_status': 'TAXABLE', 'history_complete': True}],
                    'securities': [{'id': 'stock', 'ticker': 'FICTION'}],
                    'positions': [{'account_id': 'tax', 'security_id': 'stock', 'security': 'FICTION',
                                   'quantity': str(sum(quantities)), 'source_timestamp': '2026-10-13'}],
                    'lots': [{'id': str(i), 'account_id': 'tax', 'security_id': 'stock',
                              'security': 'FICTION', 'quantity': str(q), 'remaining_quantity': str(q),
                              'cost_basis': str(b + 100), 'remaining_adjusted_basis': str(b),
                              'acquisition_date': '2024-01-01' if i == 0 else '2026-01-01'}
                             for i, (q, b) in enumerate(zip(quantities, bases))],
                    'activities': [], 'cash_balances': [], 'snapshots': []}


@given('two specific lots with remaining adjusted bases 240 and 140')
def two(sale_context):
    portfolio(sale_context, [3, 2], [240, 140])


@given('two specific lots including a long term loss')
def loss(sale_context):
    portfolio(sale_context, [3, 2], [400, 140])


@given('three one share specific lots')
def three(sale_context):
    portfolio(sale_context, [1, 1, 1], [80, 80, 80])


@given('the second lot has unknown basis')
def unknown(sale_context):
    sale_context['state']['lots'][1].update(cost_basis=None, remaining_adjusted_basis=None)


def estimate(ctx, quantity, fee):
    ctx['before'] = copy.deepcopy(ctx['state'])
    ctx['result'] = analyze(ctx['state'], 'tax', 'FICTION', str(quantity), '100', '2026-10-13',
                            method='SPECIFIC', lot_ids=[lot['id'] for lot in ctx['state']['lots']],
                            rates={'ordinary_income_rate': '.4', 'long_term_capital_gains_rate': '.2'}, fee=str(fee))


@when('five shares are estimated at 100 with a sale fee of 5')
def five(sale_context):
    estimate(sale_context, 5, 5)


@when('three shares are estimated with a fee of 1')
def thirds(sale_context):
    estimate(sale_context, 3, 1)


@then('the long term gain is 57 and short term gain is 58')
def gains(sale_context):
    result = sale_context['result']
    assert result['realized_gain_loss'] == '115'
    assert result['long_term_gain_loss'] == '57'
    assert result['short_term_gain_loss'] == '58'
    assert [row['fee'] for row in result['selected_lots']] == ['3', '2']


@then('the positive estimated tax cost is 34.6 without changing financial facts')
def cost(sale_context):
    assert sale_context['result']['positive_estimated_tax_cost'] == '34.6'
    assert sale_context['state'] == sale_context['before']


@then('the positive estimated tax cost is 23.2 despite the loss')
def loss_cost(sale_context):
    assert sale_context['result']['positive_estimated_tax_cost'] == '23.2'
    assert sale_context['result']['wash_sale']['warnings']
    assert sale_context['state'] == sale_context['before']


@then('the allocated fees total exactly 1')
def residue(sale_context):
    assert sum(Fraction(row['fee']) for row in sale_context['result']['selected_lots']) == 1
    assert sale_context['state'] == sale_context['before']


@then('the sale reports insufficient data without invented gains')
def blocked(sale_context):
    assert sale_context['result']['status'] == 'INSUFFICIENT_DATA'
    assert sale_context['result']['realized_gain_loss'] is None
    assert sale_context['state'] == sale_context['before']
