"""Additional PRD financial safeguards over real ledgers and public interfaces."""

import copy
import hashlib
import json
from decimal import Decimal

import pytest
from typer.testing import CliRunner

from invest.analytics import risk
from invest.analytics_store import snapshot
from invest.cli import app
from invest.ledger import Ledger
from invest.lookthrough import exposure
from invest.market import MarketClient
from invest.portfolio_research_inputs import universe


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    path = tmp_path / 'fictional-analytics-audit.db'
    monkeypatch.setenv('INVEST_DB', str(path))
    instance = Ledger(path)
    instance.apply({
        'account': {'id': 'fictional', 'name': 'Fictional audit account',
                    'tax_status': 'TAX_FREE', 'history_complete': True},
        'positions': [{
            'security': ticker, 'name': 'Fictional ' + ticker, 'asset_type': 'ETF',
            'cusip': cusip, 'quantity': '1', 'price': '100', 'market_value': '100',
            'displayed_price_precision': 2, 'displayed_market_value_precision': 2,
        } for ticker, cusip in [('FUND-A', '111111111'), ('FUND-B', '222222222')]],
        'lots': [], 'cash': '100', 'cash_known': True, 'positions_complete': True,
        'lots_complete': False, 'source_timestamp': '2026-09-30',
        'source_hash': 'fictional-reviewed-audit-observation', 'data_environment': 'SYNTHETIC',
    })
    yield instance
    instance.connection.close()


def issue_codes(result):
    return {issue['code'] for issue in result.get('issues', [])}


@pytest.mark.parametrize('missing', ['2026-10-02', '2026-10-06'])
def test_risk_does_not_silently_drop_missing_interior_or_end_session(ledger, tmp_path, missing):
    days = ['2026-10-01', '2026-10-02', '2026-10-05', '2026-10-06']
    payload = {'history': {ticker: [
        {'date': day, 'adjClose': str(100 + index)} for index, day in enumerate(days)
        if ticker == 'FUND-A' or day != missing
    ] for ticker in ['FUND-A', 'FUND-B']}}
    fixture = tmp_path / 'fictional-risk.json'
    fixture.write_text(json.dumps(payload))
    before = copy.deepcopy(ledger.state())
    result = risk(before, MarketClient(ledger, fixture_path=fixture))
    assert ledger.state() == before
    assert result['status'] != 'AVAILABLE', 'Dropping sessions hides unsupported historical alignment'
    assert result['annualized_volatility'] is None
    assert result.get('issues'), 'Missing sessions require typed coverage issues, not warning prose'


def backtest_payload(ledger):
    sid = ledger.resolve('FUND-A')['id']
    days = ['2026-10-01', '2026-10-02', '2026-10-05']
    return {
        'start': days[0], 'end': days[-1], 'manifest_ids': ['fictional-history-manifest'],
        'candidates': [{'id': 'fictional-candidate', 'weights': {sid: '0.5', 'CASH': '0.5'}}],
        'history': {sid: [{'date': day, 'total_return_index': '100'} for day in days]},
        'history_provenance': {'kind': 'DIVIDEND_ADJUSTED_TOTAL_RETURN_INDEX',
                               'frequency': 'DAILY_TRADING_SESSION', 'expected_sessions': days,
                               'source_id': 'fictional-reviewed-history', 'data_environment': 'SYNTHETIC'},
        'cash_return': '0', 'fees': '0', 'starting_value': '1000', 'rebalancing': 'NONE',
    }


def invoke_backtest(tmp_path, payload):
    path = tmp_path / 'fictional-backtest.json'
    path.write_text(json.dumps(payload))
    response = CliRunner().invoke(app, ['backtest', 'run', str(path)])
    assert response.exit_code == 0, response.stderr
    return json.loads(response.stdout)


