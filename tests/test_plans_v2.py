import copy
import json
from decimal import Decimal
from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when
from typer.testing import CliRunner

from invest.cli import app
from invest.ledger import Ledger
from invest.market import MarketClient
from invest.models import DomainError
from invest.targets import save

scenarios('features/plans_v2.feature')


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.setenv('INVEST_DB', str(tmp_path / 'db'))
    monkeypatch.setenv('INVEST_CONFIG', str(tmp_path / 'config.toml'))
    monkeypatch.setenv('INVEST_FIXTURES', '/app/tests/fixtures/fmp-synthetic.json')
    ledger = Ledger(tmp_path / 'db')
    return {'ledger': ledger, 'client': MarketClient(ledger, fixture_path=Path('tests/fixtures/fmp-synthetic.json')),
            'tmp': tmp_path}


def setup(ctx, status, account='ira', quantity='10'):
    ctx['ledger'].apply({'account': {'id': account, 'name': account, 'tax_status': status,
                                    'history_complete': True},
        'positions': [{'security': 'AAA', 'asset_type': 'STOCK', 'quantity': quantity,
                       'price': '100', 'market_value': str(Decimal(quantity)*100),
                       'cost_basis': str(Decimal(quantity)*50), 'as_of': '2026-10-08'},
                      {'security': 'BBB', 'asset_type': 'STOCK', 'quantity': '0', 'price': '100',
                       'market_value': '0', 'as_of': '2026-10-08'}],
        'lots': [{'id': account+'-old', 'security': 'AAA', 'quantity': quantity,
                  'remaining_quantity': quantity, 'cost_basis': str(Decimal(quantity)*50),
                  'acquisition_date': '2024-01-01'}],
        'cash': '0', 'source_hash': 'synthetic-'+account, 'source_timestamp': '2026-10-08',
        'positions_complete': True, 'lots_complete': True})
    ctx['aaa'] = ctx['ledger'].resolve('AAA')['id']
    ctx['bbb'] = ctx['ledger'].resolve('BBB')['id']
    ctx['payload'] = {'name': 'Replacement', 'description': 'Synthetic',
        'target_allocations': {ctx['aaa']: '0', ctx['bbb']: '1', 'CASH': '0'},
        'planning_constraints': {'eligible_accounts': [account],
                                'permitted_securities': {account: [ctx['aaa'], ctx['bbb']]}}}
    ctx['before'] = copy.deepcopy(ctx['ledger'].state())


@given('an eligible synthetic retirement portfolio')
def retirement(ctx):
    setup(ctx, 'TAX_FREE')


@given('an eligible synthetic taxable portfolio')
def taxable(ctx):
    setup(ctx, 'TAXABLE', 'tax')


@given('eligible taxable and retirement accounts')
def multiple(ctx):
    setup(ctx, 'TAXABLE', 'tax', '5')
    setup(ctx, 'TAX_DEFERRED', 'ira', '5')
    ctx['payload']['planning_constraints'].update(eligible_accounts=['tax', 'ira'],
        permitted_securities={'tax': [ctx['aaa'], ctx['bbb']], 'ira': [ctx['aaa'], ctx['bbb']]})
    ctx['before'] = copy.deepcopy(ctx['ledger'].state())


@when('a full replacement plan is generated')
def generated(ctx):
    from invest.plans import generate

    ctx['target'] = save(ctx['ledger'], ctx['payload'])
    ctx['plan'] = generate(ctx['ledger'], ctx['client'], ctx['target']['id'], as_of='2026-10-08',
                           prices=ctx.get('prices'))


@then('it sells and buys in the IRA with zero taxable gain and no actual mutation')
def retirement_plan(ctx):
    p = ctx['plan']
    assert p['status'] == 'READY_FOR_HUMAN_REVIEW'
    assert [(a['type'], a['account_id']) for a in p['proposed_actions']] == [('SELL', 'ira'), ('BUY', 'ira')]
    assert Decimal(p['tax_analysis']['realized_gain_loss']) == 0
    assert Decimal(p['cash_after']['ira']) == 0
    assert ctx['ledger'].state() == ctx['before']
    assert ctx['ledger'].rows('market_data_cache') == []
    assert ctx['ledger'].rows('fund_holdings_cache') == []


@then('taxable sales identify exact lots and long term gains')
def lots(ctx):
    p = ctx['plan']
    sell = next(a for a in p['proposed_actions'] if a['type'] == 'SELL')
    assert sell['lot_allocations'] == [{'lot_id': 'tax-old', 'quantity': '10'}]
    assert Decimal(p['tax_analysis']['long_term_gain_loss']) == 500
    assert Decimal(p['tax_analysis']['short_term_gain_loss']) == 0
    assert ctx['ledger'].state() == ctx['before']


