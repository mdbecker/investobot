"""Read-only dashboard behavior over accepted synthetic facts and saved results."""

import json
import threading
from http.client import HTTPConnection
from pathlib import Path

import httpx
import pytest
from bs4 import BeautifulSoup
from planning_fixtures import saved_proposal

from invest import backtest, plans, targets
from invest.ledger import Ledger
from invest.market import MarketClient
from invest.web import create_server

POST_ROUTES = ['/api/import', '/api/reconcile', '/api/apply', '/api/activity',
               '/api/analyze', '/api/targets/save', '/api/targets/activate',
               '/api/targets/archive', '/api/plans/generate', '/api/plans/compare',
               '/api/prompts/save', '/api/prompts/delete', '/api/agent/execute', '/unknown']


@pytest.fixture
def dashboard(tmp_path, monkeypatch):
    monkeypatch.setenv('INVEST_CONFIG', str(tmp_path / 'config.toml'))
    monkeypatch.setenv('FMP_API_KEY', 'fictional-provider-key')
    monkeypatch.delenv('INVEST_FIXTURES', raising=False)
    path = tmp_path / 'ledger.db'
    server = create_server(path, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield {'path': path, 'server': server, 'tmp': tmp_path}
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def request(ctx, path, *, method='GET', body=None, headers=None):
    conn = HTTPConnection('127.0.0.1', ctx['server'].server_port, timeout=5)
    try:
        conn.request(method, path, body=body, headers=headers or {})
        response = conn.getresponse()
        raw = response.read().decode()
        return response.status, json.loads(raw) if response.getheader('Content-Type').startswith(
            'application/json') else raw
    finally:
        conn.close()


def accepted(ctx, asset_type='STOCK'):
    ledger = Ledger(ctx['path'])
    ledger.apply({'data_environment': 'SYNTHETIC',
        'account': {'id': 'ira', 'name': 'Synthetic IRA', 'tax_status': 'TAX_FREE'},
        'positions': [{'security': 'AAA', 'asset_type': asset_type, 'quantity': '10',
                       'price': '100', 'market_value': '1000', 'as_of': '2026-10-08',
                       'displayed_price_precision': 0, 'displayed_market_value_precision': 0}],
        'cash': '200', 'cash_known': True, 'positions_complete': True,
        'source_timestamp': '2026-10-08', 'source_hash': 'synthetic-viewer'})
    return ledger


@pytest.mark.parametrize('route', POST_ROUTES)
def test_every_post_is_method_not_allowed_without_creating_selected_ledger(dashboard, route):
    # Given no ledger, even a malformed body with no Origin cannot start a workflow.
    code, error = request(dashboard, route, method='POST', body='not JSON')
    assert code == 405, error
    assert error['code'] == 1 and isinstance(error['error'], str)
    assert not dashboard['path'].exists()


def test_former_posts_preserve_all_records_and_prompt_files(dashboard):
    # Given accepted financial facts and a user prompt, former commands are inert.
    ledger = accepted(dashboard)
    try:
        before = list(ledger.connection.iterdump())
    finally:
        ledger.connection.close()
    prompt = dashboard['tmp'] / 'prompts' / 'human.md'
    prompt.parent.mkdir()
    prompt.write_text('Reviewed human prompt')
    for route in POST_ROUTES:
        code, value = request(dashboard, route, method='POST', body='{}', headers={
            'Content-Type': 'application/json',
            'Origin': f"http://127.0.0.1:{dashboard['server'].server_port}"})
        assert code == 405, value
    ledger = Ledger(dashboard['path'])
    try:
        assert list(ledger.connection.iterdump()) == before
    finally:
        ledger.connection.close()
    assert prompt.read_text() == 'Reviewed human prompt'
    assert list(prompt.parent.iterdir()) == [prompt]


def test_absent_dashboard_has_empty_saved_results_without_creating_database(dashboard):
    for route, key in [('/api/plans', 'plans'), ('/api/targets', 'targets'),
                       ('/api/backtests', 'runs')]:
        code, value = request(dashboard, route)
        assert code == 200, value
        assert value[key] == []
    code, value = request(dashboard, '/api/overview')
    assert code == 200, value
    assert value['state']['accounts'] == []
    assert not dashboard['path'].exists()


def test_accepted_balances_and_existing_saved_plan_are_viewable(dashboard):
    ledger = accepted(dashboard)
    try:
        sid = ledger.resolve('AAA')['id']
        target = targets.save(ledger, {'name': 'Hold shares', 'target_allocations': {sid: '1'},
            'planning_constraints': {'eligible_accounts': ['ira'],
                                    'permitted_securities': {'ira': [sid]}}})
        plan = saved_proposal(ledger, MarketClient(ledger, fixture_path=Path(
            'tests/fixtures/fmp-synthetic.json')), target['id'], as_of='2026-10-08')
        before = list(ledger.connection.iterdump())
        code, overview = request(dashboard, '/api/overview')
        assert code == 200, overview
        assert overview['summary']['total_value'] == '1200'
        assert overview['summary']['cash'] == '200'
        assert request(dashboard, '/api/plans')[1]['plans'][0]['id'] == plan['id']
        assert request(dashboard, '/api/plans/' + plan['id'])[1] == plans.show(ledger, plan['id'])
        assert request(dashboard, '/api/plans/' + plan['id'] + '/report?format=json')[1] == plan
        assert list(ledger.connection.iterdump()) == before
    finally:
        ledger.connection.close()


def test_saved_backtests_are_listed_read_and_compared_with_assumption_mismatch(dashboard):
    ledger = accepted(dashboard)
    try:
        sid = ledger.resolve('AAA')['id']
        results = []
        for fee in ['0', '1']:
            results.append(backtest.run(ledger, portfolio={sid: '1'}, start='2026-10-01',
                end='2026-10-02', policy={'starting_value': '1000', 'cash_return': '0',
                                        'fee_per_trade': fee},
                manifest={'id': 'synthetic-history', 'data_environment': 'SYNTHETIC',
                          'sessions': ['2026-10-01', '2026-10-02'], 'series': {sid: [
                              {'date': '2026-10-01', 'total_return_index': '100'},
                              {'date': '2026-10-02', 'total_return_index': '101'}]}}))
        before = list(ledger.connection.iterdump())
        code, listing = request(dashboard, '/api/backtests')
        assert code == 200, listing
        assert {row['id'] for row in listing['runs']} == {row['id'] for row in results}
        assert request(dashboard, '/api/backtests/' + results[0]['id']) == (200, results[0])
        query = '&'.join('run_id=' + row['id'] for row in results)
        code, comparison = request(dashboard, '/api/backtests/compare?' + query)
        assert code == 200, comparison
        assert comparison == backtest.compare(ledger, [row['id'] for row in results])
        assert comparison['status'] == 'INCOMPARABLE'
        assert 'ASSUMPTION_MISMATCH' in {issue['code'] for issue in comparison['issues']}
        assert list(ledger.connection.iterdump()) == before
    finally:
        ledger.connection.close()


def test_fund_overview_without_cached_holdings_never_contacts_provider(dashboard, monkeypatch):
    ledger = accepted(dashboard, asset_type='ETF')
    try:
        before = list(ledger.connection.iterdump())
        calls = []

        def unavailable(*args, **kwargs):
            calls.append(args)
            raise AssertionError('Dashboard attempted outbound provider request')

        monkeypatch.setattr(httpx, 'get', unavailable)
        code, value = request(dashboard, '/api/overview')
        assert calls == [], 'GET must not refresh missing holdings evidence'
        assert code == 200, value
        assert value['exposure']['unknown_exposure_percentage'] != '0'
        assert list(ledger.connection.iterdump()) == before
    finally:
        ledger.connection.close()


def test_served_viewer_contains_no_retired_forms_or_command_navigation(dashboard):
    code, html = request(dashboard, '/')
    assert code == 200
    page = BeautifulSoup(html, 'html.parser')
    assert not page.select('form, textarea, input[type="file"], label.confirmation')
    links = {node.get('href') for node in page.select('#primary-nav a')}
    assert {'#overview', '#targets', '#plans', '#backtests'} <= links
    assert not links & {'#prompts', '#import', '#activity', '#analysis'}
    assert 'saved backtests' in page.get_text(' ', strip=True).lower()
    script = request(dashboard, '/app.js')[1]
    assert 'POST' not in script
    for action in ['targets/save', 'plans/generate', 'prompts/save', 'api/analyze']:
        assert action not in script


def test_get_rejects_foreign_host_and_preserves_safe_headers(dashboard):
    code, error = request(dashboard, '/api/summary', headers={'Host': 'external.example'})
    assert code == 403 and error['code'] == 1
    assert not dashboard['path'].exists()


def test_mixed_currency_summary_returns_typed_error(dashboard):
    ledger = Ledger(dashboard['path'])
    try:
        for account, currency in [('dollars', 'USD'), ('euros', 'EUR')]:
            ledger.apply({'account': {'id': account, 'name': account, 'currency': currency},
                          'positions': [], 'cash': '100', 'source_hash': account,
                          'data_environment': 'SYNTHETIC'})
    finally:
        ledger.connection.close()
    code, error = request(dashboard, '/api/summary')
    assert code == 409 and error['code'] == 3


def test_unmarked_accepted_holding_preserves_viewable_facts_and_typed_exposure_gap(
        dashboard, monkeypatch):
    # Given a confirmed purchase without an independent accepted valuation mark.
    ledger = accepted(dashboard)
    try:
        ledger.register_security({'ticker': 'UNMARKED', 'name': 'Synthetic unmarked stock',
                                  'asset_type': 'STOCK', 'currency': 'USD',
                                  'source': 'Reviewed synthetic security identity'})
        sid = ledger.resolve('AAA')['id']
        target = targets.save(ledger, {'name': 'Accepted active target',
            'target_allocations': {sid: '1'}, 'planning_constraints': {
                'eligible_accounts': ['ira'], 'permitted_securities': {'ira': [sid]}}})
        targets.activate(ledger, target['id'])
        ledger.record_activity({'activity_id': 'synthetic-unmarked-purchase', 'account_id': 'ira',
                                'type': 'BUY', 'security': 'UNMARKED', 'quantity': '1',
                                'price': '10', 'fee': '0', 'date': '2026-10-08'}, yes=True)
        before = list(ledger.connection.iterdump())
        calls = []

        def unavailable(*args, **kwargs):
            calls.append(args)
            raise AssertionError('Viewer attempted a provider request')

        monkeypatch.setattr(httpx, 'get', unavailable)
        code, value = request(dashboard, '/api/overview')
        assert code == 200, value
        assert value['summary']['total_value'] is None
        assert value['summary']['cash'] == '190'
        holding = next(row for row in value['state']['positions'] if row['security'] == 'UNMARKED')
        assert holding['quantity'] == '1' and holding['market_value'] is None
        assert value['exposure']['status'] == 'PARTIAL'
        assert value['exposure']['total_value'] is None
        assert value['exposure']['unknown_exposure_percentage'] is None
        assert 'MISSING_VALUATION_MARK' in {issue['code'] for issue in value['exposure']['issues']}
        assert value['active_target']['id'] == target['id']
        assert value['target_diff']['status'] == 'UNAVAILABLE'
        assert value['target_diff']['allocations'] == []
        assert 'MISSING_VALUATION_MARK' in {issue['code'] for issue in value['target_diff']['issues']}
        assert request(dashboard, '/api/targets/' + target['id'])[1]['id'] == target['id']
        code, drift = request(dashboard, '/api/targets/' + target['id'] + '/diff')
        assert code == 200 and drift['status'] == 'UNAVAILABLE'
        assert calls == []
        assert list(ledger.connection.iterdump()) == before
    finally:
        ledger.connection.close()


@pytest.mark.parametrize('weight', ['1', '0.6'])
def test_persisted_fund_source_issues_preserve_numeric_coverage_and_exposure(dashboard, weight):
    # Given a persisted synthetic fund observation with incomplete source-date evidence.
    from decimal import Decimal

    ledger = accepted(dashboard, asset_type='ETF')
    issue = {'code': 'PARTIAL_SOURCE_DATE_COVERAGE',
             'message': 'Some constituent source dates are unverified',
             'blocks_calculation': False, 'blocks_proposals': True,
             'blocks_execution_review': True}
    try:
        with ledger.connection:
            ledger.put('fund_holdings_cache', 'synthetic-partial-date', {
                'id': 'synthetic-partial-date', 'ticker': 'AAA',
                'data_environment': 'SYNTHETIC', 'source': 'REVIEWED_SYNTHETIC',
                'retrieved_at': '2026-10-12T12:00:00Z', 'data_as_of': '2026-10-08',
                'warnings': [], 'issues': [issue], 'holdings': [{
                    'identifier': 'CUSIP:333333333', 'cusip': '333333333',
                    'ticker': 'SYNTHETIC-LEAF', 'weight': weight}]})
        before = list(ledger.connection.iterdump())
        # When the read-only dashboard calculates exposure from stored evidence.
        code, result = request(dashboard, '/api/overview')
        assert code == 200, result
        exposure = result['exposure']
        leaf = next(row for row in exposure['exposures'] if row['ticker'] == 'SYNTHETIC-LEAF')
        # Then known dollars and residual remain exact, separately from evidence quality.
        assert Decimal(leaf['total_value']) == Decimal('1000') * Decimal(weight)
        assert Decimal(exposure['unknown_exposure_value']) == Decimal('1000') * (1 - Decimal(weight))
        assert any(row['code'] == issue['code'] and row['blocks_proposals'] for row in exposure['issues'])
        assert any('source dates' in warning for warning in exposure['warnings'])
        coverage = next(iter(exposure['fund_coverage'].values()))
        assert Decimal(coverage['represented_weight']) == Decimal(weight)
        assert coverage['numeric_complete'] is (weight == '1')
        assert coverage['evidence_complete'] is False
        assert list(ledger.connection.iterdump()) == before
    finally:
        ledger.connection.close()


def test_many_saved_backtests_list_compact_summaries_and_keep_full_immutable_review(dashboard):
    # Given many accepted synthetic saved runs with full histories and differing assumptions.
    ledger = accepted(dashboard)
    try:
        sid = ledger.resolve('AAA')['id']
        sessions = [f'2026-10-{day:02d}' for day in range(1, 21)]
        saved = [backtest.run(ledger, portfolio={sid: '1'}, start=sessions[0], end=sessions[-1],
            policy={'starting_value': '1000', 'cash_return': '0', 'fee_per_trade': str(index % 2)},
            manifest={'id': 'synthetic-long-history', 'data_environment': 'SYNTHETIC',
                      'sessions': sessions, 'series': {sid: [
                          {'date': day, 'total_return_index': str(100 + index)}
                          for index, day in enumerate(sessions)]}}) for index in range(16)]
        before = list(ledger.connection.iterdump())
        # When listing saved runs, only a stable small summary crosses the HTTP boundary.
        code, listing = request(dashboard, '/api/backtests')
        assert code == 200, listing
        expected_keys = {'id', 'start', 'end', 'status', 'created_at', 'total_return',
                         'annualized_return', 'volatility', 'max_drawdown', 'final_value', 'turnover'}
        assert len(listing['runs']) == len(saved)
        by_id = {row['id']: row for row in saved}
        for row in listing['runs']:
            assert set(row) == expected_keys
            assert row == {key: by_id[row['id']].get(key) for key in expected_keys}
        assert len(json.dumps(listing)) < len(json.dumps({'runs': saved})) / 2
        # Then full inspection and assumption-mismatch comparison retain original records.
        assert request(dashboard, '/api/backtests/' + saved[0]['id']) == (200, saved[0])
        query = '&'.join('run_id=' + row['id'] for row in saved[:2])
        code, comparison = request(dashboard, '/api/backtests/compare?' + query)
        assert code == 200 and comparison == backtest.compare(ledger, [row['id'] for row in saved[:2]])
        assert comparison['status'] == 'INCOMPARABLE'
        assert 'ASSUMPTION_MISMATCH' in {issue['code'] for issue in comparison['issues']}
        assert list(ledger.connection.iterdump()) == before
    finally:
        ledger.connection.close()
