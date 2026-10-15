import copy
import hashlib
import json
from decimal import Decimal
from pathlib import Path

import pytest
from planning_fixtures import saved_proposal
from pydantic import ValidationError
from pytest_bdd import given, scenarios, then, when
from typer.testing import CliRunner

from invest.cli import app
from invest.ledger import Ledger
from invest.market import MarketClient
from invest.models import DomainError
from invest.plan_storage import load_plan, summaries
from invest.plans import compare, persisted
from invest.reports import export
from invest.targets import save
from invest.web import create_server

scenarios('features/final_hardening.feature')


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.setenv('INVEST_DB', str(tmp_path / 'db'))
    monkeypatch.setenv('INVEST_CONFIG', str(tmp_path / 'config.toml'))
    ledger = Ledger(tmp_path / 'db')
    return {'ledger': ledger, 'client': MarketClient(ledger, fixture_path=Path('tests/fixtures/fmp-synthetic.json')),
            'tmp': tmp_path, 'monkeypatch': monkeypatch}


@given('a fully known dated synthetic taxable account')
def taxable(ctx):
    ctx['snap'] = {'data_environment': 'SYNTHETIC', 'account': {'id': 'tax', 'name': 'Synthetic', 'tax_status': 'TAXABLE', 'history_complete': True},
        'positions': [{'security': 'AAA', 'cusip': 'SYNTH-C1', 'asset_type': 'STOCK', 'quantity': '10',
                       'price': '100', 'market_value': '1000', 'cost_basis': '800', 'as_of': '2026-10-08', 'displayed_price_precision': 0, 'displayed_market_value_precision': 0},
                      {'security': 'BBB', 'asset_type': 'STOCK', 'quantity': '0', 'price': '100',
                       'market_value': '0', 'as_of': '2026-10-08', 'displayed_price_precision': 0, 'displayed_market_value_precision': 0}],
        'lots': [{'id': 'known-lot', 'security': 'AAA', 'quantity': '10', 'remaining_quantity': '10',
                  'cost_basis': '800', 'acquisition_date': '2024-01-01'}],
        'cash_known': True, 'cash': '500', 'source_hash': 'synthetic-final', 'source_timestamp': '2026-10-08',
        'positions_complete': True, 'lots_complete': True}
    ctx['ledger'].apply(ctx['snap'])
    ctx['aaa'], ctx['bbb'] = [ctx['ledger'].resolve(s)['id'] for s in ['AAA', 'BBB']]
    ctx['payload'] = {'name': 'Full replacement', 'target_allocations': {ctx['bbb']: '1'},
        'planning_constraints': {'eligible_accounts': ['tax']}}
    ctx['before'] = ctx['ledger'].state()


def apply(ctx):
    try:
        ctx['ledger'].apply(ctx['snap'])
    except (DomainError, ValidationError) as exc:
        ctx['error'] = exc


@when('a partial valuation refresh has no basis or lot table')
def refresh(ctx):
    ctx['snap'].update(lots=[], lots_complete=False, positions_complete=False)
    ctx['snap']['positions'][0].update(price='110', market_value='1100', cost_basis=None)
    apply(ctx)


@then('known basis and lot history remain available')
def basis(ctx):
    p = next(p for p in ctx['ledger'].state()['positions'] if p['security']=='AAA')
    assert Decimal(p['cost_basis']) == 800
    assert ctx['ledger'].state()['lots'] == ctx['before']['lots']


@when('a complete snapshot contradicts its own lot basis')
def contradiction(ctx):
    ctx['snap']['positions'][0]['cost_basis'] = '999'
    apply(ctx)


@when('normalized completeness is supplied as a string')
def bool_input(ctx):
    ctx['snap']['positions_complete'] = 'true'
    apply(ctx)


@when('the same account supplies conflicting strong identity for a ticker')
def identity(ctx):
    ctx['snap'].update(lots=[], lots_complete=False)
    ctx['snap']['positions'][0]['cusip'] = 'SYNTH-CONFLICT'
    apply(ctx)


@then('input is rejected atomically')
def rejected(ctx):
    assert 'error' in ctx
    assert ctx['ledger'].state() == ctx['before']


@when('an invalid numeric activity is previewed through the CLI')
def bad_number(ctx):
    ctx['result'] = CliRunner().invoke(app, ['portfolio', 'record-activity', '-'], input=json.dumps({
        'activity_id': 'bad', 'account_id': 'tax', 'type': 'BUY', 'security': 'AAA',
        'quantity': 'NOT_A_NUMBER', 'price': '100', 'date': '2026-10-08'}))


@when('a malformed activity is previewed through the CLI')
def malformed(ctx):
    ctx['result'] = CliRunner().invoke(app, ['portfolio', 'record-activity', '-'], input=json.dumps({
        'activity_id': 'bad', 'account_id': 'tax', 'type': None, 'date': '2026-10-08'}))


@then('the CLI returns input error JSON on stderr')
def input_error(ctx):
    assert ctx['result'].exit_code == 1
    assert json.loads(ctx['result'].stderr)['error']
    assert ctx['result'].stdout == ''
    assert ctx['ledger'].state() == ctx['before']


@when('a confirmed sale fee exceeds its gross proceeds')
def excess_fee(ctx):
    try:
        ctx['ledger'].record_activity({'activity_id': 'bad-fee', 'account_id': 'tax',
            'security': 'AAA', 'type': 'SELL', 'quantity': '1', 'price': '100', 'fee': '200',
            'date': '2026-10-08', 'lot_allocations': [{'lot_id': 'known-lot', 'quantity': '1'}]}, yes=True)
    except DomainError as exc:
        ctx['error'] = exc


