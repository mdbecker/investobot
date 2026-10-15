"""The same observable financial plan serves preview and approved proposals."""
import copy

import pytest
from pytest_bdd import given, scenarios, then, when

from invest.ledger import Ledger
from invest.planning import propose, save_policy
from invest.plans import list_plans, show
from invest.targets import save

scenarios('features/mvp/planning_single_path.feature')


@pytest.fixture
def planning_context(tmp_path):
    ledger = Ledger(tmp_path / 'planner.db')
    yield {'ledger': ledger}
    ledger.connection.close()


def setup(ctx, environment):
    ledger = ctx['ledger']
    ledger.apply({'account': {'id': 'account', 'name': 'Fictional account', 'tax_status': 'TAX_FREE'},
                  'data_environment': environment, 'positions': [], 'lots': [], 'cash': '200',
                  'cash_known': True, 'positions_complete': True, 'lots_complete': True,
                  'source_timestamp': '2026-10-13', 'source_hash': 'fictional-planning'})
    sid = ledger.register_security({'ticker': 'FICTION', 'name': 'Fictional stock',
                                   'asset_type': 'STOCK', 'currency': 'USD',
                                   'source': 'Reviewed fictional identity', 'data_environment': environment})['id']
    ctx['sid'] = sid
    ctx['target'] = save(ledger, {'name': 'Fictional monthly target', 'data_environment': environment,
                                'target_allocations': {sid: '1'},
                                'planning_constraints': {'eligible_accounts': ['account']}})['id']
    ctx['policy'] = {'version': 'fictional-v1', 'data_environment': environment,
                     'source': 'Reviewed fictional assumptions', 'fee_per_trade': '5',
                     'cash_floors': {'account': '50'}, 'minimum_notional': '25',
                     'permissions': {'account': {sid: {'can_buy': True, 'can_sell': False,
                                                      'can_hold': True, 'share_increment': '1'}}}}
    ctx['prices'] = {sid: {'price': '100', 'source': 'Fictional source', 'as_of': '2026-10-13',
                           'currency': 'USD', 'data_environment': environment}}
    ctx['before'] = copy.deepcopy(ledger.state())


@given('a complete synthetic account with 200 cash and an approved target')
def synthetic(planning_context):
    setup(planning_context, 'SYNTHETIC')


@given('a complete real account with 200 cash and an approved target')
def real(planning_context):
    setup(planning_context, 'REAL')


@given('execution fees are unknown')
def unknown(planning_context):
    planning_context['policy'].pop('fee_per_trade')


@given('the sourced price is stale')
def stale(planning_context):
    planning_context['prices'][planning_context['sid']]['as_of'] = '2026-09-01'


def proposal(ctx, policy):
    return propose(ctx['ledger'], ctx['target'], policy=policy, mode='contributions-only',
                   as_of='2026-10-13', prices=ctx['prices'])


@when('an unapproved synthetic contribution is previewed twice')
def preview(planning_context):
    planning_context['results'] = [proposal(planning_context, planning_context['policy']) for _ in range(2)]


@when('a contribution is proposed using a saved approved policy')
def approved(planning_context):
    policy = save_policy(planning_context['ledger'], planning_context['policy'], confirm=True)
    planning_context['results'] = [proposal(planning_context, policy['id'])]


@then('each preview buys one share for 100 with a fee of 5 and preserves a cash floor of 50')
def buys(planning_context):
    for result in planning_context['results']:
        action, = result['proposed_actions']
        assert (action['type'], action['account_id'], action['security'], action['quantity'],
                action['price'], action['notional'], action['fee']) == (
                    'BUY', 'account', planning_context['sid'], '1', '100', '100', '5')
        assert result['cash_after'] == {'account': '95'}


@then('no plans or accepted financial facts are written')
def no_writes(planning_context):
    assert list_plans(planning_context['ledger'])['plans'] == []
    assert planning_context['ledger'].state() == planning_context['before']


@then('the saved plan contains complete executable details and accepted facts remain unchanged')
def saved(planning_context):
    buys(planning_context)
    result = planning_context['results'][0]
    assert show(planning_context['ledger'], result['id'])['proposed_actions'] == result['proposed_actions']
    assert len(list_plans(planning_context['ledger'])['plans']) == 1
    assert planning_context['ledger'].state() == planning_context['before']


@then('the proposal is blocked for missing policy approval without writes')
def blocked(planning_context):
    for result in planning_context['results']:
        assert result['status'] == 'BLOCKED'
        assert result['proposed_actions'] == []
        assert 'UNAPPROVED_TRADING_POLICY' in {issue['code'] for issue in result['issues']}
    no_writes(planning_context)


