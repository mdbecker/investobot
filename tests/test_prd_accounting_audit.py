"""Public-boundary PRD accounting audit with coherent reviewed fictional sources."""

import json
from decimal import Decimal

import pytest
from typer.testing import CliRunner

from invest.cli import app
from invest.ledger import Ledger
from invest.planning import propose
from invest.targets import save
from invest.tax import analyze, lots


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    path = tmp_path / 'audit.db'
    monkeypatch.setenv('INVEST_DB', str(path))
    selected = Ledger(path)
    yield selected
    selected.connection.close()


def accept(ledger, account='ira', *, quantity='10', cash='0', date='2026-03-01',
           currency='USD', complete=True, original='1000', adjusted='800'):
    positions, inventory = [], []
    if Decimal(quantity):
        positions = [{'security': 'FICT', 'asset_type': 'STOCK', 'quantity': quantity,
                      'price': '100', 'market_value': str(Decimal(quantity) * 100),
                      'cost_basis': adjusted, 'as_of': date,
                      'displayed_price_precision': 0, 'displayed_market_value_precision': 0}]
        inventory = [{'id': account + '-lot', 'security': 'FICT', 'quantity': quantity,
                      'remaining_quantity': quantity, 'cost_basis': original,
                      'remaining_adjusted_basis': adjusted, 'acquisition_date': '2024-01-01',
                      'source_lot_id': account + '-original-lot', 'identity_status': 'VERIFIED',
                      'identity_source': 'Reviewed fictional remaining adjusted basis statement'}]
    return ledger.apply({'account': {'id': account, 'name': account, 'currency': currency,
                        'tax_status': 'TAXABLE' if account.startswith('a-tax') else 'TAX_FREE',
                        'history_complete': True},
                        'positions': positions, 'lots': inventory, 'cash': cash,
                        'source_timestamp': date, 'positions_complete': complete,
                        'lots_complete': complete, 'data_environment': 'SYNTHETIC',
                        'source_hash': f'{account}:{date}:{quantity}:{cash}:{complete}:{original}'})


def register(ledger, ticker):
    return ledger.register_security({'ticker': ticker, 'name': 'Fictional ' + ticker,
                                    'asset_type': 'STOCK', 'currency': 'USD',
                                    'source': 'Reviewed fictional issuer metadata'})['id']


def proposal(ledger, weights, accounts, *, mode='contributions-only', day='2026-03-10'):
    securities = {row['id'] for row in ledger.rows('securities')}
    target = save(ledger, {'name': 'Fictional audited target', 'target_allocations': weights,
                          'planning_constraints': {'eligible_accounts': accounts,
                           'permitted_securities': {account: sorted(securities) for account in accounts}}})
    policy = {'version': 'fictional-audit', 'data_environment': 'SYNTHETIC',
              'source': 'Reviewed fictional policy approval', 'fee_per_trade': '0',
              'max_position_age_days': 30, 'cash_floors': {account: '0' for account in accounts},
              'permissions': {account: {sid: {'can_buy': True, 'can_sell': True,
                'can_hold': True, 'share_increment': '0.1'} for sid in securities} for account in accounts},
              'annual_tax_budget': {'year': 2026, 'annual_allowance': '1000',
                'short_term_rate': '0.4', 'long_term_rate': '0.2', 'currency': 'USD',
                'taxable_history_complete': True, 'source': 'Reviewed all fictional taxable sales',
                'as_of': '2026-03-10T12:00:00Z', 'data_environment': 'SYNTHETIC'}}
    return propose(ledger, target['id'], policy=policy, mode=mode, as_of=day,
                   prices={sid: '100' for sid in securities})


