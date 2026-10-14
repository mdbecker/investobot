import json
from pathlib import Path

import pytest
from planning_fixtures import saved_proposal
from pytest_bdd import given, parsers, scenarios, then, when
from typer.testing import CliRunner

from invest.cli import app
from invest.contracts import tools_describe
from invest.ledger import Ledger
from invest.market import MarketClient
from invest.models import DomainError
from invest.plan_storage import load_plan, summaries
from invest.plans import show
from invest.targets import save

scenarios('features/stabilization.feature')


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.setenv('INVEST_DB', str(tmp_path / 'ledger.db'))
    monkeypatch.setenv('INVEST_CONFIG', str(tmp_path / 'missing.toml'))
    return {'ledger': Ledger(tmp_path / 'ledger.db'), 'tmp': tmp_path}


def snapshot(account='a', source='2026-10-08'):
    return {'account': {'id': account, 'name': 'Verified Roth', 'institution': 'synthetic',
                       'account_type': 'Roth IRA', 'tax_status': 'TAX_FREE',
                       'history_complete': True, 'currency': 'USD', 'active': True},
            'positions': [{'security': 'VTI', 'asset_type': 'OTHER', 'quantity': '10',
                           'market_value': '1000', 'price': '100', 'cost_basis': '800',
                           'cusip': 'SYNTH-C1', 'isin': 'SYNTH-I1', 'as_of': '2026-10-08', 'displayed_price_precision': 0, 'displayed_market_value_precision': 0}],
            'lots': [{'id': f'{account}-lot', 'security': 'VTI', 'quantity': '10',
                      'remaining_quantity': '10', 'cost_basis': '800',
                      'acquisition_date': '2024-01-01'}],
            'cash': '100', 'source_hash': f'{account}-{source}', 'source_timestamp': source,
            'data_environment': 'SYNTHETIC',
            'positions_complete': True, 'lots_complete': True}


@given('an unknown security in two dated accounts with saved plans')
def populated(ctx):
    ledger = ctx['ledger']
    ctx['snap'] = snapshot()
    ledger.apply(ctx['snap'])
    ledger.apply(snapshot('b'))
    ctx['sid'] = ledger.resolve('VTI')['id']
    target = save(ledger, {'name': 'Synthetic', 'target_allocations': {ctx['sid']: '1'},
                          'planning_constraints': {'eligible_accounts': ['a', 'b'],
                          'permitted_securities': {'a': [ctx['sid']], 'b': [ctx['sid']]}}})
    client = MarketClient(ledger, fixture_path=Path('tests/fixtures/fmp-synthetic.json'))
    ctx['plan'] = saved_proposal(ledger, client, target['id'], as_of='2026-10-08')
    ctx['before'] = ledger.state()


def classify(ctx, asset='ETF', source='Verified synthetic issuer', confirm=True):
    return ctx['ledger'].classify_security(ctx['sid'], asset, source, confirm=confirm)


def update(ctx, payload=None, yes=True, account='a'):
    return ctx['ledger'].update_account(account, payload or {
        'tax_status': 'TAX_DEFERRED', 'reason': 'Verified correction', 'source': 'Synthetic statement'}, yes=yes)


def catch(ctx, call):
    ctx['before'] = ctx['ledger'].state()
    try:
        call()
    except (DomainError, ValueError) as exc:
        ctx['error'] = exc


@when('an ETF classification is confirmed')
def correct(ctx):
    ctx['result'] = classify(ctx)


@then('canonical and current classifications agree without changing inventory')
def retained(ctx):
    state = ctx['ledger'].state()
    assert ctx['ledger'].resolve(ctx['sid'])['asset_type'] == 'ETF'
    assert all(p['asset_type'] == 'ETF' for p in state['positions'])
    assert [{k: v for k, v in p.items() if k != 'asset_type'} for p in state['positions']] == [
        {k: v for k, v in p.items() if k != 'asset_type'} for p in ctx['before']['positions']]
    assert state['lots'] == ctx['before']['lots']
    assert state['snapshots'] == ctx['before']['snapshots']


