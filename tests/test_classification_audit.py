import copy
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from invest.ledger import Ledger
from invest.market import MarketClient
from invest.models import DomainError
from invest.plans import generate, persisted, show
from invest.targets import save

scenarios('features/classification_audit.feature')


@pytest.fixture
def ctx(tmp_path):
    ledger = Ledger(tmp_path / 'ledger.db')
    yield {'ledger': ledger}
    ledger.connection.close()


def snapshot(account='a', asset='OTHER', quantity='10', basis='800', date='2026-10-08'):
    return {'data_environment': 'SYNTHETIC', 'account': {'id': account, 'name': 'Synthetic IRA', 'tax_status': 'TAX_FREE',
                        'currency': 'USD', 'history_complete': True},
        'positions': [{'security': 'VTI', 'asset_type': asset, 'quantity': quantity,
                       'price': '100', 'market_value': str(int(quantity) * 100),
                       'cost_basis': basis, 'as_of': date, 'cusip': 'SYN-C',
                       'isin': 'SYN-I', 'figi': 'SYN-F', 'displayed_price_precision': 0, 'displayed_market_value_precision': 0}],
        'lots': [{'id': account + '-lot', 'security': 'VTI', 'quantity': quantity,
                  'remaining_quantity': quantity, 'cost_basis': basis,
                  'acquisition_date': '2024-01-01'}],
        'cash': '100', 'source_hash': f'{account}-{date}-{asset}-{quantity}',
        'source_timestamp': date, 'positions_complete': True, 'lots_complete': True}


@given('an unknown security is held in two synthetic accounts')
def held(ctx):
    ledger = ctx['ledger']
    ledger.apply(snapshot())
    ledger.apply(snapshot('b'))
    ctx['sid'] = ledger.resolve('VTI')['id']
    ctx['before'] = copy.deepcopy(ledger.state())


@given('a household without securities')
def empty(ctx):
    pass


@given('its ETF classification is explicitly confirmed')
def confirmed(ctx):
    ctx['ledger'].classify_security(ctx['sid'], 'ETF', 'Verified synthetic issuer', confirm=True)
    ctx['before'] = copy.deepcopy(ctx['ledger'].state())


@when('a changed snapshot suggests ETF for that security')
def suggested(ctx):
    ctx['incoming'] = snapshot(asset='ETF', quantity='12', basis='960', date='2026-10-09')
    ctx['incoming']['cash'] = '125'
    ctx['diff'] = ctx['ledger'].reconcile(ctx['incoming'])


@then('reconciliation identifies the canonical security and explicit correction workflow')
def review(ctx):
    assert ctx['diff']['classification_reviews'] == [{
        'security_id': ctx['sid'], 'ticker': 'VTI', 'canonical_type': 'OTHER',
        'observed_type': 'ETF', 'action_required': 'EXPLICIT_CLASSIFICATION'}]
    assert any('security classify' in w and ctx['sid'] in w for w in ctx['diff']['warnings'])


@then('reconciliation leaves accepted state unchanged')
def read_only(ctx):
    assert ctx['ledger'].state() == ctx['before']


@when('those holdings are accepted')
def accepted(ctx):
    ctx['ledger'].apply(ctx['incoming'])


@then('quantities cash basis and lots update while both classifications stay OTHER')
def updated(ctx):
    state = ctx['ledger'].state()
    assert ctx['ledger'].resolve(ctx['sid'])['asset_type'] == 'OTHER'
    assert all(p['asset_type'] == 'OTHER' for p in state['positions'])
    position = next(p for p in state['positions'] if p['account_id'] == 'a')
    assert position['quantity'] == '12'
    assert position['market_value'] == '1200'
    assert position['cost_basis'] == '960'
    assert next(l for l in state['lots'] if l['account_id'] == 'a')['cost_basis'] == '960'
    assert next(c for c in state['cash_balances'] if c['account_id'] == 'a')['amount'] == '125'
    assert next(p for p in state['positions'] if p['account_id'] == 'b')['quantity'] == '10'
    assert state['accounts'] == ctx['before']['accounts']


@then('no classification correction is audited')
def unaudited(ctx):
    assert ctx['ledger'].resolve(ctx['sid'])['classification_history'] == []


@when('a changed snapshot omits the classification')
def unknown_source(ctx):
    ctx['incoming'] = snapshot(quantity='12', basis='960', date='2026-10-09')
    ctx['incoming']['positions'][0].pop('asset_type')


@then('canonical and current classifications remain ETF')
def preserved(ctx):
    assert ctx['ledger'].resolve(ctx['sid'])['asset_type'] == 'ETF'
    assert all(p['asset_type'] == 'ETF' for p in ctx['ledger'].rows('positions'))
    assert len(ctx['ledger'].resolve(ctx['sid'])['classification_history']) == 1


