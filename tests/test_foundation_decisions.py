"""Given accepted synthetic facts, proposals follow financial constraints on any date."""

import copy
import json
from decimal import Decimal

import pytest
from typer.testing import CliRunner

from invest.cli import app
from invest.ledger import Ledger
from invest.models import DomainError, Snapshot
from invest.planning import propose, save_policy
from invest.policy_models import TradingPolicyInput
from invest.simulations import simulate
from invest.targets import save


@pytest.fixture
def household(tmp_path):
    ledger = Ledger(tmp_path / 'synthetic.db')
    ledger.apply({'data_environment': 'SYNTHETIC',
        'account': {'id': 'ira', 'name': 'Fictional retirement', 'tax_status': 'TAX_FREE'},
        'positions': [{'security': 'OLD', 'asset_type': 'ETF', 'quantity': '10',
            'price': '100', 'market_value': '1000', 'cost_basis': '500', 'as_of': '2026-02-01',
            'displayed_price_precision': 2, 'displayed_market_value_precision': 2}],
        'lots': [{'id': 'old-lot', 'security': 'OLD', 'quantity': '10',
            'remaining_quantity': '10', 'cost_basis': '500', 'acquisition_date': '2024-01-01',
            'identity_status': 'VERIFIED', 'source_lot_id': 'fictional-old',
            'identity_source': 'Reviewed fictional statement', 'saleable': True}],
        'cash_known': True, 'cash': '0', 'positions_complete': True, 'lots_complete': True,
        'source_timestamp': '2026-02-01', 'source_hash': 'fictional-opening'})
    old = ledger.resolve('OLD')['id']
    new = ledger.register_security({'ticker': 'NEW', 'name': 'Fictional replacement',
        'asset_type': 'ETF', 'currency': 'USD', 'source': 'Fictional identity'})['id']
    policy = {'version': 'reviewed', 'source': 'Human reviewed synthetic policy',
        'data_environment': 'SYNTHETIC', 'fee_per_trade': '0', 'minimum_notional': '1',
        'permissions': {'ira': {sid: {'can_buy': True, 'can_sell': True, 'can_hold': True,
            'share_increment': '0.01'} for sid in [old, new]}}}
    yield {'ledger': ledger, 'old': old, 'new': new, 'policy': policy}
    ledger.connection.close()


def proposal(ctx, day='2026-02-10', weight='0.6', mode='rebalance'):
    target = save(ctx['ledger'], {'name': 'Fictional target',
        'target_allocations': {ctx['old']: weight, ctx['new']: str(1 - Decimal(weight))},
        'planning_constraints': {'eligible_accounts': ['ira']}})
    policy = save_policy(ctx['ledger'], ctx['policy'], confirm=True)
    return propose(ctx['ledger'], target['id'], policy=policy['id'], mode=mode,
        as_of=day, prices={sid: {'price': '100', 'currency': 'USD',
            'data_environment': 'SYNTHETIC', 'source': 'Fictional price', 'as_of': day}
            for sid in [ctx['old'], ctx['new']]})


def test_february_and_march_reviewed_rebalances_propose_same_sale_and_buy(household):
    """When only the date changes, then the exact permitted financial actions agree."""
    before = copy.deepcopy(household['ledger'].state())
    february = proposal(household)
    march = proposal(household, '2026-03-10')
    assert [(a['type'], a['quantity']) for a in february['proposed_actions']] == [('SELL', '4'), ('BUY', '4')]
    assert [{k: v for k, v in a.items() if k != 'date'} for a in february['proposed_actions']] == [
        {k: v for k, v in a.items() if k != 'date'} for a in march['proposed_actions']]
    assert not {'CADENCE_NOT_ELIGIBLE', 'MONTHLY_CADENCE_USED'} & {i['code'] for i in february['issues']}
    assert 'cadence' not in february
    assert household['ledger'].state() == before


def test_small_positive_drift_can_rebalance_above_minimum_notional(household):
    result = proposal(household, weight='0.99')
    assert [(a['type'], a['quantity']) for a in result['proposed_actions']] == [('SELL', '0.1'), ('BUY', '0.1')]


