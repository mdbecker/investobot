"""Unified MVP accounting cases; fictional inputs, real ledger and public boundaries."""

import copy
import importlib
import json
import math
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from typer.testing import CliRunner

from invest.cli import app
from invest.ledger import Ledger
from invest.models import DomainError
from invest.parsers.generic import parse_html

scenarios('features/mvp/accounting.feature')


@pytest.fixture
def accounting(tmp_path, monkeypatch):
    path = tmp_path / 'fictional-accounting.db'
    monkeypatch.setenv('INVEST_DB', str(path))
    monkeypatch.setenv('INVEST_PROMPTS', str(tmp_path / 'prompts'))
    ledger = Ledger(path)
    yield {'ledger': ledger, 'directory': tmp_path, 'runner': CliRunner()}
    ledger.connection.close()


def snapshot(account='taxable', date='2026-10-09', quantity='10', basis='900', cash='1000'):
    return {
        'account': {'id': account, 'name': 'Fictional ' + account,
                    'tax_status': 'TAX_FREE' if account == 'ira' else 'TAXABLE',
                    'history_complete': True},
        'positions': [{'security': 'FICTION', 'name': 'Invented security',
                       'asset_type': 'STOCK', 'quantity': quantity, 'price': '100',
                       'market_value': str(Decimal(quantity) * 100), 'cost_basis': basis,
                       'as_of': date, 'displayed_price_precision': 2,
                       'displayed_market_value_precision': 2}],
        'lots': [{'id': account + '-broker-lot', 'security': 'FICTION',
                  'acquisition_date': '2024-01-01', 'quantity': quantity,
                  'remaining_quantity': quantity, 'cost_basis': basis,
                  'remaining_adjusted_basis': basis,
                  'source_lot_id': account + '-broker-lot', 'identity_status': 'VERIFIED',
                  'identity_source': 'Reviewed fictional original broker record: ' + account + '/broker-lot'}],
        'cash': cash, 'cash_known': True, 'positions_complete': True,
        'lots_complete': True, 'source_timestamp': date,
        'source_hash': f'{account}:{date}:{quantity}:{basis}:{cash}',
        'data_environment': 'SYNTHETIC',
    }


def activity(kind='CASH_DEPOSIT', id='deposit', **fields):
    return {'activity_id': id, 'account_id': 'taxable', 'type': kind,
            'date': '2026-10-10', **fields}


def issue_codes(result):
    return {row['code'] for row in result.get('issues', [])}


def invoke(ctx, args):
    result = ctx['runner'].invoke(app, args)
    assert result.exit_code == 0, (
        f'Required public command unavailable: {args}; stderr={result.stderr}'
    )
    assert not result.stderr
    return json.loads(result.stdout)


@given(parsers.parse('accounting case {case} has {description}'))
def case_setup(accounting, case, description):
    ctx = accounting
    ctx['case'] = case
    ctx['description'] = description
    snap = snapshot()
    if case in {'B20', 'B21', 'B22', 'B23', 'B24'}:
        snap = snapshot(date='2025-10-10', cash='0')
    if case in {'B28', 'B29'}:
        snap = snapshot(basis='1200')
    if case == 'B09':
        snap.pop('cash')
        snap['cash_known'] = False
        snap['positions'].append({**snap['positions'][0], 'security': 'SECOND'})
        snap['lots'] = []
        snap['lots_complete'] = False
    if case in {'B10', 'B30'}:
        snap = snapshot(quantity='4', basis='360')
        snap['lots'][0]['quantity'] = '10'
        snap['lots'][0]['cost_basis'] = '900'
        snap['lots'][0]['remaining_adjusted_basis'] = '360'
        # The initial accepted pre-sale observation is internally consistent.
        if case == 'B10':
            snap = snapshot(quantity='10', basis='1000')
    if case == 'B14':
        snap['positions'][0].update(security='SAME', cusip='111111111')
        snap['lots'][0]['security'] = 'SAME'
    ctx['ledger'].apply(snap)
    ctx['candidate'] = copy.deepcopy(snap)
    if case == 'B06':
        ctx['candidate']['positions'][0]['market_value'] = '100'
        ctx['candidate']['source_hash'] = 'contradictory-value'
    elif case in {'B07', 'B08'}:
        ctx['ledger'].record_activity(activity('BUY', 'purchase', security='FICTION',
            quantity='1', price='100', fee='0'), yes=True)
        ctx['candidate']['source_timestamp'] = '2026-10-09' if case == 'B07' else '2026-10-10'
        ctx['candidate']['source_hash'] = 'late-observation'
        ctx['candidate']['imported_at'] = '2026-10-11T12:00:00Z'
    elif case == 'B11':
        ctx['ledger'].record_activity(activity(amount='10'), yes=True)
    elif case == 'B12':
        ctx['ledger'].register_security({'ticker': 'UNMARKED', 'currency': 'USD',
            'name': 'Unmarked fictional security', 'asset_type': 'STOCK',
            'source': 'Fictional source identity'})
        ctx['ledger'].record_activity(activity('BUY', 'unmarked-buy', security='UNMARKED',
            quantity='1', price='20', fee='0'), yes=True)
    elif case == 'B14':
        ctx['candidate']['positions'][0]['cusip'] = '222222222'
        ctx['candidate']['source_hash'] = 'strong-id-conflict'
    elif case.startswith('B2'):
        prepare_analysis_case(ctx)
    ctx['before'] = ctx['ledger'].state()


