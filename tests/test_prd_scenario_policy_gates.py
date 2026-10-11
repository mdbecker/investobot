"""Legacy generation is an unapproved hypothetical scenario, never a policy bypass."""

import copy
import json
from decimal import Decimal

import pytest
from typer.testing import CliRunner

from invest.cli import app
from invest.ledger import Ledger
from invest.market import MarketClient
from invest.plans import generate
from invest.targets import save


def setup(tmp_path, monkeypatch, *, baseline='SYNTHETIC', target_environment='SYNTHETIC'):
    path = tmp_path / 'fictional-scenario.db'
    fixture = tmp_path / 'fictional-public-data.json'
    fixture.write_text(json.dumps({'history': {}, 'holdings': {}}))
    monkeypatch.setenv('INVEST_DB', str(path))
    monkeypatch.setenv('INVEST_FIXTURES', str(fixture))
    monkeypatch.setenv('INVEST_PROMPTS', str(tmp_path / 'prompts'))
    ledger = Ledger(path)
    ledger.apply({
        'account': {'id': 'ira', 'name': 'Fictional scenario IRA', 'tax_status': 'TAX_FREE',
                    'history_complete': True},
        'positions': [{'security': ticker, 'name': 'Fictional ' + ticker, 'asset_type': 'STOCK',
                       'quantity': quantity, 'price': '100', 'market_value': value,
                       'displayed_price_precision': 2, 'displayed_market_value_precision': 2}
                      for ticker, quantity, value in [('OLD', '10', '1000'), ('NEW', '0', '0')]],
        'lots': [], 'cash': '0', 'cash_known': True, 'positions_complete': True,
        'lots_complete': False, 'source_timestamp': '2026-10-09',
        'source_hash': 'fictional-scenario-original-source', 'data_environment': baseline or 'SYNTHETIC',
    })
    if baseline is None:
        # Model a historical ledger whose source environment was never recorded.
        # New acceptance must not permit this missing provenance.
        with ledger.connection:
            for table in ('accounts', 'securities', 'positions', 'cash_balances'):
                for row in ledger.rows(table):
                    ledger.put(table, row['id'], dict(row, data_environment=None))
            ledger.connection.execute("UPDATE snapshot_observations SET data_environment=NULL, "
                "payload_json=json_set(payload_json, '$.data_environment', NULL)")
    old, new = ledger.resolve('OLD')['id'], ledger.resolve('NEW')['id']
    target = save(ledger, {'name': 'Fictional replacement scenario',
                          'data_environment': target_environment,
                          'target_allocations': {old: '0', new: '1'},
                          'planning_constraints': {'eligible_accounts': ['ira'],
                                                   'permitted_securities': {'ira': [old, new]}}})
    return ledger, MarketClient(ledger, fixture_path=fixture), target['id'], old, new


def unapproved(result):
    assert result['mode'] == 'HYPOTHETICAL'
    assert result['status'] == 'REVIEW_REQUIRED'
    matching = [issue for issue in result['issues'] if issue['code'] == 'UNAPPROVED_TRADING_POLICY']
    assert matching
    assert matching[0]['blocks_calculation'] is False
    assert matching[0]['blocks_proposals'] is True
    assert matching[0]['blocks_execution_review'] is True


def test_synthetic_direct_generation_preserves_simulation_but_requires_policy_review(tmp_path, monkeypatch):
    ledger, client, target, _, new = setup(tmp_path, monkeypatch)
    try:
        before = copy.deepcopy(ledger.state())
        result = generate(ledger, client, target, as_of='2026-10-10')
        assert ledger.state() == before
        assert [action['type'] for action in result['proposed_actions']] == ['SELL', 'BUY']
        assert result['proposed_actions'][1]['security'] == new
        assert Decimal(result['proposed_allocation']['total_value']) == 1000
        assert ledger.connection.execute('SELECT count(*) FROM plan_runs WHERE id=?', (result['id'],)).fetchone()[0] == 1
        unapproved(result)
    finally:
        ledger.connection.close()


def test_synthetic_cli_generation_exposes_typed_unapproved_scenario_summary(tmp_path, monkeypatch):
    ledger, _, target, _, _ = setup(tmp_path, monkeypatch)
    try:
        before = copy.deepcopy(ledger.state())
        response = CliRunner().invoke(app, ['plan', 'generate', '--target', target, '--as-of', '2026-10-10'])
        assert response.exit_code == 0, response.stderr
        assert ledger.state() == before
        unapproved(json.loads(response.stdout)['plan'])
    finally:
        ledger.connection.close()


@pytest.mark.parametrize('real_input', ['baseline', 'target', 'prices'])
def test_real_input_cannot_use_unapproved_direct_scenario_generator(tmp_path, monkeypatch, real_input):
    ledger, client, target, old, new = setup(
        tmp_path, monkeypatch, baseline='REAL' if real_input == 'baseline' else 'SYNTHETIC',
        target_environment='REAL' if real_input == 'target' else 'SYNTHETIC')
    prices = None if real_input != 'prices' else {
        sid: {'price': '100', 'as_of': '2026-10-10', 'currency': 'USD',
              'source': 'Reviewed fictional REAL-labelled price isolation test', 'data_environment': 'REAL'}
        for sid in [old, new]}
    try:
        before = copy.deepcopy(ledger.state())
        result = generate(ledger, client, target, as_of='2026-10-10', prices=prices)
        assert ledger.state() == before
        assert result['status'] == 'BLOCKED'
        assert result['proposed_actions'] == []
        assert any(issue['blocks_proposals'] for issue in result['issues'])
        assert ledger.connection.execute('SELECT count(*) FROM plan_runs').fetchone()[0] == 0
    finally:
        ledger.connection.close()


def test_real_cli_generation_returns_structured_blocked_outcome_without_saved_plan(tmp_path, monkeypatch):
    ledger, _, target, _, _ = setup(tmp_path, monkeypatch, baseline='REAL', target_environment='REAL')
    try:
        before = copy.deepcopy(ledger.state())
        response = CliRunner().invoke(app, ['plan', 'generate', '--target', target, '--as-of', '2026-10-10'])
        assert response.exit_code == 0, response.stderr
        result = json.loads(response.stdout)
        blocked = result.get('plan', result)
        assert blocked['status'] == 'BLOCKED'
        assert blocked['proposed_actions'] == []
        assert blocked['issues']
        assert ledger.state() == before
        assert ledger.connection.execute('SELECT count(*) FROM plan_runs').fetchone()[0] == 0
    finally:
        ledger.connection.close()


def test_unknown_legacy_provenance_is_not_synthesized_as_synthetic(tmp_path, monkeypatch):
    ledger, client, target, _, _ = setup(tmp_path, monkeypatch, baseline=None, target_environment=None)
    try:
        before = copy.deepcopy(ledger.state())
        result = generate(ledger, client, target, as_of='2026-10-10')
        assert ledger.state() == before
        unapproved(result)
        assert result.get('data_environment') is None
        assert 'UNKNOWN_DATA_ENVIRONMENT' in {issue['code'] for issue in result['issues']}
    finally:
        ledger.connection.close()