def test_contributions_only_never_sells(household):
    assert proposal(household, mode='contributions-only')['proposed_actions'] == []


def test_live_policy_contract_has_no_calendar_controls(household):
    assert not {'quarterly_months', 'drift_trigger', 'exception_approved', 'exception_reason'} & set(
        TradingPolicyInput.model_json_schema()['properties'])


def test_confirmed_purchase_this_month_does_not_block_later_contribution(household):
    ledger = household['ledger']
    ledger.record_activity({'activity_id': 'cash', 'account_id': 'ira', 'type': 'CASH_DEPOSIT',
        'amount': '500', 'date': '2026-02-02'}, yes=True)
    ledger.record_activity({'activity_id': 'buy', 'account_id': 'ira', 'type': 'BUY',
        'security': household['old'], 'quantity': '1', 'price': '100', 'fee': '0',
        'date': '2026-02-03'}, yes=True)
    result = proposal(household, mode='contributions-only')
    assert result['proposed_actions'] and all(a['type'] == 'BUY' for a in result['proposed_actions'])
    assert 'MONTHLY_CADENCE_USED' not in {i['code'] for i in result['issues']}


def basisless(ctx, status='TAX_FREE', lot_quantity='10'):
    ledger = ctx['ledger']
    with ledger.connection:
        account = ledger.rows('accounts')[0]
        ledger.put('accounts', account['id'], dict(account, tax_status=status))
        lot = ledger.rows('lots')[0]
        ledger.put('lots', lot['id'], dict(lot, cost_basis=None, remaining_adjusted_basis=None,
            acquisition_date=None, remaining_quantity=lot_quantity))
        position = ledger.rows('positions')[0]
        ledger.put('positions', position['id'], dict(position, cost_basis=None))


def sale(ctx, quantity='4'):
    return {'type': 'SELL', 'account_id': 'ira', 'security': ctx['old'], 'quantity': quantity,
        'price': '100', 'fee': '1', 'date': '2026-03-10',
        'lot_allocations': [{'lot_id': 'old-lot', 'quantity': quantity}]}


@pytest.mark.parametrize('status', ['TAX_FREE', 'TAX_DEFERRED'])
def test_basisless_retirement_sale_conserves_shares_cash_and_unknown_tax_facts(household, status):
    basisless(household, status)
    ledger = household['ledger']
    before = copy.deepcopy(ledger.state())
    result = simulate(before, [sale(household)])
    assert ledger.state() == before
    lot = result['after']['lots'][0]
    assert Decimal(lot['remaining_quantity']) == 6
    assert lot['cost_basis'] is None and lot['remaining_adjusted_basis'] is None
    assert result['after']['positions'][0]['cost_basis'] is None
    assert Decimal(result['after']['cash_balances'][0]['amount']) == 399
    proposed = proposal(household, '2026-03-10')
    assert proposed['estimated_tax_budget_consumption'] == '0'
    assert proposed['proposed_actions'][0]['lot_allocations'] == [{'lot_id': 'old-lot', 'quantity': '4'}]
    ledger.record_activity(dict(sale(household), activity_id='reviewed-sale'), yes=True)
    allocated = ledger.rows('activities')[0]['lot_allocations'][0]
    assert allocated['basis_removed'] is None and allocated['term'] is None
    assert allocated['realized_gain'] is None
    assert ledger.record_activity(dict(sale(household), activity_id='reviewed-sale'), yes=True)['status'] == 'UNCHANGED'


def test_basisless_taxable_sale_is_typed_and_atomic(household):
    basisless(household, 'TAXABLE')
    before = copy.deepcopy(household['ledger'].state())
    with pytest.raises(DomainError) as failure:
        household['ledger'].record_activity(dict(sale(household), activity_id='invalid'), yes=True)
    assert failure.value.code == 3
    assert 'UNRESOLVED_LOTS' in {i['code'] for i in failure.value.result['issues']}
    assert household['ledger'].state() == before
    assert not proposal(household, '2026-03-10')['proposed_actions']