def prepare_analysis_case(ctx):
    """Persist dated history and immutable test input, never mock financial engines."""
    case = ctx['case']
    if case in {'B20', 'B21', 'B22', 'B23', 'B24'}:
        ctx['start'], ctx['end'] = '2025-10-10', '2026-10-10'
        for account in (['ira'] if case == 'B22' else []):
            opening = snapshot(account, '2025-10-10', quantity='10', basis='900', cash='0')
            ctx['ledger'].apply(opening)
        if case in {'B20', 'B24'}:
            if case == 'B20':
                boundary = snapshot(date='2026-04-10', cash='100')
                boundary['source_timestamp'] = '2026-04-10T11:59:00Z'
                ctx['ledger'].apply(boundary)
            ctx['ledger'].record_activity(activity('CASH_DEPOSIT', 'flow-boundary',
                amount='100', date='2026-04-10',
                event_timestamp='2026-04-10T12:00:00Z'), yes=True)
            if case == 'B20':
                after = snapshot(date='2026-04-10', cash='200')
                after['source_timestamp'] = '2026-04-10T12:01:00Z'
                ctx['ledger'].apply(after)
            closing = snapshot(date='2026-10-10', cash='320')
        elif case == 'B23':
            ctx['ledger'].record_activity(activity('DIVIDEND', 'retained-dividend', amount='50'), yes=True)
            ctx['ledger'].record_activity(activity('BUY', 'dividend-buy', security='FICTION',
                quantity='0.5', price='100', fee='0'), yes=True)
            closing = snapshot(date='2026-10-10', quantity='10.5', basis='950', cash='0')
        else:
            closing = snapshot(date='2026-10-10', cash='100' if case == 'B21' else '0')
        if case == 'B22':
            # Explicitly linked paired legs; account flows are external, household flows cancel.
            ctx['performance_input'] = {
                'from_date': ctx['start'], 'to_date': ctx['end'], 'scope': 'HOUSEHOLD',
                'data_environment': 'SYNTHETIC', 'cash_flow_history_complete': True,
                'checkpoints': [
                    {'date': ctx['start'], 'value': '2000', 'complete': True},
                    {'date': ctx['end'], 'value': '2000', 'complete': True}],
                'cash_flows': [
                    {'id': 'out', 'account_id': 'taxable', 'amount': '-200',
                     'date': '2026-04-10', 'transfer_id': 'pair', 'classification': 'INTERNAL_TRANSFER'},
                    {'id': 'in', 'account_id': 'ira', 'amount': '200',
                     'date': '2026-04-10', 'transfer_id': 'pair', 'classification': 'INTERNAL_TRANSFER'}]}
        ctx['ledger'].apply(closing)
    elif case in {'B26', 'B27'}:
        ctx['budget_input'] = {'year': 2026, 'annual_allowance': '500',
            'short_term_rate': '0.40', 'long_term_rate': '0.20', 'currency': 'USD',
            'taxable_history_complete': True, 'data_environment': 'SYNTHETIC',
            'source': 'Fictional complete taxable-account sale attestation',
            'as_of': '2026-10-10T12:00:00Z',
            'proposed_positive_tax_cost': '400' if case == 'B26' else '0'}
        if case == 'B26':
            ctx['ledger'].record_activity(activity('SELL', 'confirmed-taxable-sale',
                security='FICTION', quantity='5', price='290', fee='0',
                lot_allocations=[{'lot_id': 'taxable-broker-lot', 'quantity': '5'}]), yes=True)
        with ctx['ledger'].connection:
            for index, estimate in enumerate(['400', '100']):
                ctx['ledger'].put('trade_proposals', f'unexecuted-{index}',
                    {'id': f'unexecuted-{index}', 'status': 'READY_FOR_HUMAN_REVIEW',
                     'executed': False, 'estimated_positive_tax_cost': estimate})
    elif case in {'B28', 'B29'}:
        ctx['ledger'].apply(snapshot('ira', '2026-09-20'))
        ctx['ledger'].record_activity(activity('BUY', 'ira-acquisition', account_id='ira',
            date='2026-09-20', security='FICTION', quantity='1', price='100', fee='0'), yes=True)
        ctx['harvest_input'] = {'loss_sale_date': '2026-10-10', 'security': 'FICTION',
            'spouse_history_complete': False if case == 'B29' else True,
            'replacement': {'security': 'OTHER-FUND', 'substantially_identical': None},
            'data_environment': 'SYNTHETIC'}


