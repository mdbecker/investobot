"""Dashboard GET requests must never initialize or modify selected ledger files."""

import hashlib
import json
import sqlite3
import threading
from http.client import RemoteDisconnected
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

import pytest
from test_mvp_research_workflows_bdd import accepted_household
from typer.testing import CliRunner

from invest.cli import app
from invest.ledger import Ledger
from invest.web import create_server

ROUTES = [('/api/check', {'as_of': '2026-10-10'},
           ['portfolio', 'check', '--as-of', '2026-10-10']),
          ('/api/performance', {'from': '2026-10-09', 'to': '2026-10-10'},
           ['portfolio', 'performance', '--from', '2026-10-09', '--to', '2026-10-10']),
          ('/api/search', {'query': 'fictional'}, ['research', 'search', '--query', 'fictional'])]


@pytest.fixture
def dashboard(tmp_path, monkeypatch):
    path = tmp_path / 'selected.db'
    monkeypatch.setenv('INVEST_DB', str(path))
    monkeypatch.setenv('INVEST_CONFIG', str(tmp_path / 'config.toml'))
    server = create_server(path, host='127.0.0.1', port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield {'path': path, 'base': f'http://127.0.0.1:{server.server_port}'}
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def get(ctx, route, params):
    try:
        with urlopen(ctx['base'] + route + '?' + urlencode(params), timeout=5) as response:
            return response.status, json.loads(response.read())
    except HTTPError as error:
        return error.code, json.loads(error.read())
    except (RemoteDisconnected, ConnectionResetError, URLError) as error:
        # A lost HTTP response is an observable failure, never a successful JSON error.
        return None, {'transport_error': type(error).__name__}


@pytest.mark.parametrize('route,params,args', ROUTES)
def test_missing_selected_dashboard_reads_do_not_create_database(dashboard, route, params, args):
    expected_cli = CliRunner().invoke(app, args)
    assert expected_cli.exit_code == 0, expected_cli.output
    expected = json.loads(expected_cli.stdout)
    assert not dashboard['path'].exists()
    code, response = get(dashboard, route, params)
    assert not dashboard['path'].exists(), 'GET initialized the absent selected ledger'
    assert not dashboard['path'].with_name('selected.db-wal').exists()
    assert not dashboard['path'].with_name('selected.db-shm').exists()
    assert code == 200, response
    assert response == expected


@pytest.mark.parametrize('route,params,_args', ROUTES)
def test_incompatible_selected_database_returns_json_error_without_mutation(
        dashboard, route, params, _args):
    connection = sqlite3.connect(dashboard['path'])
    try:
        connection.execute('PRAGMA user_version=9')
        connection.execute('CREATE TABLE original_private_marker(value TEXT)')
        connection.execute("INSERT INTO original_private_marker VALUES ('fictional legacy marker')")
        connection.commit()
    finally:
        connection.close()
    original = hashlib.sha256(dashboard['path'].read_bytes()).hexdigest()
    code, response = get(dashboard, route, params)
    assert hashlib.sha256(dashboard['path'].read_bytes()).hexdigest() == original
    assert not dashboard['path'].with_name('selected.db-wal').exists()
    assert not dashboard['path'].with_name('selected.db-shm').exists()
    assert code == 409, response
    assert response['code'] == 3
    assert isinstance(response['error'], str)
    assert 'transport_error' not in response


@pytest.mark.parametrize('route,params,args', ROUTES)
def test_existing_selected_dashboard_reads_preserve_financial_fingerprint(dashboard, route, params, args):
    ctx = {'path': dashboard['path']}
    accepted_household(ctx)
    ledger = Ledger(dashboard['path'])
    before = ledger.planning_state()
    ledger.connection.close()
    expected_cli = CliRunner().invoke(app, args)
    assert expected_cli.exit_code == 0, expected_cli.output
    code, response = get(dashboard, route, params)
    assert code == 200, response
    assert response == json.loads(expected_cli.stdout)
    ledger = Ledger(dashboard['path'])
    try:
        assert ledger.planning_state() == before
    finally:
        ledger.connection.close()