@then('the fee uncertainty prevents execution review approval')
def fees(planning_context):
    issue = next(issue for issue in planning_context['results'][0]['issues']
                 if issue['code'] == 'UNKNOWN_EXECUTION_FEES')
    assert issue['blocks_execution_review'] is True
    no_writes(planning_context)


@then('no trade is proposed and stale prices are reported')
def stale_result(planning_context):
    assert planning_context['results'][0]['proposed_actions'] == []
    assert 'STALE_PRICES' in {issue['code'] for issue in planning_context['results'][0]['issues']}
    no_writes(planning_context)


@given('a complete taxable portfolio with two verified specific lots and a 34.6 tax allowance')
def taxable(planning_context):
    ctx = planning_context
    ledger = ctx['ledger']
    ledger.apply({'account': {'id': 'account', 'name': 'Fictional tax account',
                              'tax_status': 'TAXABLE', 'history_complete': True},
                  'data_environment': 'SYNTHETIC', 'source_hash': 'fictional-tax-lots',
                  'source_timestamp': '2026-10-13', 'positions_complete': True, 'lots_complete': True,
                  'cash': '0', 'cash_known': True,
                  'positions': [{'security': 'FICTION', 'asset_type': 'STOCK', 'quantity': '5',
                                 'price': '100', 'market_value': '500', 'cost_basis': '380',
                                 'displayed_price_precision': 2, 'displayed_market_value_precision': 2}],
                  'lots': [{'id': lid, 'source_lot_id': lid, 'security': 'FICTION',
                            'quantity': qty, 'remaining_quantity': qty, 'cost_basis': basis,
                            'remaining_adjusted_basis': basis, 'acquisition_date': acquired,
                            'identity_status': 'VERIFIED', 'saleable': True,
                            'identity_source': 'Reviewed fictional broker identity'}
                           for lid, qty, basis, acquired in [('old', '3', '240', '2024-01-01'),
                                                              ('new', '2', '140', '2026-01-01')]]})
    ctx['sid'] = ledger.resolve('FICTION')['id']
    ctx['target'] = save(ledger, {'name': 'Cash target', 'data_environment': 'SYNTHETIC',
                                'target_allocations': {'CASH': '1'},
                                'planning_constraints': {'eligible_accounts': ['account']}})['id']
    ctx['policy'] = {'version': 'fictional-tax-v1', 'data_environment': 'SYNTHETIC',
                     'source': 'Reviewed fictional budget', 'fee_per_trade': '5',
                     'minimum_notional': '25', 'cash_floors': {'account': '0'},
                     'permissions': {'account': {ctx['sid']: {'can_buy': False, 'can_sell': True,
                                                              'can_hold': True, 'share_increment': '1'}}},
                     'annual_tax_budget': {'year': 2026, 'annual_allowance': '34.6',
                         'short_term_rate': '.4', 'long_term_rate': '.2', 'currency': 'USD',
                         'taxable_history_complete': True, 'covered_account_ids': ['account'],
                         'data_environment': 'SYNTHETIC', 'source': 'Reviewed fictional no earlier sales',
                         'as_of': '2026-10-13T00:00:00Z'}}
    ctx['prices'] = {ctx['sid']: {'price': '100', 'source': 'Fictional price',
                                'as_of': '2026-10-13', 'currency': 'USD',
                                'data_environment': 'SYNTHETIC'}}
    ctx['before'] = copy.deepcopy(ledger.state())


@when('the overweight stock is proposed for sale using an approved policy')
def rebalance(planning_context):
    ctx = planning_context
    approved_policy = save_policy(ctx['ledger'], ctx['policy'], confirm=True)
    ctx['results'] = [propose(ctx['ledger'], ctx['target'], policy=approved_policy['id'],
                              mode='rebalance', as_of='2026-10-13', prices=ctx['prices'])]


@then('the sale gain is 115 and conservative tax consumption is 34.6')
def fee_budget(planning_context):
    result = planning_context['results'][0]
    action, = result['proposed_actions']
    assert action['type'] == 'SELL' and action['quantity'] == '5' and action['fee'] == '5'
    assert result['tax_analysis']['realized_gain_loss'] == '115'
    assert result['estimated_tax_budget_consumption'] == '34.6'
    assert result['cash_after'] == {'account': '495'}


@then('accepted lots and balances remain unchanged')
def unchanged(planning_context):
    assert planning_context['ledger'].state() == planning_context['before']