@when('its candidate observation is reconciled and accepted')
def reconcile_candidate(accounting):
    try:
        accounting['result'] = accounting['ledger'].reconcile(accounting['candidate'])
        accounting['accepted'] = accounting['ledger'].apply(accounting['candidate'])
    except DomainError as exc:
        accounting['error'] = exc


@then(parsers.parse('{code} blocks acceptance without changing facts'))
def typed_block(accounting, code):
    assert code in issue_codes(accounting.get('result', {})), f'Missing typed blocking issue {code}'
    assert accounting['ledger'].state() == accounting['before']
    issue = next(i for i in accounting['result']['issues'] if i['code'] == code)
    assert issue['blocks_execution_review'] is True


@when('another October 9 observation arrives on October 11')
def older_observation(accounting):
    reconcile_candidate(accounting)


@then('the purchase survives and the observation is evidence only')
def old_evidence(accounting):
    state = accounting['ledger'].state()
    assert Decimal(state['positions'][0]['quantity']) == 11
    assert len(state['activities']) == 1
    assert accounting.get('result', {}).get('status') == 'REVIEW_REQUIRED'
    assert 'OBSERVATION_PRECEDES_CONFIRMED_ACTIVITY' in issue_codes(accounting['result'])


@when('a partial page omitting the second holding is accepted')
def partial(accounting):
    snap = accounting['candidate']
    snap['positions'] = snap['positions'][:1]
    snap['positions_complete'] = False
    snap['source_hash'] = 'partial-page'
    accounting['result'] = accounting['ledger'].apply(snap)


@then('both holdings survive and cash remains typed unknown')
def unknown_cash(accounting):
    state = accounting['ledger'].state()
    assert {p['security'] for p in state['positions']} == {'FICTION', 'SECOND'}
    assert state['cash_balances'] == []
    result = accounting['ledger'].summary()
    assert result['cash'] is None, 'Unknown cash must never serialize as zero'
    assert 'UNKNOWN_CASH_COVERAGE' in issue_codes(result)


@when('a second statement reports four remaining shares and adjusted basis 360')
def adjusted_statement(accounting):
    snap = snapshot(date='2026-10-10', quantity='4', basis='360')
    snap['lots'][0].update(quantity='10', cost_basis='1000', remaining_adjusted_basis='360')
    try:
        accounting['result'] = accounting['ledger'].apply(snap)
    except DomainError as exc:
        accounting['error'] = exc


@then('the same broker lot has four shares and remaining adjusted basis 360')
def stable_lot(accounting):
    assert 'error' not in accounting, 'Source-backed adjusted remaining basis must be accepted'
    lot = accounting['ledger'].state()['lots'][0]
    assert lot['id'].endswith('broker-lot')
    assert Decimal(lot['remaining_quantity']) == 4
    assert Decimal(lot['remaining_adjusted_basis']) == 360
    assert Decimal(accounting['ledger'].state()['positions'][0]['cost_basis']) == 360


@when('identical and conflicting retries use its activity ID')
def retries(accounting):
    accounting['result'] = accounting['ledger'].record_activity(activity(amount='10'), yes=True)
    try:
        accounting['ledger'].record_activity(activity(amount='11'), yes=True)
    except DomainError as exc:
        accounting['error'] = exc


@then('the identical retry is a typed no-op and conflicting retry changes no facts')
def retry_result(accounting):
    assert accounting['result']['status'] == 'UNCHANGED'
    assert accounting['result']['committed'] is False
    assert accounting['ledger'].state() == accounting['before']
    assert isinstance(accounting.get('error'), DomainError)
    assert 'ACTIVITY_ID_CONFLICT' in issue_codes(
        getattr(accounting['error'], 'result', {})), 'Conflicts require a machine-readable issue'


@when('household summary is requested')
def summary(accounting):
    accounting['result'] = accounting['ledger'].summary()


@then('its valuation is incomplete with null value and MISSING_VALUATION_MARK')
def unmarked(accounting):
    result = accounting['result']
    assert result.get('status') == 'PARTIAL'
    p = next(p for p in accounting['ledger'].state()['positions'] if p['security'] == 'UNMARKED')
    assert p['market_value'] is None
    assert 'MISSING_VALUATION_MARK' in issue_codes(result)


