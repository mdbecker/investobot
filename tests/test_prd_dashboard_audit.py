"""Thin dashboard reads must use the same financial domains as the public CLI."""

import hashlib
import json
import threading
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen

import pytest
from bs4 import BeautifulSoup
from test_mvp_research_workflows_bdd import accepted_household
from typer.testing import CliRunner

from invest.cli import app
from invest.ledger import Ledger
from invest.search import store_chunks
from invest.web import create_server


@pytest.fixture
def dashboard(tmp_path, monkeypatch):
    path = tmp_path / 'fictional-ledger.db'
    monkeypatch.setenv('INVEST_DB', str(path))
    monkeypatch.setenv('INVEST_CONFIG', str(tmp_path / 'config.toml'))
    ctx = {'path': path}
    accepted_household(ctx, source_date='2026-10-09', history_complete=True)
    accepted_household(ctx, source_date='2026-10-10', price='110', history_complete=True)
    server = create_server(path, host='127.0.0.1', port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield {'path': path, 'base': f'http://127.0.0.1:{server.server_port}'}
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def get(ctx, route, query=None):
    url = ctx['base'] + route + ('?' + urlencode(query) if query else '')
    try:
        with urlopen(url, timeout=5) as response:
            body = response.read().decode()
            return response.status, json.loads(body) if route.startswith('/api/') else body
    except HTTPError as error:
        return error.code, json.loads(error.read())


def financial_state(path):
    ledger = Ledger(path)
    try:
        return ledger.planning_state()
    finally:
        ledger.connection.close()


def cli(args):
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout)


def test_dashboard_preflight_get_matches_public_cli_without_writes(dashboard):
    before = financial_state(dashboard['path'])
    expected = cli(['portfolio', 'check', '--as-of', '2026-10-10'])
    code, actual = get(dashboard, '/api/check', {'as_of': '2026-10-10'})
    assert code == 200, actual
    assert actual == expected
    assert 'issues' in actual and 'coverage' in actual
    assert financial_state(dashboard['path']) == before


@pytest.mark.parametrize('account', [None, 'synthetic'])
def test_dashboard_actual_performance_get_matches_cli_interval_and_account(dashboard, account):
    before = financial_state(dashboard['path'])
    query = {'from': '2026-10-09', 'to': '2026-10-10'}
    args = ['portfolio', 'performance', '--from', query['from'], '--to', query['to']]
    if account:
        query['account'] = account
        args += ['--account', account]
    expected = cli(args)
    code, actual = get(dashboard, '/api/performance', query)
    assert code == 200, actual
    assert actual == expected
    assert actual['mode'] == 'ACTUAL'
    assert 'issues' in actual
    assert financial_state(dashboard['path']) == before


def test_dashboard_research_search_get_matches_authorized_public_corpus(dashboard):
    text = 'Fictional public issuer opened its fictional factory.'
    store_chunks(dashboard['path'], [{'chunk_id': 'fictional-public-chunk',
        'document_id': 'fictional-release', 'text': text, 'source_url': 'https://example.invalid/release',
        'source_date': '2026-10-10', 'permission': 'PERMITTED',
        'content_hash': hashlib.sha256(text.encode()).hexdigest(), 'offset_start': 0,
        'offset_end': len(text), 'license': 'Reviewed fictional public reuse permission',
        'data_environment': 'SYNTHETIC'}], confirmed=True)
    before = financial_state(dashboard['path'])
    expected = cli(['research', 'search', '--query', 'factory'])
    assert expected['results'], expected
    code, actual = get(dashboard, '/api/search', {'query': 'factory'})
    assert code == 200, actual
    assert actual == expected
    assert financial_state(dashboard['path']) == before


def test_served_dashboard_exposes_preflight_and_actual_performance_affordances(dashboard):
    code, page = get(dashboard, '/')
    assert code == 200
    parsed = BeautifulSoup(page, 'html.parser')
    text = parsed.get_text(' ', strip=True).lower()
    assert 'preflight' in text, 'Investors need a visible preflight review before planning'
    assert 'actual performance' in text, 'Actual returns must be distinct from hypothetical scenarios'
    assert 'hypothetical' in text
    assert parsed.select('input[type="date"]'), 'Dated financial reviews require visible date selection'