def invoke(ctx, tmp_path, monkeypatch, command, payload, options):
    import json

    from typer.testing import CliRunner

    from invest.cli import app

    monkeypatch.setenv('INVEST_DB', str(ctx['ledger'].path))
    monkeypatch.setenv('INVEST_CONFIG', str(tmp_path / 'absent.toml'))
    path = tmp_path / 'scenario.json'
    path.write_text(json.dumps(payload))
    ctx['cli_result'] = CliRunner().invoke(app, ['plan', command, '--file', str(path), *options])


@when('the public proposal command receives an embedded unsaved target')
def embedded(planning_context, tmp_path, monkeypatch):
    ctx = planning_context
    policy = save_policy(ctx['ledger'], ctx['policy'], confirm=True)
    ctx['targets_before'] = copy.deepcopy(ctx['ledger'].rows('targets'))
    invoke(ctx, tmp_path, monkeypatch, 'propose', {'data_environment': 'SYNTHETIC',
           'account_id': 'account', 'target': {'name': 'Unsaved', 'weights': {ctx['sid']: '1'}},
           'prices': ctx['prices']}, ['--policy', policy['id'], '--mode', 'contributions-only',
                                     '--as-of', '2026-10-13'])


@then('it rejects the target without creating a version or plan')
def embedded_rejected(planning_context):
    assert planning_context['cli_result'].exit_code == 1
    assert planning_context['ledger'].rows('targets') == planning_context['targets_before']
    no_writes(planning_context)


@when('the public preview command receives a saved target and synthetic assumptions')
def public_preview(planning_context, tmp_path, monkeypatch):
    ctx = planning_context
    invoke(ctx, tmp_path, monkeypatch, 'preview', {'policy': ctx['policy'], 'prices': ctx['prices']},
           ['--target', ctx['target'], '--as-of', '2026-10-13'])


@then('the public preview reports executable details without saving')
def public_details(planning_context):
    import json

    result = planning_context['cli_result']
    assert result.exit_code == 0, result.output
    planning_context['results'] = [json.loads(result.stdout)]
    buys(planning_context)
    no_writes(planning_context)


@given('a complete taxable portfolio with two verified loss lots and a reviewed replacement')
def loss_portfolio(planning_context):
    ctx = planning_context
    taxable(ctx)
    ledger = ctx['ledger']
    snapshot = copy.deepcopy(ledger.state()['snapshots'][0])
    for field in ('id', 'fingerprint', 'override_justification', 'override_kind'):
        snapshot.pop(field, None)
    snapshot['source_hash'] = 'fictional-loss-marks'
    snapshot['positions'][0].update(price='70', market_value='350', displayed_price_precision=2,
                                    displayed_market_value_precision=2)
    ledger.apply(snapshot)
    replacement = ledger.register_security({'ticker': 'REPLACE', 'name': 'Fictional replacement',
        'asset_type': 'ETF', 'currency': 'USD', 'source': 'Reviewed fictional fund',
        'data_environment': 'SYNTHETIC'})['id']
    ctx['policy']['permissions']['account'][replacement] = {
        'can_buy': True, 'can_sell': False, 'can_hold': True, 'share_increment': '.01'}
    ctx['prices'][ctx['sid']]['price'] = '70'
    ctx['policy']['harvest_review'] = {
        'loss_sale_date': '2026-10-13', 'security': ctx['sid'], 'data_environment': 'SYNTHETIC',
        'spouse_history_complete': True, 'outside_account_history_complete': True,
        'dividend_reinvestment_history_complete': True,
        'replacement': {'security': replacement, 'substantially_identical': False,
                        'approved_for_purchase': True, 'source': 'Reviewed fictional mandates',
                        'source_locator': 'https://example.invalid/mandates'},
        'price_observations': {**ctx['prices'], replacement: {'price': '50',
            'as_of': '2026-10-13', 'data_environment': 'SYNTHETIC', 'currency': 'USD',
            'source': 'Fictional sourced mark'}}}
    ctx['before'] = copy.deepcopy(ledger.state())


@when('approved harvest and rebalance estimate the same loss sale')
def matching_workflows(planning_context):
    from invest.planning import get_policy
    from invest.tax import harvest_plan

    ctx = planning_context
    rebalance(ctx)
    ctx['harvest'] = harvest_plan(ctx['ledger'].state(), get_policy(ctx['ledger'], ctx['policy']['version']),
                                 '2026-10-13')