@when('those three events are confirmed')
def events(accounting):
    accounting['results'] = []
    for event in [activity('DIVIDEND_REINVESTMENT', 'reinvest', security='FICTION',
                          quantity='0.5', amount='50', price='100', fee='0'),
                  activity('STOCK_SPLIT', 'split', security='FICTION', split_ratio='2'),
                  activity('RETURN_OF_CAPITAL', 'roc', security='FICTION', amount='21')]:
        try:
            accounting['results'].append(accounting['ledger'].record_activity(event, yes=True))
        except DomainError as exc:
            accounting['event_error'] = exc
            break


@then('quantity basis and cash preserve event meanings without external deposits')
def event_meanings(accounting):
    assert 'event_error' not in accounting, str(accounting.get('event_error'))
    state = accounting['ledger'].state()
    assert Decimal(state['positions'][0]['quantity']) == 21
    assert Decimal(state['positions'][0]['cost_basis']) == 929
    assert Decimal(state['cash_balances'][0]['amount']) == 1021
    assert all(a['type'] != 'CASH_DEPOSIT' for a in state['activities'])


@when('the fictional HTML is parsed')
def parse(accounting):
    html = '''<table><tr><th>Symbol</th><th>Quantity</th><th>Price</th><th>Market Value</th></tr>
    <tr><td>FICTION</td><td>10</td><td>100</td><td>1000</td></tr></table>
    <table><caption>Account summary totals</caption><tr><th>Symbol</th><th>Quantity</th>
    <th>Market Value</th></tr><tr><td>TOTAL</td><td>10</td><td>1000</td></tr></table>'''
    accounting['result'] = parse_html(html, 'fictional', as_of='2026-10-10')


@then('only the actual holding is proposed and ambiguous summary is typed review required')
def summary_table(accounting):
    result = accounting['result']
    assert [p['security'] for p in result['positions']] == ['FICTION']
    assert 'AMBIGUOUS_SUMMARY_ROW' in issue_codes(result)


@when('actual performance is requested for the fixed observation interval')
def performance(accounting):
    if accounting['case'] == 'B22':
        try:
            module = importlib.import_module('invest.performance')
        except ModuleNotFoundError:
            pytest.fail('Required public actual-performance calculation capability is absent')
        accounting['result'] = module.calculate(accounting['performance_input'])
        return
    accounting['result'] = invoke(accounting, ['portfolio', 'performance',
        '--from', accounting['start'], '--to', accounting['end']])


@then('actual time weighted return is exactly 0.21')
def twr(accounting):
    assert Decimal(accounting['result']['twr']['return']) == Decimal('0.21')
    assert accounting['result']['mode'] == 'ACTUAL'
    assert accounting['ledger'].state() == accounting['before']


@then('XIRR satisfies the 365.25-day equation and is labeled money weighted')
def xirr(accounting):
    result = accounting['result']['xirr']
    assert result['method'] == 'MONEY_WEIGHTED_ACTUAL_DAYS_365_25'
    rate = float(result['annualized_return'])
    assert math.isclose(1000 * (1 + rate) ** (365 / 365.25), 1100, abs_tol=0.000001)


@then('household external contributions are zero')
def internal_transfer(accounting):
    assert Decimal(accounting['result']['net_external_contributions']) == 0
    assert accounting['result']['coverage']['paired_transfers_complete'] is True


@then('household external contributions are zero and return includes the dividend once')
def reinvestment_return(accounting):
    assert Decimal(accounting['result']['net_external_contributions']) == 0
    assert Decimal(accounting['result']['twr']['return']) == Decimal('0.05')


@then('TWR is unavailable with the precise missing boundary date')
def missing_boundary(accounting):
    result = accounting['result']
    assert result['twr']['status'] == 'UNAVAILABLE'
    assert result['twr']['return'] is None
    assert 'MISSING_FLOW_BOUNDARY_VALUATION' in issue_codes(result)
    assert '2026-04-10' in result['coverage']['missing_boundary_dates']


@when('the current-weight historical risk report is requested')
def risk_report(accounting):
    from pathlib import Path

    from invest.analytics import risk
    from invest.market import MarketClient
    accounting['result'] = risk(accounting['ledger'].state(), MarketClient(
        accounting['ledger'], fixture_path=Path('tests/fixtures/fmp-synthetic.json')))


@then('the report explicitly identifies hypothetical current allocation and excludes realized CAGR')
def hypothetical(accounting):
    assert accounting['result'].get('mode') == 'HYPOTHETICAL_CURRENT_ALLOCATION'
    assert 'realized_cagr' not in accounting['result']
    assert accounting['result']['assumptions']['cash_return'] == '0'


@when('a proposed additional 400 tax cost is assessed')
@when('yearly tax budget is requested')
def budget(accounting):
    from invest import tax
    calculate = getattr(tax, 'annual_budget', None)
    assert callable(calculate), 'Annual positive-tax-dollar budget calculation is absent'
    state = accounting['ledger'].state()
    state['saved_proposals'] = accounting['ledger'].rows('trade_proposals')
    accounting['result'] = calculate(state, accounting['budget_input'],
        proposed_positive_tax_cost=accounting['budget_input']['proposed_positive_tax_cost'])