def test_backtest_nonzero_cash_return_is_explicitly_unsupported_or_applied(ledger, tmp_path):
    payload = backtest_payload(ledger)
    payload['cash_return'] = '0.05'
    before = copy.deepcopy(ledger.state())
    result = invoke_backtest(tmp_path, payload)
    assert ledger.state() == before
    if result['status'] != 'AVAILABLE':
        assert result.get('issues'), 'Unsupported cash-return model needs a typed outcome'
    else:
        run = result['candidates'][0]
        assert run['assumptions']['cash_return'] == '0.05'
        assert Decimal(str(run['total_return'])) > 0


def test_backtest_dated_contributions_are_pinned_or_explicitly_unsupported(ledger, tmp_path):
    payload = backtest_payload(ledger)
    schedule = [{'date': '2026-10-02', 'amount': '100'}]
    payload['contribution_schedule'] = schedule
    before = copy.deepcopy(ledger.state())
    result = invoke_backtest(tmp_path, payload)
    assert ledger.state() == before
    if result['status'] != 'AVAILABLE':
        assert result.get('issues'), 'Unsupported schedule needs a typed outcome'
    else:
        assert result['candidates'][0]['assumptions']['contribution_schedule'] == schedule


def test_pure_lookthrough_cannot_claim_complete_mixed_environment_exposure(ledger):
    sid = ledger.resolve('FUND-A')['id']
    state = ledger.planning_state()
    before = copy.deepcopy(state)
    observations = {sid: {'as_of': '2026-09-30', 'published_at': '2026-09-30',
                          'source_hash': 'fictional-real-labelled-source', 'data_environment': 'REAL',
                          'holdings': []}}
    result = exposure(state, observations, as_of='2026-10-01')
    assert state == before
    assert 'MIXED_DATA_ENVIRONMENT' in issue_codes(result)
    assert result['complete'] is False


def test_historical_universe_selects_immutable_known_vintage_not_latest_cache(ledger):
    sid = ledger.resolve('FUND-A')['id']
    ledger.register_security({'ticker': 'FICTIONAL-LEAF', 'name': 'Fictional underlying company',
                              'asset_type': 'STOCK', 'currency': 'USD', 'cusip': '333333333',
                              'source': 'Reviewed fictional original security identifier'})
    leaf = ledger.resolve('FICTIONAL-LEAF')['id']
    for identity, published, weight in [('known', '2026-09-30', '1'), ('future', '2026-10-10', '0.5')]:
        rows = [{'security_id': leaf, 'cusip': '333333333', 'weight': weight}]
        encoded = json.dumps(rows, sort_keys=True, separators=(',', ':')).encode()
        payload = {'id': 'fictional-' + identity, 'data_environment': 'SYNTHETIC',
                   'artifacts': [{'id': 'holdings-' + identity, 'kind': 'FUND_HOLDINGS',
                                  'provider': 'FICTIONAL_REVIEWED', 'security_id': sid,
                                  'as_of': '2026-09-30', 'observed_at': published,
                                  'published_at': published, 'sha256': hashlib.sha256(encoded).hexdigest(),
                                  'rows': rows}]}
        assert snapshot(ledger, payload, confirm=True)['committed'] is True
    with ledger.connection:
        ledger.put('fund_holdings_cache', 'latest', {
            'id': 'latest', 'ticker': 'FUND-A', 'retrieved_at': '2026-10-10T12:00:00Z',
            'data_as_of': '2026-09-30', 'published_at': '2026-10-10',
            'data_environment': 'SYNTHETIC', 'holdings': [
                {'cusip': '333333333', 'weight': '0.5'}],
        })
    before = copy.deepcopy(ledger.state())
    result = universe(ledger, as_of='2026-10-01')
    assert ledger.state() == before
    serialized = json.dumps(result, sort_keys=True)
    assert 'holdings-known' in serialized, 'Historical paths must pin the actually known immutable artifact'
    assert 'latest' not in serialized and 'holdings-future' not in serialized