@given('the long term gain budget is two hundred')
def budget(ctx):
    ctx['payload']['planning_constraints']['long_term_gain_budget'] = '200'


@then('sales respect the budget and disclose remaining drift')
def limited(ctx):
    assert Decimal(ctx['plan']['tax_analysis']['long_term_gain_loss']) <= 200
    assert sum(Decimal(a['quantity']) for a in ctx['plan']['proposed_actions'] if a['type']=='SELL') <= 4
    assert any(Decimal(r['difference_value']) != 0 for r in ctx['plan']['remaining_target_drift'])
    assert ctx['plan']['status'] == 'REVIEW_REQUIRED'


@given('the replacement investment is not permitted')
def restricted(ctx):
    ctx['payload']['planning_constraints']['permitted_securities']['ira'] = [ctx['aaa']]


@then('the restricted replacement is not purchased and the plan needs review')
def not_permitted(ctx):
    assert not any(a['type']=='BUY' and a['security']==ctx['bbb'] for a in ctx['plan']['proposed_actions'])
    assert ctx['plan']['status'] == 'REVIEW_REQUIRED'
    assert any('permitted' in w.lower() for w in ctx['plan']['warnings'])


@given('the only holding is excluded from trading')
def excluded(ctx):
    ctx['payload']['planning_constraints']['excluded_positions'] = [
        next(p['id'] for p in ctx['ledger'].state()['positions'] if p['security']=='AAA')]


@then('no unfunded purchases are proposed')
def unfunded(ctx):
    assert ctx['plan']['proposed_actions'] == []
    assert Decimal(ctx['plan']['cash_after']['ira']) >= 0


@given('the lot basis is unresolved')
def missing(ctx):
    with ctx['ledger'].connection:
        p = next(p for p in ctx['ledger'].rows('positions') if p['security']=='AAA')
        p.update(lot_state='UNRESOLVED', cost_basis=None)
        ctx['ledger'].put('positions', p['id'], p)
    ctx['before'] = ctx['ledger'].state()


@then('no taxable sale is proposed and missing basis requires review')
def basis(ctx):
    assert not any(a['type']=='SELL' for a in ctx['plan']['proposed_actions'])
    assert ctx['plan']['status'] == 'REVIEW_REQUIRED'
    assert any('basis' in w.lower() or 'lot' in w.lower() for w in ctx['plan']['warnings'])


@given('account trading eligibility is unknown')
def unknown(ctx):
    ctx['payload']['planning_constraints']['eligible_accounts'] = []
    ctx['payload']['planning_constraints']['permitted_securities'] = {}


@then('no trades are proposed and eligibility requires review')
def eligibility(ctx):
    assert ctx['plan']['proposed_actions'] == []
    assert ctx['plan']['status'] == 'REVIEW_REQUIRED'
    assert any('eligib' in w.lower() for w in ctx['plan']['warnings'])


@given('the replacement price is stale')
def stale_price(ctx):
    ctx['prices'] = {ctx['bbb']: {'price': '100', 'as_of': '2026-10-01',
                                 'currency': 'USD', 'source': 'synthetic'}}


@then('no stale price purchase is proposed')
def no_stale(ctx):
    assert not any(a['type']=='BUY' and a['security']==ctx['bbb'] for a in ctx['plan']['proposed_actions'])
    assert ctx['plan']['status'] == 'REVIEW_REQUIRED'
    assert any('stale' in w.lower() for w in ctx['plan']['warnings'])


@given('the replacement security is an individual bond')
def bond(ctx):
    with ctx['ledger'].connection:
        s = ctx['ledger'].resolve('BBB')
        s['asset_type']='BOND'
        ctx['ledger'].put('securities', s['id'], s)
        p = next(p for p in ctx['ledger'].rows('positions') if p['security']=='BBB')
        p['asset_type']='BOND'
        ctx['ledger'].put('positions', p['id'], p)
    ctx['before'] = ctx['ledger'].state()


@then('no automatic bond purchase is proposed')
def no_bond(ctx):
    assert not any(a['security']==ctx['bbb'] for a in ctx['plan']['proposed_actions'])
    assert any('bond' in w.lower() for w in ctx['plan']['warnings'])


@given('a mutual fund permits hundredth unit trades with a cash target')
def fractional(ctx):
    with ctx['ledger'].connection:
        s = ctx['ledger'].resolve('BBB')
        s['asset_type']='MUTUAL_FUND'
        ctx['ledger'].put('securities', s['id'], s)
    ctx['payload']['target_allocations'] = {ctx['aaa']: '0', ctx['bbb']: '.955', 'CASH': '.045'}
    ctx['payload']['planning_constraints']['trade_increments'] = {'ira': {ctx['bbb']: '.01'}}
    ctx['before'] = ctx['ledger'].state()