@then('remaining headroom is 300 and the sale is blocked by annual tax budget')
def budget_block(accounting):
    assert Decimal(accounting['result']['remaining_allowance']) == 300
    assert Decimal(accounting['result']['year_to_date_consumption']) == 200
    assert 'ANNUAL_TAX_BUDGET_EXCEEDED' in issue_codes(accounting['result'])


@then('the remaining headroom is 500 and proposed consumption is zero')
def proposals_free(accounting):
    assert Decimal(accounting['result']['remaining_allowance']) == 500
    assert Decimal(accounting['result']['year_to_date_consumption']) == 0


@when('household harvest review is requested')
def harvest(accounting):
    from invest import tax
    calculate = getattr(tax, 'harvest_plan', None)
    assert callable(calculate), 'Household harvest review capability with explicit policy is absent'
    accounting['result'] = calculate(accounting['ledger'].state(),
        accounting['harvest_input'], as_of='2026-10-10')


@then('the IRA conflict is cited and no guaranteed tax savings are reported')
def ira_conflict(accounting):
    result = accounting['result']
    assert 'HOUSEHOLD_IRA_ACQUISITION_CONFLICT' in issue_codes(result)
    assert any(c['activity_id'] == 'ira-acquisition' for c in result['wash_review']['conflicts'])
    assert result['guaranteed_tax_savings'] is None


@then('legal review remains required and no replacement is certified wash-sale safe')
def legal_unknown(accounting):
    result = accounting['result']
    assert result['status'] == 'REVIEW_REQUIRED'
    assert {'UNKNOWN_OUTSIDE_ACCOUNT_HISTORY', 'SUBSTANTIAL_IDENTITY_REVIEW'} <= issue_codes(result)
    assert all(c.get('legal_wash_sale_safe') is not True for c in result['replacement_candidates'])


@when('one share is sold from that explicit broker lot')
def specific_sale(accounting):
    lot = accounting['ledger'].state()['lots'][0]
    accounting['ledger'].record_activity(activity('SELL', 'specific-sale',
        security='FICTION', quantity='1', price='100', fee='0',
        lot_allocations=[{'lot_id': lot['id'], 'quantity': '1'}]), yes=True)


@then('remaining quantity is three and remaining adjusted basis is 270')
def conserved_basis(accounting):
    state = accounting['ledger'].state()
    lot = state['lots'][0]
    assert Decimal(lot['remaining_quantity']) == 3
    assert Decimal(lot['remaining_adjusted_basis']) == 270
    assert Decimal(state['positions'][0]['cost_basis']) == 270


