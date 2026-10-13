"""Reviewed immutable harvest policies produce conditional, never executable trades."""

import copy
import json

import pytest
from typer.testing import CliRunner

from invest.cli import app
from invest.ledger import Ledger
from invest.planning import get_policy, list_policies, save_policy
from invest.plans import state_hash
from invest.tax import harvest_plan


@pytest.fixture
def household(tmp_path, monkeypatch):
    ledger = Ledger(tmp_path / 'fictional.db')
    monkeypatch.setenv('INVEST_DB', str(ledger.path))
    monkeypatch.setenv('INVEST_CONFIG', str(tmp_path / 'absent.toml'))
    positions = [{'security': ticker, 'asset_type': 'ETF', 'quantity': quantity,
                  'price': price, 'market_value': value, 'cost_basis': basis,
                  'displayed_price_precision': 2, 'displayed_market_value_precision': 2,
                  'as_of': '2026-09-01'} for ticker, quantity, price, value, basis in
                 [('LOSS', '10', '80', '800', '1000'), ('GAIN', '1', '120', '120', '80')]]
    lots = [{'id': ticker + '-lot', 'source_lot_id': ticker + '-lot',
             'security': ticker, 'quantity': quantity, 'remaining_quantity': quantity,
             'cost_basis': basis, 'remaining_adjusted_basis': basis,
             'acquisition_date': '2024-01-01', 'identity_status': 'VERIFIED',
             'identity_source': 'Human-reviewed fictional immutable broker reference',
             'saleable': True} for ticker, quantity, basis in
            [('LOSS', '10', '1000'), ('GAIN', '1', '80')]]
    snapshot = {'account': {'id': 'tax', 'name': 'Fictional taxable account',
                           'tax_status': 'TAXABLE', 'currency': 'USD', 'history_complete': True},
                'positions': positions, 'lots': lots, 'cash': '100', 'cash_known': True,
                'positions_complete': True, 'lots_complete': True,
                'source_timestamp': '2026-09-01', 'source_hash': 'fictional-opening',
                'data_environment': 'SYNTHETIC'}
    ledger.apply(snapshot)
    loss = ledger.resolve('LOSS')['id']
    ledger.record_activity({'activity_id': 'fictional-prior-gain', 'account_id': 'tax',
        'type': 'SELL', 'security': 'GAIN', 'quantity': '1', 'price': '120', 'fee': '0',
        'date': '2026-09-02', 'source': 'Reviewed fictional execution',
        'lot_allocations': [{'lot_id': 'GAIN-lot', 'quantity': '1'}]}, yes=True)
    closing = copy.deepcopy(snapshot)
    closing.update(source_timestamp='2026-10-10', source_hash='fictional-closing', cash='220')
    closing['positions'] = [dict(positions[0], as_of='2026-10-10')]
    closing['lots'] = [lots[0]]
    ledger.apply(closing)
    replacement = ledger.register_security({'ticker': 'REPLACE', 'name': 'Fictional replacement ETF',
        'asset_type': 'ETF', 'currency': 'USD', 'source': 'Reviewed fictional fund prospectus',
        'data_environment': 'SYNTHETIC'})['id']
    policy = {'id': 'harvest-reviewed-v1', 'version': '1',
        'source': 'Explicit fictional human-reviewed conditional harvest policy',
        'data_environment': 'SYNTHETIC', 'minimum_notional': '25', 'fee_per_trade': '1',
        'cash_floors': {'tax': '220'}, 'max_position_age_days': 30, 'max_cash_age_days': 30,
        'permissions': {'tax': {
            loss: {'can_buy': False, 'can_sell': True, 'can_hold': True, 'share_increment': '0.001'},
            replacement: {'can_buy': True, 'can_sell': False, 'can_hold': True,
                          'share_increment': '0.001'}}},
        'annual_tax_budget': {'year': 2026, 'annual_allowance': '10', 'short_term_rate': '0.4',
            'long_term_rate': '0.2', 'currency': 'USD', 'taxable_history_complete': True,
            'covered_account_ids': ['tax'], 'data_environment': 'SYNTHETIC',
            'source': 'Reviewed fictional complete household sales attestation',
            'as_of': '2026-10-10T00:00:00Z'},
        'harvest_review': {'loss_sale_date': '2026-10-10', 'security': loss,
            'spouse_history_complete': True, 'outside_account_history_complete': True,
            'dividend_reinvestment_history_complete': True, 'data_environment': 'SYNTHETIC',
            'replacement': {'security': replacement, 'substantially_identical': False,
                'approved_for_purchase': True, 'source': 'Reviewed fictional prospectus comparison',
                'source_locator': 'https://example.invalid/funds/replacement#mandate'},
            'price_observations': {sid: {'price': price, 'currency': 'USD',
                'data_environment': 'SYNTHETIC', 'as_of': '2026-10-10',
                'source': 'Reviewed fictional contemporaneous price observation'}
                for sid, price in [(loss, '80'), (replacement, '50')]}}}
    ctx = {'ledger': ledger, 'policy': policy, 'loss': loss, 'replacement': replacement,
           'tmp': tmp_path}
    yield ctx
    ledger.connection.close()


