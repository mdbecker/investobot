import copy

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from invest.models import DomainError
from invest.tax import analyze, harvest_candidates, lots

scenarios('features/tax.feature')


@pytest.fixture
def context():
    return {}


@given('a taxable portfolio with an old high basis lot and a recent low basis lot')
def portfolio(context):
    context['state'] = {
        'accounts': [dict(id='tax', tax_status='TAXABLE', history_complete=True),
                     dict(id='ira', tax_status='TAX_FREE', history_complete=True)],
        'securities': [dict(id='sec', ticker='VTI')],
        'positions': [dict(account_id='tax', security_id='sec', security='VTI', quantity='20', price='100', market_value='2000', as_of='2026-10-08')],
        'lots': [dict(id='old', account_id='tax', security_id='sec', security='VTI', acquisition_date='2024-10-08', quantity='20', remaining_quantity='10', cost_basis='2200'),
                 dict(id='new', account_id='tax', security_id='sec', security='VTI', acquisition_date='2026-01-01', quantity='10', remaining_quantity='10', cost_basis='800')],
        'activities': [], 'cash_balances': [], 'snapshots': [],
    }


def sale(context, **kwargs):
    args = dict(account='tax', security='VTI', quantity='10', price='100', sale_date='2026-10-08')
    args.update(kwargs)
    context['result'] = analyze(context['state'], **args)


@when(parsers.parse('a sale is analyzed using "{method}"'))
def method_sale(context, method):
    sale(context, method=method, lot_ids=['new'] if method == 'SPECIFIC' else None,
         rates={'ordinary_income_rate': '.30', 'long_term_capital_gains_rate': '.15'})


@then(parsers.parse('the selected first lot is "{lot}" and the gain is "{gain}"'))
def selected(context, lot, gain):
    assert context['result']['selected_lots'][0]['id'] == lot
    assert context['result']['realized_gain_loss'] == gain


@when('fifteen shares are sold at one hundred dollars')
def mixed(context):
    sale(context, quantity='15')


@then('long term loss is one hundred and short term gain is one hundred')
def mixed_result(context):
    assert context['result']['long_term_gain_loss'] == '-100'
    assert context['result']['short_term_gain_loss'] == '100'


@given(parsers.parse('household purchase history is "{history}"'))
def history(context, history):
    state = context['state']
    if history == 'incomplete':
        state['accounts'][1]['history_complete'] = False
    elif history in {'IRA', 'taxable', 'future'}:
        state['activities'].append(dict(id='purchase', type='BUY', account_id='ira' if history == 'IRA' else 'tax', security_id='sec', security='VTI', quantity='1', date='2026-11-07' if history == 'future' else '2026-09-08'))


@when('a loss sale is analyzed')
def loss(context):
    sale(context)


@then(parsers.parse('wash sale status is "{status}"'))
def wash(context, status):
    result = context['result']['wash_sale']
    assert result['status'] == status
    if status == 'POTENTIAL_CONFLICT':
        assert result['affected_accounts']
        assert result['conflicts'][0]['date'] in {'2026-09-08', '2026-11-07'}


@given('the available lot basis is missing')
def missing_basis(context):
    context['state']['lots'][0]['cost_basis'] = None


@given('the lot detail is missing')
def missing_lots(context):
    context['state']['lots'] = []


@then('tax analysis reports insufficient data')
def insufficient(context):
    assert context['result']['status'] == 'INSUFFICIENT_DATA'
    assert context['result']['realized_gain_loss'] is None
    assert context['result']['warnings']


@when(parsers.parse('the sale is analyzed with "{rates}" tax rates'))
def rate_sale(context, rates):
    sale(context, rates=None if rates == 'absent' else {'ordinary_income_rate': '.30', 'long_term_capital_gains_rate': '.15', 'niit_rate': '.03', 'state_capital_gains_rate': '.02'})


@then(parsers.parse('the tax estimate is "{estimate}"'))
def estimate(context, estimate):
    assert context['result']['estimated_tax_effect'] == (None if estimate == 'none' else estimate)


@when('lots and harvesting candidates are inspected')
def inspect(context):
    before = copy.deepcopy(context['state'])
    context['lot_result'] = lots(context['state'], '2026-10-08')
    context['harvest'] = harvest_candidates(context['state'], '2026-10-08')
    assert context['state'] == before


@then('the old lot has one hundred dollars of unrealized loss and is a harvesting candidate')
def candidates(context):
    old = next(lot for lot in context['lot_result']['lots'] if lot['id'] == 'old')
    assert old['cost_basis'] == '1100'
    assert old['unrealized_gain_loss'] == '-100'
    assert [lot['id'] for lot in context['harvest']['candidates']] == ['old']


@when('thirty shares are proposed for sale')
def excess(context):
    try:
        sale(context, quantity='30')
    except DomainError as error:
        context['error'] = error


@then('the sale is rejected as inconsistent state')
def rejected(context):
    assert context['error'].code == 3


@when('the old lot is inspected on its acquisition anniversary')
def anniversary(context):
    context['lot_result'] = lots(context['state'], '2025-10-08')


@then('its holding period is short term')
def short_term(context):
    assert next(lot for lot in context['lot_result']['lots'] if lot['id'] == 'old')['term'] == 'SHORT_TERM'