@given(parsers.parse('extended accounting case {case} has {description}'))
def extended_case(accounting, case, description):
    """Each independent fixture supplies every fact to its tested public boundary."""
    ctx = accounting
    ctx['case'], ctx['description'] = case, description
    snap = snapshot(date='2026-07-01')
    if case in {'AT06', 'AT07'}:
        snap = snapshot(date='2026-07-01', basis='1200')
    snap['positions'][0].update(displayed_price_precision=2, displayed_market_value_precision=2)
    ctx['ledger'].apply(snap)
    ctx['candidate'] = snapshot(date='2026-10-10')
    ctx['candidate']['positions'][0].update(
        displayed_price_precision=2, displayed_market_value_precision=2)
    if case == 'AC01':
        ctx['candidate']['positions'][0].update(quantity='1000', price='1.23',
            market_value='1234', cost_basis=None)
        ctx['candidate']['lots'] = []
        ctx['candidate']['lots_complete'] = False
    elif case == 'AC02':
        ctx['candidate']['positions'][0].pop('displayed_price_precision')
    elif case == 'AC03':
        ctx['candidate']['source_timestamp'] = 'yesterday afternoon'
    elif case == 'AC04':
        ctx['candidate']['invented_acceptance_bypass'] = True
    elif case == 'AC05':
        ctx['candidate']['provenance'] = {
            'positions': {'source_timestamp': '2026-10-10', 'coverage': 'COMPLETE'},
            'lots': {'source_timestamp': '2026-07-01', 'coverage': 'PARTIAL'},
            'cash': {'source_timestamp': None, 'coverage': 'UNKNOWN'}}
    elif case in {'AC06', 'AC07', 'AC08'}:
        ctx['html'] = '''<div>PRIVATE-UNRELATED-FICTIONAL-MARKER</div><table>
        <tr><th>Symbol</th><th>Quantity</th><th>Price</th><th>Market Value</th>
        <th>Cost Basis</th><th>Acquisition Date</th></tr>
        <tr><td>FICTION</td><td>10</td><td>100.00</td><td>1000.00</td>
        <td>900.00</td><td>2024-01-01</td></tr></table>'''
    elif case == 'AC09':
        ctx['ledger'].record_activity(activity('BUY', 'verified-buy', security='FICTION',
            quantity='1', price='100', fee='0', date='2026-10-09'), yes=True)
        # Later source, complete coverage, but it contradicts the confirmed quantity eleven.
        ctx['candidate']['source_timestamp'] = '2026-10-10T12:00:00Z'
    elif case == 'AC10':
        with ctx['ledger'].connection:
            ctx['ledger'].connection.execute('DELETE FROM cash_balances')
    elif case == 'AC11':
        small = snapshot(date='2026-10-10', quantity='3', basis='0.01')
        ctx['ledger'].apply(small)
    elif case.startswith('AP'):
        ctx['performance_input'] = {
            'from_date': '2025-10-10', 'to_date': '2026-10-10', 'scope': 'HOUSEHOLD',
            'data_environment': 'SYNTHETIC', 'cash_flow_history_complete': True,
            'checkpoints': [{'date': '2025-10-10', 'value': '1000', 'complete': True},
                            {'date': '2026-10-10', 'value': '1100', 'complete': True}],
            'cash_flows': [], 'fee_method': 'NET_OF_FEES'}
        if case == 'AP01':
            ctx['performance_input']['checkpoints'][-1]['complete'] = False
        elif case == 'AP02':
            ctx['performance_input']['cash_flow_history_complete'] = False
        elif case == 'AP03':
            # -100,+230,-132 over exact year-spaced flows has roots 10% and 20%.
            ctx['performance_input'].update(from_date='2024-10-10', to_date='2026-10-10',
                checkpoints=[{'date': '2024-10-10', 'value': '100', 'complete': True},
                             {'date': '2026-10-10', 'value': '0', 'complete': True}],
                investor_cash_flows=[{'date': '2024-10-10', 'amount': '-100'},
                                     {'date': '2025-10-10', 'amount': '230'},
                                     {'date': '2026-10-10', 'amount': '-132'}])
        elif case == 'AP04':
            ctx['performance_input'].update(
                checkpoints=[{'date': '2025-10-10', 'value': '0', 'complete': True},
                             {'date': '2026-10-10', 'value': '0', 'complete': True}],
                investor_cash_flows=[{'date': '2025-10-10', 'amount': '-100'},
                                     {'date': '2026-10-10', 'amount': '-100'}])
        elif case == 'AP06':
            ctx['performance_input']['checkpoints'][-1]['value'] = '0'
    elif case.startswith('AT'):
        setup_extended_tax(ctx)
    ctx['before'] = ctx['ledger'].state()


def setup_extended_tax(ctx):
    case = ctx['case']
    ctx['budget_input'] = {'year': 2026, 'annual_allowance': '500',
        'short_term_rate': '0.40', 'long_term_rate': '0.20', 'currency': 'USD',
        'taxable_history_complete': True, 'data_environment': 'SYNTHETIC',
        'source': 'Fictional complete all-taxable-account history attestation',
        'as_of': '2026-10-10T12:00:00Z'}
    if case == 'AT03':
        snap = snapshot(date='2026-07-02')
        original_lot = dict(snap['lots'][0])
        snap['lots'] = [
            {**original_lot, 'acquisition_date': '2024-01-01',
             'quantity': '5', 'remaining_quantity': '5', 'cost_basis': '450',
             'remaining_adjusted_basis': '450'},
            {**original_lot, 'id': 'short-term-lot', 'source_lot_id': 'short-term-lot',
             'identity_source': 'Reviewed fictional original broker record: taxable/short-term-lot',
             'acquisition_date': '2026-06-01',
             'quantity': '5', 'remaining_quantity': '5', 'cost_basis': '450',
             'remaining_adjusted_basis': '450'}]
        ctx['ledger'].apply(snap)
    if case in {'AT01', 'AT02', 'AT03', 'AT04', 'AT05'}:
        ctx['ledger'].record_activity(activity('SELL', 'august-sale', security='FICTION',
            quantity='1', price='190', fee='0', date='2026-08-10',
            lot_allocations=[{'lot_id': 'taxable-broker-lot', 'quantity': '1'}]), yes=True)
    if case in {'AT01', 'AT02', 'AT03'}:
        ctx['ledger'].record_activity(activity('SELL', 'september-sale', security='FICTION',
            quantity='2' if case == 'AT02' else '1', price='0' if case == 'AT02' else '190',
            fee='0', date='2026-09-10', lot_allocations=[{
                'lot_id': 'short-term-lot' if case == 'AT03' else 'taxable-broker-lot',
                'quantity': '2' if case == 'AT02' else '1'}]), yes=True)
    if case == 'AT04':
        ctx['budget_input']['long_term_rate'] = None
    elif case == 'AT05':
        ctx['budget_input']['currency'] = 'EUR'
    elif case in {'AT06', 'AT07'}:
        acquired = '2026-09-10' if case == 'AT06' else '2026-09-09'
        ctx['ledger'].apply(snapshot('ira', acquired))
        ctx['ledger'].record_activity(activity('BUY', 'boundary-acquisition', account_id='ira',
            date=acquired, security='FICTION', quantity='1', price='100', fee='0'), yes=True)
        ctx['harvest_input'] = {'loss_sale_date': '2026-10-10', 'security': 'FICTION',
            'spouse_history_complete': True, 'outside_account_history_complete': True,
            'replacement': {'security': 'OTHER-FUND', 'substantially_identical': None},
            'data_environment': 'SYNTHETIC'}