def approve(ctx):
    save_policy(ctx['ledger'], ctx['policy'], confirm=True)
    ctx['before'] = state_hash(ctx['ledger'].planning_state())
    return get_policy(ctx['ledger'], ctx['policy']['id'])


def report(ctx):
    approved = approve(ctx)
    result = harvest_plan(ctx['ledger'].state(), approved, '2026-10-10')
    assert state_hash(ctx['ledger'].planning_state()) == ctx['before']
    return result


def codes(result):
    return {issue['code'] for issue in result['issues']}


def test_reviewed_harvest_proposal_has_exact_fee_basis_budget_and_immutable_pins(household):
    ctx = household
    result = report(ctx)
    assert result['status'] == 'REVIEW_REQUIRED'
    assert 'HUMAN_WASH_SALE_REVIEW' in codes(result)
    assert result['legal_wash_sale_safe'] is None and result['guaranteed_tax_savings'] is None
    assert result['policy_id'] == ctx['policy']['id'] and result['policy_version'] == '1'
    policy_hash = list_policies(ctx['ledger'])['policies'][0]['policy_hash']
    assert result['policy_hash'] == policy_hash
    assert result['source_state_hash'] == ctx['before']
    sell, buy = result['proposed_actions']
    assert (sell['type'], sell['security'], sell['quantity']) == ('SELL', ctx['loss'], '10')
    assert sell['lot_allocations'] == [{'lot_id': 'LOSS-lot', 'quantity': '10'}]
    assert sell['notional'] == '800' and sell['fee'] == '1'
    assert (buy['type'], buy['security'], buy['quantity']) == ('BUY', ctx['replacement'], '15.96')
    assert buy['notional'] == '798' and buy['fee'] == '1'
    assert result['estimated_net_tax_effect'] == '-40.2'
    assert result['annual_tax_budget']['year_to_date_consumption'] == '8'
    assert result['annual_tax_budget']['remaining_headroom'] == '2'
    assert result['annual_tax_budget']['proposed_positive_tax_cost'] == '0'
    assert result['simulated_cash']['tax'] == '220'
    assert all(action['conditional'] is True for action in result['proposed_actions'])
    repeated = harvest_plan(ctx['ledger'].state(), get_policy(ctx['ledger'], ctx['policy']['id']),
                            '2026-10-10')
    assert repeated == result
    assert state_hash(ctx['ledger'].planning_state()) == ctx['before']


@pytest.mark.parametrize(('mutation', 'issue'), [
    ('fee', 'UNKNOWN_FEES'), ('rates', 'UNKNOWN_TAX_RATES'),
    ('sell', 'SELL_PERMISSION_REQUIRED'), ('buy', 'REPLACEMENT_PERMISSION_REQUIRED'),
    ('increment', 'UNKNOWN_EXECUTION_INCREMENT'),
    ('price_source', 'UNKNOWN_PRICE_PROVENANCE'), ('price_stale', 'STALE_PRICE'),
    ('price_currency', 'CURRENCY_MISMATCH'), ('price_environment', 'MIXED_DATA_ENVIRONMENT'),
    ('history', 'INCOMPLETE_TAXABLE_HISTORY'), ('replacement_source', 'UNVERIFIED_REPLACEMENT'),
])
def test_missing_required_facts_block_conditional_trades_without_mutation(household, mutation, issue):
    ctx = household
    policy = ctx['policy']
    price = policy['harvest_review']['price_observations'][ctx['replacement']]
    if mutation == 'fee':
        policy.pop('fee_per_trade')
    elif mutation == 'rates':
        policy['annual_tax_budget'].pop('long_term_rate')
    elif mutation in {'sell', 'buy'}:
        sid, flag = (ctx['loss'], 'can_sell') if mutation == 'sell' else (ctx['replacement'], 'can_buy')
        policy['permissions']['tax'][sid][flag] = False
    elif mutation == 'increment':
        policy['permissions']['tax'][ctx['replacement']].pop('share_increment')
    elif mutation == 'price_source':
        price.pop('source')
    elif mutation == 'price_stale':
        price['as_of'] = '2026-01-01'
    elif mutation == 'price_currency':
        price['currency'] = 'EUR'
    elif mutation == 'price_environment':
        price['data_environment'] = 'REAL'
    elif mutation == 'history':
        policy['annual_tax_budget']['taxable_history_complete'] = False
    else:
        policy['harvest_review']['replacement'].pop('source')
    result = report(ctx)
    assert issue in codes(result)
    assert result['proposed_actions'] == []
    assert any(row['blocks_proposal'] for row in result['issues'] if row['code'] == issue)


def test_increment_floor_and_minimum_notional_prevent_impossible_replacement(household):
    ctx = household
    ctx['policy']['cash_floors']['tax'] = '1000'
    ctx['policy']['minimum_notional'] = '25'
    result = report(ctx)
    assert result['proposed_actions'] == []
    assert {'INSUFFICIENT_REPLACEMENT_CASH', 'MINIMUM_NOTIONAL'} & codes(result)