@when('planning receives a list instead of price observations')
def price_shape(ctx):
    target = save(ctx['ledger'], ctx['payload'])
    try:
        saved_proposal(ctx['ledger'], ctx['client'], target['id'], as_of='2026-10-08', prices=[])
    except DomainError as exc:
        ctx['error'] = exc


@then('invalid price input is rejected without persisting a plan')
def invalid_prices(ctx):
    assert ctx['error'].code == 1
    assert [load_plan(ctx['ledger'], row['id']) for row in summaries(ctx['ledger'])] == []


@when('a plan uses fresh prices against old source quantities')
def old_quantities(ctx):
    ctx['snap']['source_timestamp'] = '2026-10-01'
    ctx['ledger'].apply(ctx['snap'], allow_older=True, justification='Synthetic history audit')
    t = save(ctx['ledger'], ctx['payload'])
    prices = {sid: {'price': '100', 'as_of': '2026-10-08', 'currency': 'USD', 'source': 'fresh synthetic quote'}
              for sid in [ctx['aaa'], ctx['bbb']]}
    ctx['plan'] = saved_proposal(ctx['ledger'], ctx['client'], t['id'], as_of='2026-10-08', prices=prices)


@then('the plan requires review of source freshness')
def quantity_freshness(ctx):
    assert ctx['plan']['status'] == 'BLOCKED'
    assert any('freshness' in w.lower() or 'stale' in w.lower() for w in ctx['plan']['warnings'])


@given('a dated retirement account without tax lots')
def retirement(ctx):
    taxable(ctx)
    ctx['ledger'].update_account('tax', {'tax_status': 'TAX_FREE',
        'reason': 'Synthetic retirement account fixture', 'source': 'Synthetic statement'}, yes=True)
    ctx['snap']['account']['tax_status'] = 'TAX_FREE'
    ctx['snap']['lots'] = []
    ctx['snap']['lots_complete'] = True
    ctx['snap']['positions'][0]['cost_basis'] = None
    ctx['ledger'].apply(ctx['snap'])
    ctx['before'] = ctx['ledger'].state()


@when('an otherwise eligible replacement target is planned')
def replacement(ctx):
    t = save(ctx['ledger'], ctx['payload'])
    ctx['plan'] = saved_proposal(ctx['ledger'], ctx['client'], t['id'], as_of='2026-10-08')


@then('the plan is ready for human review with zero taxable gain')
def ready(ctx):
    assert ctx['plan']['status'] == 'REVIEW_REQUIRED'
    assert 'UNRESOLVED_LOTS' in {issue['code'] for issue in ctx['plan']['issues']}
    assert Decimal(ctx['plan']['tax_analysis']['realized_gain_loss']) == 0
    assert ctx['ledger'].state() == ctx['before']


@when('the native inspection server is created with default host')
def native(ctx):
    ctx['server'] = create_server(ctx['tmp'] / 'server.db', port=0)


@then('its listener uses loopback')
def loopback(ctx):
    try:
        assert ctx['server'].server_address[0] == '127.0.0.1'
    finally:
        ctx['server'].server_close()



@when('an agent creates three targets and plans and exports their reports')
def acceptance(ctx):
    plans=[]
    for name, weights in [('Conservative', ('.3','.4','.3')), ('Balanced',('.5','.4','.1')), ('Growth',('.8','.15','.05'))]:
        payload = copy.deepcopy(ctx['payload'])
        payload.update(name=name, target_allocations={ctx['aaa']:weights[0],ctx['bbb']:weights[1],'CASH':weights[2]})
        target = save(ctx['ledger'], payload)
        plan = saved_proposal(ctx['ledger'], ctx['client'], target['id'], as_of='2026-10-08')
        plans.append(plan)
        export(plan, ctx['tmp'] / (name+'.md'))
    ctx['plans'] = plans
    ctx['comparison'] = compare(ctx['ledger'], *(p['id'] for p in plans))
    original = export(plans[0], ctx['tmp'] / 'before.md')['content_hash']
    ctx['ledger'].record_activity({'activity_id':'later-interest','account_id':'tax','type':'INTEREST',
                                  'amount':'1','date':'2026-10-08'}, yes=True)
    ctx['reproduced'] = export(persisted(ctx['ledger'], plans[0]['id']), ctx['tmp'] / 'after.md')['content_hash']
    ctx['original_hash'] = original


@then('their comparison uses the same source state and old reports remain reproducible')
def alternatives(ctx):
    assert ctx['comparison']['same_source_snapshot'] is True
    assert ctx['comparison']['same_price_assumptions'] is True
    assert len(ctx['comparison']['plans']) == 3
    assert ctx['original_hash'] == ctx['reproduced']
    assert hashlib.sha256((ctx['tmp'] / 'after.md').read_bytes()).hexdigest() == ctx['original_hash']


@when('an unclassified account page is normalized')
def unclassified(ctx):
    from invest.parsers.generic import parse_html

    ctx['normalized'] = parse_html('<table><tr><th>Symbol</th><th>Quantity</th><th>Market Value</th></tr>'
                                  '<tr><td>AAA</td><td>1</td><td>100</td></tr></table>', 'unknown')


@then('its tax treatment is OTHER rather than assumed taxable')
def unknown_classification(ctx):
    assert ctx['normalized']['account']['tax_status'] == 'OTHER'


@when('a partial normalized snapshot supplies no cash information')
def no_cash(ctx):
    ctx['snap']['positions_complete'] = False
    ctx['snap']['lots_complete'] = False
    ctx['snap']['source_timestamp'] = '2026-10-09'
    del ctx['snap']['cash']
    ctx['snap'].pop('cash_known', None)
    ctx['ledger'].apply(ctx['snap'])


@then('the previously known cash balance remains')
def keep_cash(ctx):
    assert Decimal(ctx['ledger'].summary()['cash']) == 500