@when('its new accounting boundary is exercised')
def extended_boundary(accounting):
    ctx, case = accounting, accounting['case']
    if case in {'AC03', 'AC04', 'AC05'}:
        from pydantic import ValidationError

        from invest.models import Snapshot
        try:
            ctx['validated'] = Snapshot.model_validate(ctx['candidate'])
        except ValidationError as exc:
            ctx['validation_errors'] = exc.errors()
    elif case in {'AC01', 'AC02', 'AC09'}:
        try:
            ctx['result'] = ctx['ledger'].reconcile(ctx['candidate'])
            ctx['accepted'] = ctx['ledger'].apply(ctx['candidate'])
        except DomainError as exc:
            ctx['error'] = exc
    elif case in {'AC06', 'AC07', 'AC08'}:
        ctx['result'] = parse_html(ctx['html'], 'fictional',
            institution='vanguard' if case == 'AC06' else 'generic', as_of='2026-10-10')
        if case == 'AC07':
            ctx['ledger'].apply(ctx['result'])
    elif case == 'AC10':
        ctx['result'] = invoke(ctx, ['portfolio', 'check', '--as-of', '2026-10-10'])
    elif case == 'AC11':
        ctx['ledger'].record_activity(activity('SELL', 'final-sale', security='FICTION',
            quantity='3', price='100', fee='0', lot_allocations=[{
                'lot_id': 'taxable-broker-lot', 'quantity': '3'}]), yes=True)
    elif case.startswith('AP'):
        try:
            module = importlib.import_module('invest.performance')
        except ModuleNotFoundError:
            pytest.fail('Required public actual-performance calculation capability is absent')
        ctx['result'] = module.calculate(ctx['performance_input'])
    elif case in {'AT06', 'AT07'}:
        harvest(ctx)
    else:
        from invest import tax
        calculate = getattr(tax, 'annual_budget', None)
        assert callable(calculate), 'Annual positive-tax-dollar budget calculation is absent'
        ctx['result'] = calculate(ctx['ledger'].state(), ctx['budget_input'],
            proposed_positive_tax_cost='20' if case == 'AT04' else '0')


@then('its rounding discrepancy and tolerance are explicitly reported without rewriting evidence')
def rounding(accounting):
    result = accounting['result']
    assert 'error' not in accounting
    assert result.get('value_checks'), 'Reconciliation omits source-precision value diagnostics'
    row = result['value_checks'][0]
    assert Decimal(row['observed_discrepancy']) == 4
    assert Decimal(row['rounding_tolerance']) == Decimal('5.005')
    assert row['within_tolerance'] is True
    assert Decimal(accounting['ledger'].state()['positions'][0]['market_value']) == 1234


@then('UNKNOWN_PRICE_PRECISION blocks observation acceptance')
@then('CONFIRMED_EVENT_DISCREPANCY prevents replacing balances')
def extended_block(accounting):
    code = 'UNKNOWN_PRICE_PRECISION' if accounting['case'] == 'AC02' else 'CONFIRMED_EVENT_DISCREPANCY'
    assert code in issue_codes(accounting['result'])
    assert accounting['ledger'].state() == accounting['before']


@then('the source timestamp is rejected by the strict observation model')
@then('the unknown field is rejected by the strict observation model')
def strict_model(accounting):
    field = 'source_timestamp' if accounting['case'] == 'AC03' else 'invented_acceptance_bypass'
    assert any(field in e['loc'] for e in accounting.get('validation_errors', []))
    assert accounting['ledger'].state() == accounting['before']


@then('positions lots and cash retain distinct source dates and coverage')
def provenance(accounting):
    assert 'validated' in accounting
    actual = accounting['validated'].model_dump(mode='json')
    assert actual.get('provenance') == accounting['candidate']['provenance']


@then('the adapter is provisional and human review is required')
def provisional(accounting):
    assert accounting['result'].get('institution_status') == 'PROVISIONAL'
    assert accounting['result']['status'] == 'REVIEW_REQUIRED'
    assert 'UNVALIDATED_INSTITUTION_ADAPTER' in issue_codes(accounting['result'])


