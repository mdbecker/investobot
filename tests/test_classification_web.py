import copy
import json
import threading
from urllib.request import Request, urlopen

import pytest
from pytest_bdd import given, scenarios, then, when

from invest.ledger import Ledger
from invest.web import create_server

scenarios('features/classification_web.feature')


@pytest.fixture
def ctx(tmp_path):
    path = tmp_path / 'ledger.db'
    ledger = Ledger(path)
    server = create_server(path, host='127.0.0.1', port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield {'ledger': ledger, 'base': f'http://127.0.0.1:{server.server_port}'}
    server.shutdown()
    server.server_close()
    thread.join()
    ledger.connection.close()


def request(ctx, path, payload=None):
    headers = {'Content-Type': 'application/json', 'Origin': ctx['base']}
    body = json.dumps(payload).encode() if payload is not None else None
    with urlopen(Request(ctx['base'] + path, data=body, headers=headers)) as response:
        raw = response.read().decode()
        return json.loads(raw) if path.startswith('/api/') else raw


@given('an inspection ledger holds an OTHER classified security')
def portfolio(ctx):
    snapshot = {'account': {'id': 'ira', 'name': 'Synthetic IRA', 'tax_status': 'TAX_FREE'},
        'positions': [{'security': 'VTI', 'asset_type': 'OTHER', 'quantity': '10',
                       'market_value': '1000', 'price': '100', 'as_of': '2026-10-08', 'displayed_price_precision': 0, 'displayed_market_value_precision': 0}],
        'cash': '0', 'source_timestamp': '2026-10-08', 'source_hash': 'unknown-type'}
    ctx['ledger'].apply(snapshot)
    ctx['security_id'] = ctx['ledger'].resolve('VTI')['id']
    ctx['snapshot'] = copy.deepcopy(snapshot)
    ctx['snapshot']['positions'][0]['asset_type'] = 'ETF'
    ctx['snapshot']['positions'][0]['quantity'] = '11'
    ctx['snapshot']['positions'][0]['market_value'] = '1100'
    ctx['snapshot']['source_hash'] = 'observed-etf'


@when('an ETF observation is reconciled through the local API')
def reconcile(ctx):
    ctx['reconciliation'] = request(ctx, '/api/reconcile', {'snapshot': ctx['snapshot']})


@then('the API identifies the canonical security and suggested ETF classification')
def review(ctx):
    assert ctx['reconciliation']['classification_reviews'] == [{
        'security_id': ctx['security_id'], 'ticker': 'VTI', 'canonical_type': 'OTHER',
        'observed_type': 'ETF', 'action_required': 'EXPLICIT_CLASSIFICATION'}]
    assert ctx['ledger'].resolve('VTI')['asset_type'] == 'OTHER'


@then('the API explains the explicit classification correction')
def warning(ctx):
    assert any('security classify' in message for message in ctx['reconciliation']['warnings'])


@then('the inspection interface displays structured classification guidance')
def interface(ctx):
    script = request(ctx, '/app.js')
    assert 'result.classification_reviews' in script
    assert 'review.security_id' in script
    assert 'review.observed_type' in script
    assert 'invest security classify' in script


@when('the ETF observation is explicitly accepted through the local API')
def accept(ctx):
    request(ctx, '/api/apply', {'snapshot': ctx['snapshot'], 'confirm': True})


@then('accepted holdings retain the canonical OTHER classification')
def preserved(ctx):
    assert ctx['ledger'].resolve('VTI')['asset_type'] == 'OTHER'
    position = ctx['ledger'].rows('positions')[0]
    assert position['asset_type'] == 'OTHER'
    assert position['quantity'] == '11'