@then('classification provenance is audited and plans become stale')
def classification_audit(ctx):
    history = ctx['ledger'].resolve(ctx['sid'])['classification_history']
    assert len(history) == 1
    assert history[0]['previous_type'] == 'OTHER'
    assert history[0]['new_type'] == 'ETF'
    assert history[0]['source'] == 'Verified synthetic issuer'
    assert history[0]['changed_at']
    stale(ctx)


@when('classification is previewed then confirmed twice')
def repeats(ctx):
    ctx['preview'] = classify(ctx, confirm=False)
    ctx['preview_state'] = ctx['ledger'].state()
    classify(ctx)
    ctx['confirmed'] = ctx['ledger'].state()
    ctx['repeat'] = classify(ctx)


@then('preview is read only and the repeat is unchanged')
def repeat_check(ctx):
    assert ctx['preview']['status'] == 'PREVIEW'
    assert ctx['preview_state'] == ctx['before']
    assert ctx['repeat']['status'] == 'UNCHANGED'
    assert ctx['ledger'].state() == ctx['confirmed']


@when(parsers.re(r'classification is requested with "(?P<asset>[^"]*)" and "(?P<source>[^"]*)"'))
def invalid_class(ctx, asset, source):
    catch(ctx, lambda: classify(ctx, asset, source))


@when('a verified ETF is classified as STOCK')
def known(ctx):
    classify(ctx)
    catch(ctx, lambda: classify(ctx, 'STOCK'))


@then('the correction is rejected atomically')
def rejected(ctx):
    assert 'error' in ctx
    assert ctx['ledger'].state() == ctx['before']


@when('a verified ETF receives an incomplete classification snapshot')
def incomplete(ctx):
    classify(ctx)
    ctx['snap']['positions'][0]['market_value'] = '1100'
    ctx['snap']['positions'][0]['price'] = '110'
    ctx['ledger'].apply(ctx['snap'])


@then('every current position remains an ETF')
def etfs(ctx):
    assert ctx['ledger'].resolve(ctx['sid'])['asset_type'] == 'ETF'
    assert all(p['asset_type'] == 'ETF' for p in ctx['ledger'].rows('positions'))


@when('a verified ETF receives a STOCK snapshot')
def contradictory(ctx):
    classify(ctx)
    ctx['snap']['positions'][0]['asset_type'] = 'STOCK'
    catch(ctx, lambda: ctx['ledger'].apply(ctx['snap']))


@when('a snapshot changes every account metadata field and valuation')
def metadata(ctx):
    ctx['snap']['account'].update(name='Default', institution='generic', account_type='brokerage',
        tax_status='TAXABLE', history_complete=False, currency='EUR', active=False)
    ctx['snap']['positions'][0]['market_value'] = '1100'
    ctx['snap']['positions'][0]['price'] = '110'
    ctx['diff'] = ctx['ledger'].reconcile(ctx['snap'])
    ctx['ledger'].apply(ctx['snap'])


@then('reconciliation explains metadata discrepancies and preserves configuration')
def metadata_preserved(ctx):
    assert ctx['ledger'].rows('accounts') == ctx['before']['accounts']
    assert ctx['ledger'].resolve(ctx['sid'])['currency'] == 'USD'
    assert ctx['ledger'].rows('positions')[0]['market_value'] == '1100'
    assert {d['field'] for d in ctx['diff']['account_metadata_discrepancies']} == {
        'name', 'institution', 'account_type', 'tax_status', 'history_complete', 'currency', 'active'}
    assert any('account update' in w for w in ctx['diff']['warnings'])


@when('account tax treatment is previewed then confirmed twice')
def account_repeat(ctx):
    ctx['preview'] = update(ctx, yes=False)
    ctx['preview_state'] = ctx['ledger'].state()
    update(ctx)
    ctx['confirmed'] = ctx['ledger'].state()
    ctx['repeat'] = update(ctx)


@then('account preview is read only and confirmation is audited once')
def account_audit(ctx):
    assert ctx['preview']['status'] == 'PREVIEW'
    assert ctx['preview_state'] == ctx['before']
    assert ctx['repeat']['status'] == 'UNCHANGED'
    assert ctx['ledger'].state() == ctx['confirmed']
    account = next(a for a in ctx['ledger'].rows('accounts') if a['id'] == 'a')
    assert account['tax_status'] == 'TAX_DEFERRED'
    assert len(account['metadata_history']) == 1
    assert account['metadata_history'][0]['reason'] == 'Verified correction'
    assert account['metadata_history'][0]['source'] == 'Synthetic statement'
    assert account['metadata_history'][0]['changed_at']