@then('financial cells have provenance and the private page text is absent from SQLite')
def cell_provenance(accounting):
    position = accounting['result']['positions'][0]
    assert position.get('cell_provenance', {}).get('quantity')
    assert 'PRIVATE-UNRELATED-FICTIONAL-MARKER' not in '\n'.join(accounting['ledger'].connection.iterdump())


@then('the unmatched lot is unresolved and cannot support a specific lot sale')
def unresolved_lot(accounting):
    lot = accounting['result']['lots'][0]
    assert lot.get('identity_status') == 'UNRESOLVED'
    assert lot.get('saleable') is False
    assert 'UNVERIFIED_LOT_IDENTITY' in issue_codes(accounting['result'])


@then('preflight returns UNKNOWN_CASH_COVERAGE and a next human action without mutation')
def preflight(accounting):
    assert 'UNKNOWN_CASH_COVERAGE' in issue_codes(accounting['result'])
    assert accounting['result']['next_human_actions']
    assert accounting['ledger'].state() == accounting['before']


@then('final lot quantity and adjusted basis are exactly zero')
def final_basis(accounting):
    lot = accounting['ledger'].state()['lots'][0]
    assert Decimal(lot['remaining_quantity']) == 0
    assert Decimal(lot['remaining_adjusted_basis']) == 0


@then(parsers.parse('actual returns are unavailable with {code}'))
def performance_unavailable(accounting, code):
    result = accounting['result']
    assert code in issue_codes(result)
    assert result['twr']['return'] is None
    assert result['cagr']['annualized_return'] is None
    assert accounting['ledger'].state() == accounting['before']


@then(parsers.parse('XIRR is null and {code} is reported'))
def xirr_unavailable(accounting, code):
    assert code in issue_codes(accounting['result'])
    assert accounting['result']['xirr']['status'] == 'UNAVAILABLE'
    assert accounting['result']['xirr']['annualized_return'] is None


@then('actual CAGR follows the declared 365.25-day annualization equation')
def actual_cagr(accounting):
    result = accounting['result']
    assert result['mode'] == 'ACTUAL'
    assert Decimal(result['twr']['return']) == Decimal('0.1')
    assert math.isclose(float(result['cagr']['annualized_return']),
                        1.1 ** (365.25 / 365) - 1, abs_tol=0.000000001)
    assert result['cagr']['calendar_days'] == 365


@then('actual TWR and CAGR are both exactly minus one')
def total_loss(accounting):
    assert Decimal(accounting['result']['twr']['return']) == -1
    assert Decimal(accounting['result']['cagr']['annualized_return']) == -1


@then('annual consumption sums both sales and the remaining allowance is 460')
def accumulated_budget(accounting):
    assert Decimal(accounting['result']['year_to_date_consumption']) == 40
    assert Decimal(accounting['result']['remaining_allowance']) == 460


@then('positive tax consumption remains 20 and signed net gain remains negative')
def losses_no_credit(accounting):
    assert Decimal(accounting['result']['year_to_date_consumption']) == 20
    assert Decimal(accounting['result']['remaining_allowance']) == 480
    assert Decimal(accounting['result']['realized_signed_net_gain']) == -80


@then('annual positive tax consumption is 60 with separate term rates')
def separate_rates(accounting):
    assert Decimal(accounting['result']['year_to_date_consumption']) == 60
    assert Decimal(accounting['result']['short_term_positive_tax_cost']) == 40
    assert Decimal(accounting['result']['long_term_positive_tax_cost']) == 20


@then('UNKNOWN_TAX_RATE blocks the gain sale but does not block a cash only proposal')
def unknown_rate(accounting):
    issue = next(i for i in accounting['result']['issues'] if i['code'] == 'UNKNOWN_TAX_RATE')
    assert issue['blocks_proposal'] is True
    assert accounting['result']['gain_realizing_sale_allowed'] is False
    assert accounting['result']['cash_only_proposal_allowed'] is True


@then('UNSUPPORTED_TAX_CURRENCY blocks tax budget calculation')
def budget_currency(accounting):
    assert 'UNSUPPORTED_TAX_CURRENCY' in issue_codes(accounting['result'])
    assert accounting['result']['status'] == 'BLOCKED'
    assert accounting['result']['remaining_allowance'] is None


@then('the boundary acquisition is included as a household conflict')
def window_included(accounting):
    assert any(c['activity_id'] == 'boundary-acquisition'
               for c in accounting['result']['wash_review']['conflicts'])
    assert accounting['result']['guaranteed_tax_savings'] is None


@then('the old acquisition is excluded without certifying legal safety')
def window_excluded(accounting):
    assert not any(c['activity_id'] == 'boundary-acquisition'
                   for c in accounting['result']['wash_review']['conflicts'])
    assert accounting['result']['legal_wash_sale_safe'] is not True
