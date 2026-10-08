import json
import threading
from decimal import Decimal
from http.client import HTTPConnection
from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from invest.ledger import Ledger
from invest.web import create_server

scenarios('features/planning_web.feature')


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.setenv('INVEST_DB', str(tmp_path / 'db'))
    monkeypatch.setenv('INVEST_CONFIG', str(tmp_path / 'config.toml'))
    monkeypatch.setenv('INVEST_PROMPTS', str(tmp_path / 'prompts'))
    monkeypatch.setenv('INVEST_FIXTURES', str(Path('tests/fixtures/fmp-synthetic.json').resolve()))
    ledger = Ledger(tmp_path / 'db')
    server = create_server(tmp_path / 'db', host='127.0.0.1', port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield {'ledger': ledger, 'server': server, 'tmp': tmp_path}
    server.shutdown()
    server.server_close()
    thread.join()
    ledger.connection.close()


def request(ctx, path, payload=None, origin=True):
    conn = HTTPConnection('127.0.0.1', ctx['server'].server_port)
    headers = {}
    if payload is not None:
        headers['Content-Type'] = 'application/json'
        headers['Origin'] = f"http://127.0.0.1:{ctx['server'].server_port}" if origin else 'https://external.example'
    conn.request('GET' if payload is None else 'POST', path,
                 body=None if payload is None else json.dumps(payload), headers=headers)
    response = conn.getresponse()
    body = response.read().decode()
    content_type = response.getheader('Content-Type')
    value = json.loads(body) if content_type.startswith('application/json') else body
    conn.close()
    return response.status, value


@given('a local server with a dated synthetic retirement portfolio')
def setup(ctx):
    ctx['ledger'].apply({'account': {'id': 'ira', 'name': 'IRA', 'tax_status': 'TAX_FREE',
                                   'history_complete': True},
        'positions': [{'security': 'AAA', 'asset_type': 'STOCK', 'quantity': '10', 'price': '100',
                       'market_value': '1000', 'as_of': '2026-10-08'},
                      {'security': 'BBB', 'asset_type': 'STOCK', 'quantity': '0', 'price': '100',
                       'market_value': '0', 'as_of': '2026-10-08'}],
        'cash': '0', 'source_timestamp': '2026-10-08', 'source_hash': 'synthetic-web'})
    aaa, bbb = [ctx['ledger'].resolve(t)['id'] for t in ['AAA', 'BBB']]
    ctx['target_input'] = {'name': 'Web target', 'target_allocations': {aaa: '0', bbb: '1', 'CASH': '0'},
        'planning_constraints': {'eligible_accounts': ['ira'], 'permitted_securities': {'ira': [aaa, bbb]}}}
    ctx['before'] = ctx['ledger'].state()


@when('a target is saved and activated through the local API')
def target(ctx):
    status, ctx['target'] = request(ctx, '/api/targets/save', {'target': ctx['target_input']})
    assert status == 200
    assert request(ctx, '/api/targets/activate', {'target_id': ctx['target']['id'], 'confirm': True})[0] == 200


@then('overview values and target differences match the CLI domain')
def overview(ctx):
    from invest.targets import diff

    status, value = request(ctx, '/api/overview')
    assert status == 200
    assert Decimal(value['summary']['total_value']) == 1000
    assert value['target_diff'] == diff(ctx['ledger'], ctx['target']['id'])
    assert value['active_target']['id'] == ctx['target']['id']
    assert value['data_freshness'][0]['source_timestamp'] == '2026-10-08'
    assert ctx['ledger'].state() == ctx['before']
    assert ctx['ledger'].rows('market_data_cache') == []


@when('a plan is generated through the local API')
def generate(ctx):
    target(ctx)
    status, ctx['plan'] = request(ctx, '/api/plans/generate', {'target_id': ctx['target']['id'],
                                                           'as_of': '2026-10-08'})
    assert status == 200


@then('saved trades and tax values match the CLI domain')
def plan(ctx):
    from invest.plans import show

    status, value = request(ctx, '/api/plans/'+ctx['plan']['id'])
    assert status == 200
    assert value == show(ctx['ledger'], ctx['plan']['id'])
    assert [a['type'] for a in value['proposed_actions']] == ['SELL', 'BUY']
    assert Decimal(value['tax_analysis']['realized_gain_loss']) == 0


@then('a report can be downloaded without changing actual state')
def report(ctx):
    status, value = request(ctx, '/api/plans/'+ctx['plan']['id']+'/report?format=json')
    assert status == 200
    assert value == ctx['ledger'].rows('plans')[0]
    assert ctx['ledger'].state() == ctx['before']


@when('confirmed activity changes the portfolio')
def activity(ctx):
    ctx['ledger'].record_activity({'activity_id': 'interest', 'account_id': 'ira', 'type': 'INTEREST',
        'amount': '1', 'date': '2026-10-08'}, yes=True)


@then('the API visibly identifies the plan as stale')
def stale(ctx):
    assert request(ctx, '/api/plans/'+ctx['plan']['id'])[1]['status'] == 'STALE'


@when('a user reads creates and edits a prompt through the API')
def prompts(ctx):
    status, listing = request(ctx, '/api/prompts')
    assert status == 200
    ctx['bundled_id'] = listing['prompts'][0]['id']
    ctx['bundled'] = request(ctx, '/api/prompts/'+ctx['bundled_id'])[1]
    for content in ['First full prompt', 'Second full prompt']:
        assert request(ctx, '/api/prompts/save', {'id': 'my-research', 'content': content})[0] == 200


@then('the full prompt text is returned and bundled defaults remain recoverable')
def full_text(ctx):
    assert request(ctx, '/api/prompts/my-research')[1]['content'] == 'Second full prompt'
    assert request(ctx, '/api/prompts/'+ctx['bundled_id'])[1] == ctx['bundled']
    assert request(ctx, '/api/prompts/delete', {'id': 'my-research'})[0] == 200
    assert request(ctx, '/api/prompts/my-research')[0] == 400


@when('invalid prompt paths and execution requests are posted')
def invalid(ctx):
    ctx['results'] = [request(ctx, '/api/prompts/save', {'id': '../outside', 'content': 'bad'}),
                      request(ctx, '/api/agent/execute', {'command': 'trade'}),
                      request(ctx, '/api/trades/execute', {'security': 'AAA'})]


@then('no prompt or actual state changes occur')
def no_execution(ctx):
    assert all(s in {400, 404} for s, _ in ctx['results'])
    assert ctx['ledger'].state() == ctx['before']
    assert not (ctx['tmp'] / 'outside.md').exists()


@when('a target save comes from another origin')
def cross_origin(ctx):
    ctx['status'] = request(ctx, '/api/targets/save', {'target': ctx['target_input']}, origin=False)[0]


@then('the write is rejected')
def protected(ctx):
    assert ctx['status'] == 403
    assert ctx['ledger'].rows('targets') == []