@then('both estimate a 35 loss and zero positive tax consumption while retaining wash review')
def matching_loss(planning_context):
    ctx = planning_context
    rebalance_result = ctx['results'][0]
    harvest_result = ctx['harvest']
    assert rebalance_result['tax_analysis']['realized_gain_loss'] == '-35'
    assert harvest_result['tax_analysis']['realized_gain_loss'] == '-35'
    assert rebalance_result['estimated_tax_budget_consumption'] == '0'
    assert harvest_result['estimated_tax_budget_consumption'] == '0'
    assert 'HUMAN_WASH_SALE_REVIEW' in {issue['code'] for issue in harvest_result['issues']}
    assert harvest_result['legal_wash_sale_safe'] is None
    assert ctx['ledger'].state() == ctx['before']


@given('the accepted source permits storage but blocks trade proposals')
def source_gate(planning_context):
    ctx = planning_context
    snapshot = copy.deepcopy(ctx['ledger'].state()['snapshots'][0])
    for field in ('id', 'fingerprint', 'override_justification', 'override_kind'):
        snapshot.pop(field, None)
    snapshot['source_hash'] = 'fictional-provisional-source'
    snapshot['issues'] = [{'code': 'PROVISIONAL_ADAPTER', 'message': 'Review original source',
                           'blocks_acceptance': False, 'blocks_calculation': False,
                           'blocks_proposals': True, 'blocks_execution_review': True}]
    ctx['ledger'].apply(snapshot)
    ctx['before'] = copy.deepcopy(ctx['ledger'].state())


@then('the typed source issue survives and no trade is proposed')
def source_blocked(planning_context):
    result = planning_context['results'][0]
    assert result['proposed_actions'] == []
    issue = next(issue for issue in result['issues'] if issue['code'] == 'PROVISIONAL_ADAPTER')
    assert issue['blocks_calculation'] is False
    assert issue['blocks_proposals'] is True
    assert issue['blocks_execution_review'] is True
    unchanged(planning_context)


@given('the sourced price is 100 plus a residue at decimal place 150')
def precise_price(planning_context):
    planning_context['prices'][planning_context['sid']]['price'] = '100.' + '0' * 149 + '1'


@then('the one share purchase preserves the exact remaining cash residue')
def precise_cash(planning_context):
    from fractions import Fraction

    result = planning_context['results'][0]
    action, = result['proposed_actions']
    assert action['quantity'] == '1'
    assert action['price'] == planning_context['prices'][planning_context['sid']]['price']
    assert Fraction(result['cash_after']['account']) == Fraction(95) - Fraction(1, 10**150)
    unchanged(planning_context)


@given('a later accepted source receipt has the same import time and blocks trade proposals')
def tied_harvest_source(planning_context):
    ctx = planning_context
    latest_id = ctx['ledger'].planning_state()['snapshots'][0]['id']
    snapshot = copy.deepcopy(next(row for row in ctx['ledger'].state()['snapshots']
                                  if row['id'] == latest_id))
    ctx['tied_import_time'] = snapshot['imported_at']
    for field in ('id', 'fingerprint', 'override_justification', 'override_kind'):
        snapshot.pop(field, None)
    snapshot['source_hash'] = 'fictional-tied-harvest-source'
    snapshot['issues'] = [{'code': 'PROVISIONAL_ADAPTER', 'message': 'Review original source',
                           'blocks_acceptance': False, 'blocks_calculation': False,
                           'blocks_proposals': True, 'blocks_execution_review': True}]
    ctx['newest_receipt'] = ctx['ledger'].apply(snapshot)['snapshot_id']
    ctx['before'] = copy.deepcopy(ctx['ledger'].state())


@then('harvest retains the source blocker and proposes no trades')
def harvest_source_blocked(planning_context):
    result = planning_context['harvest']
    assert result['proposed_actions'] == []
    issue = next(issue for issue in result['issues'] if issue['code'] == 'PROVISIONAL_ADAPTER')
    assert issue['blocks_calculation'] is False
    assert issue['blocks_proposals'] is True
    assert issue['blocks_execution_review'] is True
    unchanged(planning_context)


@then('harvest pins the same latest receipt fingerprint as the ledger')
def harvest_receipt_pin(planning_context):
    from invest.financial_state import state_hash

    ctx = planning_context
    projected = ctx['ledger'].planning_state()
    receipt, = projected['snapshots']
    assert receipt['id'] == ctx['newest_receipt']
    assert receipt['imported_at'] == ctx['tied_import_time']
    assert ctx['harvest']['source_state_hash'] == state_hash(projected)