@pytest.mark.parametrize('quantity,lot_quantity', [('11', '10'), ('4', '3'), ('4', '12')])
def test_impossible_or_inconsistent_retirement_sale_is_typed_and_atomic(household, quantity, lot_quantity):
    basisless(household, lot_quantity=lot_quantity)
    before = copy.deepcopy(household['ledger'].state())
    with pytest.raises(DomainError) as failure:
        household['ledger'].record_activity(dict(sale(household, quantity), activity_id='invalid'), yes=True)
    assert failure.value.code == 3
    assert failure.value.result['issues']
    assert household['ledger'].state() == before
    if quantity == '4':
        result = proposal(household, '2026-03-10')
        assert not result['proposed_actions']
        assert 'UNRESOLVED_LOTS' in {i['code'] for i in result['issues']}


def test_retirement_intake_accepts_sourced_quantity_without_tax_date(household):
    ledger = household['ledger']
    candidate = {k: copy.deepcopy(v) for k, v in ledger.state()['snapshots'][0].items()
                 if k in Snapshot.model_fields}
    candidate['lots'][0].update(acquisition_date=None, cost_basis=None)
    candidate['positions'][0]['cost_basis'] = None
    candidate.update(source_hash='fictional-basisless', source_timestamp='2026-02-02')
    assert ledger.apply(candidate)['status'] == 'APPLIED'
    assert ledger.rows('lots')[0]['acquisition_date'] is None


@pytest.mark.parametrize('environment', ['REAL', 'SYNTHETIC'])
def test_cli_import_explicit_environment_reaches_parser_without_contradiction(tmp_path, monkeypatch, environment):
    """Given supplied HTML, when CLI previews it, then parser provenance agrees."""
    monkeypatch.setenv('INVEST_DB', str(tmp_path / 'absent.db'))
    page = tmp_path / 'fictional.html'
    page.write_text('<table><tr><th>Symbol</th><th>Quantity</th><th>Price</th><th>Market Value</th></tr>'
        '<tr><td>FAKE</td><td>2</td><td>100.00</td><td>200.00</td></tr>'
        '<tr><td>CASH</td><td></td><td></td><td>50.00</td></tr></table>')
    result = CliRunner().invoke(app, ['portfolio', 'import', str(page), '--account', 'fictional',
        '--institution', 'vanguard', '--as-of', '2026-02-01', '--data-environment', environment])
    assert result.exit_code == 0, result.output
    candidate = json.loads(result.stdout)
    assert candidate['data_environment'] == environment
    assert 'UNKNOWN_DATA_ENVIRONMENT' not in {i['code'] for i in candidate['issues']}
    assert 'UNVALIDATED_INSTITUTION_ADAPTER' in {i['code'] for i in candidate['issues']}
    assert not (tmp_path / 'absent.db').exists()


@pytest.mark.parametrize('option', [[], ['--data-environment', 'UNKNOWN']])
def test_cli_import_requires_explicit_valid_environment_before_reading_file(option):
    result = CliRunner().invoke(app, ['portfolio', 'import', '/absent.html', '--account', 'fictional', *option])
    assert result.exit_code == 1
    assert 'environment' in json.loads(result.stderr)['error'].lower()


def test_blocking_parser_evidence_cannot_be_overridden_into_complete_acceptance(household):
    ledger = household['ledger']
    candidate = {k: copy.deepcopy(v) for k, v in ledger.state()['snapshots'][0].items()
                 if k in Snapshot.model_fields}
    candidate.update(source_hash='fictional-unresolved', source_timestamp='2026-02-02',
        issues=[{'code': 'UNRESOLVED_SOURCE_ROW', 'message': 'Omitted financial source row',
            'blocks_calculation': True, 'blocks_proposal': True, 'blocks_execution_review': True}])
    before = copy.deepcopy(ledger.state())
    with pytest.raises(DomainError) as failure:
        ledger.apply(candidate)
    assert failure.value.code == 3
    assert 'UNRESOLVED_SOURCE_ROW' in {i['code'] for i in failure.value.result['issues']}
    assert ledger.state() == before