def contradictory(ctx, identity=None):
    incoming = snapshot(asset='STOCK' if identity is None else 'OTHER',
                        quantity='12', basis='960', date='2026-10-09')
    incoming['cash'] = '999'
    incoming['account']['name'] = 'Untrusted replacement account name'
    if identity:
        incoming['positions'][0][identity] = 'CONFLICTING-IDENTITY'
    incoming['positions'].insert(0, {'security': 'NEW', 'asset_type': 'STOCK',
        'quantity': '1', 'price': '50', 'market_value': '50', 'cost_basis': '40',
        'as_of': '2026-10-09', 'displayed_price_precision': 0, 'displayed_market_value_precision': 0})
    incoming['lots'].append({'id': 'new-lot', 'security': 'NEW', 'quantity': '1',
        'remaining_quantity': '1', 'cost_basis': '40', 'acquisition_date': '2024-01-01'})
    try:
        ctx['ledger'].apply(incoming)
    except DomainError as exc:
        ctx['error'] = exc


@when('a multiple-security snapshot contradicts the confirmed type')
def known_conflict(ctx):
    contradictory(ctx)


@when(parsers.parse('a multiple-security snapshot conflicts in {identity}'))
def identity_conflict(ctx, identity):
    contradictory(ctx, identity)


@then('no positions cash account metadata securities or snapshots change')
def atomic(ctx):
    assert ctx['error'].code == 3
    assert ctx['ledger'].state() == ctx['before']
    assert all(s['ticker'] != 'NEW' for s in ctx['ledger'].rows('securities'))


@when('a new ETF snapshot is reconciled and accepted')
def new(ctx):
    incoming = snapshot(asset='ETF')
    ctx['diff'] = ctx['ledger'].reconcile(incoming)
    ctx['ledger'].apply(incoming)


@then('its initial classification is ETF without review or correction history')
def initial(ctx):
    assert ctx['diff']['classification_reviews'] == []
    security = ctx['ledger'].resolve('VTI')
    assert security['asset_type'] == 'ETF'
    assert security['classification_history'] == []


@given('a plan and historical snapshots are saved')
def planned(ctx):
    ledger = ctx['ledger']
    target = save(ledger, {'name': 'Synthetic', 'target_allocations': {ctx['sid']: '1'},
        'planning_constraints': {'eligible_accounts': ['a', 'b'],
                                'permitted_securities': {'a': [ctx['sid']], 'b': [ctx['sid']]}}})
    client = MarketClient(ledger, fixture_path=Path('tests/fixtures/fmp-synthetic.json'))
    ctx['plan'] = generate(ledger, client, target['id'], as_of='2026-10-08')
    ctx['before'] = copy.deepcopy(ledger.state())


@when('ETF classification is previewed and confirmed twice with provenance')
def correction(ctx):
    ledger = ctx['ledger']
    ctx['preview'] = ledger.classify_security(ctx['sid'], 'ETF', 'Verified synthetic issuer')
    ctx['preview_state'] = ledger.state()
    ctx['confirmation'] = ledger.classify_security(ctx['sid'], 'ETF',
                                                 'Verified synthetic issuer', confirm=True)
    ctx['confirmed_state'] = ledger.state()
    ctx['repeat'] = ledger.classify_security(ctx['sid'], 'ETF', 'Verified synthetic issuer',
                                           confirm=True)


@then('preview changes nothing and confirmation updates both accounts once')
def once(ctx):
    assert ctx['preview']['status'] == 'PREVIEW'
    assert ctx['preview_state'] == ctx['before']
    assert ctx['repeat']['status'] == 'UNCHANGED'
    assert ctx['ledger'].state() == ctx['confirmed_state']
    assert ctx['ledger'].resolve(ctx['sid'])['asset_type'] == 'ETF'
    assert all(p['asset_type'] == 'ETF' for p in ctx['ledger'].rows('positions'))


@then('exact financial amounts lots and historical snapshots are preserved')
def finances(ctx):
    state = ctx['ledger'].state()
    for table in ('accounts', 'cash_balances', 'lots', 'snapshots'):
        assert state[table] == ctx['before'][table]
    assert [{k: v for k, v in p.items() if k != 'asset_type'} for p in state['positions']] == [
        {k: v for k, v in p.items() if k != 'asset_type'} for p in ctx['before']['positions']]


@then('the classification history records verified provenance and the saved plan is stale')
def audit(ctx):
    history = ctx['ledger'].resolve(ctx['sid'])['classification_history']
    assert len(history) == 1
    assert history[0]['previous_type'] == 'OTHER'
    assert history[0]['new_type'] == 'ETF'
    assert history[0]['source'] == 'Verified synthetic issuer'
    assert history[0]['changed_at']
    assert show(ctx['ledger'], ctx['plan']['id'])['status'] == 'STALE'
    assert persisted(ctx['ledger'], ctx['plan']['id']) == ctx['plan']


@when('classification is confirmed without a source')
def no_source(ctx):
    try:
        ctx['ledger'].classify_security(ctx['sid'], 'ETF', '', confirm=True)
    except (DomainError, ValueError) as exc:
        ctx['error'] = exc


@then('classification fails without changing accepted state')
def source_required(ctx):
    assert 'error' in ctx
    assert ctx['ledger'].state() == ctx['before']