@then('the mutual fund purchase uses the explicit fractional increment')
def fractions(ctx):
    buy = next(a for a in ctx['plan']['proposed_actions'] if a['type']=='BUY')
    assert Decimal(buy['quantity']) == Decimal('9.55')
    assert Decimal(ctx['plan']['cash_after']['ira']) == 45


@when('confirmed account activity changes the source state')
def source_change(ctx):
    ctx['persisted'] = copy.deepcopy(ctx['ledger'].rows('plans')[0])
    ctx['ledger'].record_activity({'activity_id': 'interest-1', 'account_id': 'ira',
        'type': 'INTEREST', 'amount': '1', 'date': '2026-10-08'}, yes=True)


@then('the saved plan is stale and its original inputs remain immutable')
def stale(ctx):
    from invest.plans import show

    assert show(ctx['ledger'], ctx['plan']['id'])['status'] == 'STALE'
    assert ctx['ledger'].rows('plans')[0] == ctx['persisted']


@when('two alternatives are planned against the same portfolio')
def alternatives(ctx):
    from invest.plans import compare, generate

    generated(ctx)
    ctx['payload']['target_allocations'] = {ctx['aaa']: '.5', ctx['bbb']: '.5', 'CASH': '0'}
    t = save(ctx['ledger'], ctx['payload'])
    p = generate(ctx['ledger'], ctx['client'], t['id'], as_of='2026-10-08')
    ctx['comparison'] = compare(ctx['ledger'], ctx['plan']['id'], p['id'])


@then('comparison reports turnover tax drift and a common baseline')
def compared(ctx):
    result = ctx['comparison']
    assert result['same_source_snapshot'] is True
    assert result['same_price_assumptions'] is True
    assert len(result['plans']) == 2
    assert all('turnover' in p and 'tax_analysis' in p and 'remaining_target_drift' in p
               and 'trade_count' in p for p in result['plans'])


@then('retirement sales precede taxable sales and cash remains in each account')
def coordinated(ctx):
    sells = [a for a in ctx['plan']['proposed_actions'] if a['type']=='SELL']
    assert [a['account_id'] for a in sells] == ['ira', 'tax']
    assert all(Decimal(v) >= 0 for v in ctx['plan']['cash_after'].values())
    assert Decimal(ctx['plan']['tax_analysis']['long_term_gain_loss']) == 250


@given('an account uses another currency')
def currency(ctx):
    ctx['ledger'].apply({'account': {'id': 'eur', 'name': 'EUR', 'currency': 'EUR'},
                         'positions': [], 'cash': '1', 'source_hash': 'eur'})


@when('a full replacement plan is requested')
def invalid_plan(ctx):
    from invest.plans import generate

    t = save(ctx['ledger'], ctx['payload'])
    try:
        generate(ctx['ledger'], ctx['client'], t['id'], as_of='2026-10-08')
    except DomainError as exc:
        ctx['error'] = exc


@then('planning rejects mixed currencies without saving a plan')
def rejected(ctx):
    assert ctx['error'].code == 3
    assert ctx['ledger'].rows('plans') == []


@when('the agent generates compares and exports plans through the CLI')
def cli(ctx):
    t = save(ctx['ledger'], ctx['payload'])
    runner = CliRunner()
    ctx['results'] = []
    ids = []
    for _ in range(2):
        r = runner.invoke(app, ['plan', 'generate', '--target', t['id'], '--as-of', '2026-10-08'])
        assert r.exit_code == 0, r.output
        ctx['results'].append(r)
        ids.append(json.loads(r.stdout)['plan']['id'])
    for args in [['plan', 'list'], ['plan', 'show', ids[0]], ['plan', 'compare', *ids]]:
        ctx['results'].append(runner.invoke(app, args))
    ctx['report_path'] = ctx['tmp'] / 'report.json'
    ctx['results'].append(runner.invoke(app, ['report', 'export', ids[0], '--format', 'json',
        '--output', str(ctx['report_path'])]))
    ctx['first_id'] = ids[0]


@then('all plan commands return JSON and the report matches the persisted plan')
def exported(ctx):
    for r in ctx['results']:
        assert r.exit_code == 0, r.output
        assert json.loads(r.stdout)
    assert json.loads(ctx['report_path'].read_text()) == next(
        p for p in ctx['ledger'].rows('plans') if p['id']==ctx['first_id'])
    assert ctx['ledger'].state() == ctx['before']