def test_untracked_spouse_history_keeps_estimates_but_suppresses_conditional_actions(household):
    ctx = household
    ctx['policy']['harvest_review']['spouse_history_complete'] = False
    result = report(ctx)
    assert 'UNKNOWN_OUTSIDE_ACCOUNT_HISTORY' in codes(result)
    assert result['proposed_actions'] == []
    assert result['status'] == 'REVIEW_REQUIRED'
    assert result['guaranteed_tax_savings'] is None


def test_public_harvest_cli_loads_approved_version_and_discovery(household):
    ctx = household
    approve(ctx)
    runner = CliRunner()
    described = runner.invoke(app, ['tools', 'describe', 'tax.harvest-plan'])
    assert described.exit_code == 0, described.output
    assert '--policy-version' in json.dumps(json.loads(described.stdout))
    result = runner.invoke(app, ['tax', 'harvest-plan', '--policy-version', ctx['policy']['id'],
                                 '--as-of', '2026-10-10'])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload['policy_id'] == ctx['policy']['id']
    assert len(payload['proposed_actions']) == 2
    assert payload['status'] == 'REVIEW_REQUIRED'
    assert state_hash(ctx['ledger'].planning_state()) == ctx['before']


def test_unsaved_policy_never_authorizes_harvest_proposal(household):
    ctx = household
    unsaved = copy.deepcopy(ctx['policy'])
    unsaved.pop('id')
    before = state_hash(ctx['ledger'].planning_state())
    result = harvest_plan(ctx['ledger'].state(), unsaved, '2026-10-10')
    assert 'UNAPPROVED_HARVEST_POLICY' in codes(result)
    assert result['proposed_actions'] == []
    assert state_hash(ctx['ledger'].planning_state()) == before


def test_missing_saved_policy_cli_is_typed_and_read_only(household):
    before = state_hash(household['ledger'].planning_state())
    result = CliRunner().invoke(app, ['tax', 'harvest-plan', '--policy-version', 'absent-policy',
                                     '--as-of', '2026-10-10'])
    assert result.exit_code == 3, result.output
    assert json.loads(result.stderr)['code'] == 3
    assert state_hash(household['ledger'].planning_state()) == before


@pytest.mark.parametrize(('mutation', 'issue'), [
    ('lot', 'UNVERIFIED_LOT_IDENTITY'), ('cash', 'UNKNOWN_CASH'),
    ('account_environment', 'MIXED_DATA_ENVIRONMENT'), ('date', 'HARVEST_DATE_MISMATCH'),
    ('budget', 'UNKNOWN_ANNUAL_TAX_BUDGET'),
])
def test_invalid_financial_state_or_policy_suppresses_actions(household, mutation, issue):
    ctx = household
    if mutation == 'lot':
        with ctx['ledger'].connection:
            lot = next(row for row in ctx['ledger'].rows('lots') if row['id'] == 'LOSS-lot')
            ctx['ledger'].put('lots', lot['id'], dict(lot, identity_status='UNRESOLVED'))
    elif mutation == 'cash':
        with ctx['ledger'].connection:
            ctx['ledger'].connection.execute('DELETE FROM cash_balances')
    elif mutation == 'account_environment':
        with ctx['ledger'].connection:
            row = ctx['ledger'].rows('accounts')[0]
            ctx['ledger'].put('accounts', row['id'], dict(row, data_environment='REAL'))
    elif mutation == 'date':
        ctx['policy']['harvest_review']['loss_sale_date'] = '2026-10-11'
    else:
        ctx['policy'].pop('annual_tax_budget')
    result = report(ctx)
    assert issue in codes(result)
    assert result['proposed_actions'] == []


def test_supplied_policy_id_without_saved_identity_cannot_authorize_proposals(household):
    result = harvest_plan(household['ledger'].state(), household['policy'], '2026-10-10')
    assert 'UNAPPROVED_HARVEST_POLICY' in codes(result)
    assert result['proposed_actions'] == []


def test_new_price_above_remaining_basis_cannot_be_reported_as_loss_harvest(household):
    household['policy']['harvest_review']['price_observations'][household['loss']]['price'] = '200'
    result = report(household)
    assert 'NOT_A_LOSS_AT_PROPOSED_PRICE' in codes(result)
    assert result['proposed_actions'] == []


def test_modifying_loaded_policy_payload_invalidates_its_approval(household):
    approved = approve(household)
    approved['fee_per_trade'] = '0'
    result = harvest_plan(household['ledger'].state(), approved, '2026-10-10')
    assert 'UNAPPROVED_HARVEST_POLICY' in codes(result)
    assert result['proposed_actions'] == []


@pytest.mark.parametrize('field', ['price', 'permission'])
def test_harvest_policy_rejects_inexact_or_coerced_source_facts(household, field):
    from pydantic import ValidationError

    from invest.policy_models import TradingPolicyInput

    payload = household['policy']
    if field == 'price':
        payload['harvest_review']['price_observations'][household['loss']]['price'] = 80.0
    else:
        payload['harvest_review']['replacement']['approved_for_purchase'] = 'true'
    with pytest.raises(ValidationError):
        TradingPolicyInput.model_validate(payload)
