
import json

import pytest
from pytest_bdd import given, scenarios, then, when
from typer.testing import CliRunner

from invest.cli import app
from invest.ledger import Ledger

scenarios('features/target_cli.feature')


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.setenv('INVEST_DB', str(tmp_path / 'db'))
    monkeypatch.setenv('INVEST_CONFIG', str(tmp_path / 'config.toml'))
    return {'ledger': Ledger(tmp_path / 'db'), 'runner': CliRunner()}


@given('a synthetic accepted investment and a target input')
def investment(ctx):
    ctx['ledger'].apply({'account': {'id': 'ira', 'name': 'IRA', 'tax_status': 'TAX_FREE'},
                         'positions': [{'security': 'AAA', 'asset_type': 'ETF', 'quantity': '10',
                                        'market_value': '1000', 'price': '100'}],
                         'cash': '100', 'source_hash': 'synthetic', 'source_timestamp': '2026-10-08'})
    sid = ctx['ledger'].resolve('AAA')['id']
    ctx['input'] = {'name': 'Balanced', 'target_allocations': {sid: '0.9', 'CASH': '0.1'},
                    'planning_constraints': {'eligible_accounts': ['ira'],
                                             'permitted_securities': {'ira': [sid]}}}
    ctx['before'] = ctx['ledger'].state()


@when('the agent saves lists activates and compares the target through the CLI')
def commands(ctx):
    saved = ctx['runner'].invoke(app, ['target', 'save', '-'], input=json.dumps(ctx['input']))
    assert saved.exit_code == 0, saved.output
    target_id = json.loads(saved.stdout)['id']
    ctx['results'] = [saved] + [ctx['runner'].invoke(app, ['target', cmd, target_id])
                               for cmd in ['show', 'activate', 'diff']]
    ctx['results'].append(ctx['runner'].invoke(app, ['target', 'list']))


@then('all outputs are JSON and actual holdings remain unchanged')
def outputs(ctx):
    for result in ctx['results']:
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)
    assert ctx['ledger'].state() == ctx['before']


@when('the agent registers a verified synthetic investment')
def register(ctx):
    ctx['result'] = ctx['runner'].invoke(app, ['security', 'register', '-'], input=json.dumps({
        'ticker': 'SYNTH', 'name': 'Synthetic fund', 'asset_type': 'ETF', 'currency': 'USD',
        'isin': 'SYNTHETICISIN', 'source': 'human-verified synthetic metadata'}))


@then('its canonical ID is available with no positions or activities')
def registered(ctx):
    assert ctx['result'].exit_code == 0, ctx['result'].output
    assert json.loads(ctx['result'].stdout)['id'] == ctx['ledger'].resolve('SYNTH')['id']
    assert ctx['ledger'].state()['positions'] == []
    assert ctx['ledger'].state()['activities'] == []


@given('a version one database with historical portfolio data')
def legacy(ctx):
    import sqlite3

    from invest.ledger import TABLES

    ctx['legacy_path'] = ctx['ledger'].path.parent / 'legacy.db'
    conn = sqlite3.connect(ctx['legacy_path'])
    with conn:
        for table in TABLES:
            if table not in {'targets', 'target_versions', 'plans'}:
                conn.execute(f'CREATE TABLE {table} (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
        conn.execute('PRAGMA user_version=1')
        conn.execute('INSERT INTO snapshots VALUES (?, ?)', ('legacy-snapshot', json.dumps({
            'id': 'legacy-snapshot', 'source_hash': 'old', 'account': {'id': 'old'}})))
        conn.execute('INSERT INTO activities VALUES (?, ?)', ('legacy-activity', json.dumps({
            'id': 'legacy-activity', 'type': 'BUY', 'quantity': '1'})))
    conn.close()


@when('the updated ledger opens the database')
def migrated(ctx):
    import pytest

    from invest.models import DomainError
    with pytest.raises(DomainError, match='reset'):
        Ledger(ctx['legacy_path'])


@then('the historical data remains readable and planning tables are available')
def preserved(ctx):
    import sqlite3
    with sqlite3.connect(ctx['legacy_path']) as connection:
        assert connection.execute('PRAGMA user_version').fetchone()[0] == 1
        assert connection.execute('SELECT count(*) FROM snapshots').fetchone()[0] == 1