@then('saved plans are stale')
def stale(ctx):
    assert show(ctx['ledger'], ctx['plan']['id'])['status'] == 'STALE'
    assert [load_plan(ctx['ledger'], row['id']) for row in summaries(ctx['ledger'])][0] == ctx['plan']


@when(parsers.parse('an invalid account update "{case}" is confirmed'))
def bad_account(ctx, case):
    payload = {'tax_status': 'TAX_DEFERRED', 'reason': 'Correction', 'source': 'Statement'}
    cases = {'identity': {'id': 'changed'}, 'unsupported': {'cash': '0'},
             'currency': {'currency': 'EUR'}, 'missing reason': {'reason': ' '},
             'missing source': {'source': ''}, 'invalid boolean': {'history_complete': 'true'},
             'invalid tax': {'tax_status': 'made up'}}
    payload.update(cases.get(case, {}))
    catch(ctx, lambda: update(ctx, payload, account='missing' if case == 'unknown' else 'a'))


@given('an empty account with no cash observation')
def empty(ctx):
    snap = snapshot()
    snap.update(positions=[], lots=[], cash_known=False)
    ctx['ledger'].apply(snap)


@when('its currency is explicitly changed')
def currency(ctx):
    update(ctx, {'currency': 'EUR', 'source': 'Statement', 'reason': 'Correction'})


@then('its new currency is audited')
def euro(ctx):
    assert ctx['ledger'].rows('accounts')[0]['currency'] == 'EUR'
    assert len(ctx['ledger'].rows('accounts')[0]['metadata_history']) == 1


def undated(ctx):
    ctx['snap'].update(source_timestamp=None, lots=[], lots_complete=False)
    ctx['snap']['positions'][0].update(quantity='11', market_value='1100', cost_basis=None)


@when('an undated changed snapshot is reconciled and ordinarily applied')
def unknown(ctx):
    undated(ctx)
    ctx['diff'] = ctx['ledger'].reconcile(ctx['snap'])
    catch(ctx, lambda: ctx['ledger'].apply(ctx['snap']))


@then('unknown freshness requires override and leaves state unchanged')
def guard(ctx):
    assert ctx['diff']['source_date_status'] == 'UNKNOWN_SOURCE_DATE'
    assert ctx['diff']['latest_known_source_date'] == '2026-10-08'
    assert ctx['diff']['override_required'] is True
    rejected(ctx)


@when('an undated changed snapshot is applied with justification')
def reviewed(ctx):
    undated(ctx)
    ctx['ledger'].apply(ctx['snap'], allow_older=True, justification='Reviewed synthetic source')


@then('the unknown date override is audited and plans are stale')
def override_audit(ctx):
    snap = next(s for s in ctx['ledger'].rows('snapshots') if s['source_timestamp'] is None)
    assert snap['override_kind'] == 'UNKNOWN_SOURCE_DATE_OVERRIDE'
    assert snap['override_justification'] == 'Reviewed synthetic source'
    assert next(p for p in ctx['ledger'].rows('positions') if p['account_id'] == 'a')['source_timestamp'] is None
    stale(ctx)


@given(parsers.parse('a "{prior}" accepted source date'))
def prior(ctx, prior):
    ctx['snap'] = snapshot(source=None if prior in {'none', 'unknown'} else prior)
    if prior != 'none':
        ctx['ledger'].apply(ctx['snap'])


@when(parsers.parse('a snapshot with "{incoming}" source date is reconciled'))
def reconcile_date(ctx, incoming):
    ctx['snap']['source_timestamp'] = None if incoming == 'unknown' else incoming
    ctx['snap']['positions'][0]['market_value'] = '1100'
    ctx['snap']['positions'][0]['price'] = '110'
    ctx['diff'] = ctx['ledger'].reconcile(ctx['snap'])


@then(parsers.parse('its date status is "{status}" and override is "{required}"'))
def date_status(ctx, status, required):
    assert ctx['diff']['source_date_status'] == status
    assert ctx['diff']['override_required'] is (required == 'true')
    if required == 'false':
        ctx['ledger'].apply(ctx['snap'])


