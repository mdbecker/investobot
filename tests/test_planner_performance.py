import copy
from decimal import Decimal
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from invest.ledger import Ledger
from invest.market import MarketClient
from invest.models import DomainError
from invest.plans import generate
from invest.targets import save

scenarios('features/planner_performance.feature')


@pytest.fixture
def planning(tmp_path):
    ledger = Ledger(tmp_path / 'planning.db')
    return {'ledger': ledger, 'client': MarketClient(
        ledger, fixture_path=Path('tests/fixtures/fmp-synthetic.json'))}


@given('a deterministic mixed household with gain and loss lots')
def mixed_household(planning):
    ledger = planning['ledger']
    for account, status, quantity, basis, lots in [
        ('ira', 'TAX_FREE', '5', '250', [('ira-old', '5', '250')]),
        ('tax', 'TAXABLE', '10', '780',
         [('tax-loss', '4', '480'), ('tax-gain', '6', '300')]),
    ]:
        ledger.apply({
            'account': {'id': account, 'name': account, 'tax_status': status,
                        'history_complete': True},
            'positions': [
                {'security': 'AAA', 'asset_type': 'STOCK', 'quantity': quantity,
                 'price': '100', 'market_value': str(Decimal(quantity) * 100),
                 'cost_basis': basis, 'as_of': '2026-10-08'},
                {'security': 'BBB', 'asset_type': 'MUTUAL_FUND', 'quantity': '0',
                 'price': '100', 'market_value': '0', 'as_of': '2026-10-08'},
            ],
            'lots': [{'id': lid, 'security': 'AAA', 'quantity': qty,
                      'remaining_quantity': qty, 'cost_basis': cost,
                      'acquisition_date': '2024-01-01'} for lid, qty, cost in lots],
            'cash': '0', 'source_hash': f'planner-fixture-{account}',
            'source_timestamp': '2026-10-08', 'positions_complete': True,
            'lots_complete': True,
        })
    aaa, bbb = ledger.resolve('AAA')['id'], ledger.resolve('BBB')['id']
    planning.update(aaa=aaa, bbb=bbb, before=copy.deepcopy(ledger.state()))
    planning['target'] = save(ledger, {
        'name': 'Deterministic replacement',
        'target_allocations': {aaa: '0', bbb: '.95', 'CASH': '.05'},
        'planning_constraints': {
            'eligible_accounts': ['tax', 'ira'],
            'permitted_securities': {a: [aaa, bbb] for a in ['tax', 'ira']},
            'long_term_gain_budget': '100',
            'trade_increments': {a: {bbb: '.1'} for a in ['tax', 'ira']},
        },
    })


def make_plan(planning):
    return generate(planning['ledger'], planning['client'], planning['target']['id'],
                    as_of='2026-10-08', rates={
                        'ordinary_income_rate': '.3', 'long_term_capital_gains_rate': '.2'})


@when('its constrained replacement plan is generated')
def generate_plan(planning):
    planning['plan'] = make_plan(planning)


@then('the exact retirement-first trades and lot allocations are preserved')
def exact_trades(planning):
    plan = planning['plan']
    assert [(a['type'], a['account_id'], a['security'], a['quantity'])
            for a in plan['proposed_actions']] == [
                ('SELL', 'ira', planning['aaa'], '5'),
                ('SELL', 'tax', planning['aaa'], '4'),
                ('SELL', 'tax', planning['aaa'], '2'),
                ('BUY', 'ira', planning['bbb'], '5'),
                ('BUY', 'tax', planning['bbb'], '5.2'),
            ]
    assert [a['lot_allocations'] for a in plan['proposed_actions']
            if a['account_id'] == 'tax' and a['type'] == 'SELL'] == [
                [{'lot_id': 'tax-loss', 'quantity': '4'}],
                [{'lot_id': 'tax-gain', 'quantity': '2'}],
            ]


@then('final cash, gains, tax and allocation preserve the recorded results')
def exact_finances(planning):
    plan = planning['plan']
    assert {a: Decimal(v) for a, v in plan['cash_after'].items()} == {
        'ira': Decimal('0'), 'tax': Decimal('80')}
    assert Decimal(plan['tax_analysis']['realized_gain_loss']) == 20
    assert Decimal(plan['tax_analysis']['long_term_gain_loss']) == 20
    assert Decimal(plan['tax_analysis']['short_term_gain_loss']) == 0
    assert Decimal(plan['tax_analysis']['estimated_tax_effect']) == 4
    assert Decimal(plan['turnover']) == 2120
    assert {r['security_id']: Decimal(r['current_value'])
            for r in plan['proposed_allocation']['allocations']} == {
                planning['aaa']: Decimal('400'), planning['bbb']: Decimal('1020'),
                'CASH': Decimal('80')}
    assert plan['status'] == 'REVIEW_REQUIRED'
    assert 'LONG_TERM: realized gain budget limits taxable sale' in plan['warnings']


@then('planning leaves accepted holdings and provider caches unchanged')
def unchanged(planning):
    assert planning['ledger'].state() == planning['before']
    assert planning['ledger'].rows('market_data_cache') == []
    assert planning['ledger'].rows('fund_holdings_cache') == []


@given(parsers.parse('the authoritative simulation returns inconsistent {field}'))
def inconsistent_simulation(planning, monkeypatch, field):
    import invest.plans as plans

    original = plans.simulate

    def corrupted(*args, **kwargs):
        result = original(*args, **kwargs)
        state = result['hypothetical_state']
        if field == 'cash':
            state['cash_balances'][0]['amount'] = '999'
        else:
            state['positions'][0]['market_value'] = '999'
        return result

    monkeypatch.setattr(plans, 'simulate', corrupted)


@when('its constrained replacement plan is requested')
def request_plan(planning):
    try:
        make_plan(planning)
    except DomainError as exc:
        planning['error'] = exc


@then('inconsistent simulation fails without saving a plan')
def inconsistent_rejected(planning):
    assert 'error' in planning, 'An inconsistent simulation was accepted'
    assert planning['error'].code == 3
    assert 'inconsistent' in str(planning['error']).lower()
    assert planning['ledger'].connection.execute('SELECT count(*) FROM plan_runs').fetchone()[0] == 0