@pytest.mark.parametrize('original', ['1000', None])
@pytest.mark.parametrize('query', ['lots', 'sale'])
def test_tax_queries_use_exact_remaining_adjusted_basis_even_without_original(ledger, original, query):
    accept(ledger, 'a-tax', original=original)
    state = ledger.state()
    if query == 'lots':
        inventory = lots(state, '2026-03-10')
        assert inventory['lots'][0]['cost_basis'] == '800'
        return
    result = analyze(state, 'a-tax', 'FICT', '2', '100', '2026-03-10', method='SPECIFIC',
                     lot_ids=['a-tax-lot'])
    assert len(result['selected_lots']) == 1, result
    assert result['selected_lots'][0]['basis'] == '160'
    assert result['long_term_gain_loss'] == '40'


def test_mixed_currency_household_performance_is_unavailable(ledger):
    for day in ['2025-03-10', '2026-03-10']:
        accept(ledger, 'usd', quantity='0', cash='100', currency='USD', date=day)
        accept(ledger, 'eur', quantity='0', cash='100', currency='EUR', date=day)
    result = CliRunner().invoke(app, ['portfolio', 'performance', '--from', '2025-03-10',
                                    '--to', '2026-03-10'])
    assert result.exit_code == 0, result.stderr
    outcome = json.loads(result.stdout)
    assert outcome['twr']['status'] == 'UNAVAILABLE'
    assert any(issue['code'] == 'UNSUPPORTED_CURRENCY' for issue in outcome['issues'])


def test_account_performance_selects_only_requested_account(ledger):
    for day, cash in [('2025-03-10', '100'), ('2026-03-10', '110')]:
        accept(ledger, 'selected', quantity='0', cash=cash, date=day)
        accept(ledger, 'other', quantity='0', cash='1000', date=day)
    result = CliRunner().invoke(app, ['portfolio', 'performance', '--from', '2025-03-10',
                                    '--to', '2026-03-10', '--account', 'selected'])
    assert result.exit_code == 0, result.stderr
    outcome = json.loads(result.stdout)
    assert outcome['scope'] == 'ACCOUNT'
    assert Decimal(str(outcome['twr']['return'])) == Decimal('0.1')


def test_stale_cash_only_account_cannot_fund_actionable_proposal(ledger):
    accept(ledger, quantity='0', cash='1000', date='2020-03-01')
    sid = register(ledger, 'NEW')
    result = proposal(ledger, {sid: '1'}, ['ira'])
    assert result['status'] == 'BLOCKED'
    assert result['proposed_actions'] == []
    assert any(issue['code'] in {'STALE_CASH', 'STALE_CASH_COVERAGE'} for issue in result['issues'])


def test_partial_position_coverage_blocks_whole_household_proposal(ledger):
    accept(ledger, cash='1000', complete=False)
    sid = register(ledger, 'NEW')
    result = proposal(ledger, {sid: '1'}, ['ira'])
    assert result['status'] == 'BLOCKED'
    assert result['proposed_actions'] == []
    assert any(issue['code'] == 'INCOMPLETE_POSITION_COVERAGE' for issue in result['issues'])


def test_rebalance_uses_retirement_sale_before_equivalent_taxable_sale(ledger):
    accept(ledger, 'a-tax')
    accept(ledger, 'z-ira')
    existing = ledger.resolve('FICT')['id']
    replacement = register(ledger, 'NEW')
    result = proposal(ledger, {existing: '0.5', replacement: '0.5'}, ['a-tax', 'z-ira'],
                      mode='rebalance')
    sales = [row for row in result['proposed_actions'] if row['type'] == 'SELL']
    assert sales
    assert {row['account_id'] for row in sales} == {'z-ira'}
    assert result['estimated_tax_budget_consumption'] == '0'


def test_limited_contribution_addresses_larger_underweight_first(ledger):
    accept(ledger, quantity='0', cash='100')
    first, second = sorted([register(ledger, 'SMALL'), register(ledger, 'LARGE')])
    result = proposal(ledger, {first: '0.3', second: '0.7'}, ['ira'])
    buys = [row for row in result['proposed_actions'] if row['type'] == 'BUY']
    assert buys and buys[0]['security'] == second