@when('the same snapshot is applied again')
def reapply(ctx):
    ctx['result'] = ctx['ledger'].apply(ctx['snap'])


@then('no snapshot transition is duplicated')
def no_duplicate(ctx):
    assert ctx['result']['status'] == 'UNCHANGED'
    assert ctx['ledger'].state() == ctx['before']


@when('an undated changed snapshot is applied without justification')
def no_reason(ctx):
    undated(ctx)
    catch(ctx, lambda: ctx['ledger'].apply(ctx['snap'], allow_older=True, justification=' '))


@when('an older snapshot is applied with justification')
def older(ctx):
    ctx['snap']['source_timestamp'] = '2026-10-07'
    ctx['ledger'].apply(ctx['snap'], allow_older=True, justification='Older reviewed source')


@then('an older source override is audited')
def older_audit(ctx):
    snap = next(s for s in ctx['ledger'].rows('snapshots') if s['source_timestamp'] == '2026-10-07')
    assert snap['override_kind'] == 'OLDER_SOURCE_OVERRIDE'


@when('corrections are previewed and confirmed through the CLI')
def cli(ctx):
    runner = CliRunner()
    args = ['security', 'classify', ctx['sid'], '--asset-type', 'ETF', '--source', 'Issuer']
    ctx['cli_preview'] = runner.invoke(app, args)
    ctx['cli_confirm'] = runner.invoke(app, args + ['--confirm'])
    payload = {'tax_status': 'TAX_DEFERRED', 'reason': 'Correction', 'source': 'Statement'}
    ctx['cli_account'] = runner.invoke(app, ['account', 'update', 'a', '--file', '-', '--yes'], input=json.dumps(payload))


@then('CLI corrections and discovery contracts are consistent')
def cli_check(ctx):
    for key in ['cli_preview', 'cli_confirm', 'cli_account']:
        assert ctx[key].exit_code == 0, ctx[key].output
    assert json.loads(ctx['cli_preview'].stdout)['status'] == 'PREVIEW'
    assert tools_describe('security.classify')['mutation_scope'] == 'security_metadata'
    assert tools_describe('account.update')['mutation_scope'] == 'account_metadata'
    assert 'reason' in tools_describe('account.update')['json_input_schema']['properties']


@given('legacy account and security records without audit fields')
def legacy(ctx):
    populated(ctx)
    with ctx['ledger'].connection:
        for table, field in [('accounts', 'metadata_history'), ('securities', 'classification_history')]:
            for row in ctx['ledger'].rows(table):
                row.pop(field, None)
                ctx['ledger'].put(table, row['id'], row)


@when('the ledger is reopened')
def reopen(ctx):
    ctx['ledger'].connection.close()
    ctx['ledger'] = Ledger(ctx['tmp'] / 'ledger.db')


@then('legacy records expose safe empty audit histories')
def defaults(ctx):
    assert all(a['metadata_history'] == [] for a in ctx['ledger'].rows('accounts'))
    assert all(s['classification_history'] == [] for s in ctx['ledger'].rows('securities'))


@when('a nonexistent security is classified')
def missing_security(ctx):
    catch(ctx, lambda: ctx['ledger'].classify_security('missing', 'ETF', 'Issuer', confirm=True))


@when('registration attempts to replace OTHER with ETF')
def register_bypass(ctx):
    catch(ctx, lambda: ctx['ledger'].register_security({'ticker': 'VTI', 'name': 'Synthetic',
        'asset_type': 'ETF', 'currency': 'USD', 'source': 'Issuer'}))


@when('a verified ETF receives conflicting strong identities')
def identity_conflict(ctx):
    classify(ctx)
    ctx['snap']['positions'][0]['cusip'] = 'CONFLICTING-CUSIP'
    catch(ctx, lambda: ctx['ledger'].apply(ctx['snap']))


@when('an otherwise unchanged snapshot loses its source date')
def lost_source_date(ctx):
    ctx['snap']['source_timestamp'] = None
    ctx['diff'] = ctx['ledger'].reconcile(ctx['snap'])
    catch(ctx, lambda: ctx['ledger'].apply(ctx['snap']))
