"""Observable historical-price coverage without an invented exchange calendar."""

import json

import pytest

from invest.backtest import run
from invest.ledger import Ledger
from invest.market import MarketClient
from invest.models import DomainError


@pytest.fixture
def ledger(tmp_path):
    result = Ledger(tmp_path / 'synthetic.db')
    try:
        yield result
    finally:
        result.connection.close()


def history(ledger, tmp_path, rows):
    fixture = tmp_path / 'provider.json'
    fixture.write_text(json.dumps({'history': {'FAKE': rows}}))
    return MarketClient(ledger, fixture_path=fixture).history('FAKE')


def test_exchange_holiday_preserves_observed_prices_without_claiming_missing_sessions(ledger, tmp_path):
    # Given Friday and Tuesday observations around the synthetic Labor Day holiday.
    rows = [{'date': '2026-09-04', 'adjClose': '100'},
            {'date': '2026-09-08', 'adjClose': '102'}]
    # When the provider history has no independently pinned session calendar.
    result = history(ledger, tmp_path, rows)
    # Then observations are usable and full exchange-session completeness is unverified.
    assert result['status'] == 'AVAILABLE'
    assert result['prices'] == [{'date': '2026-09-04', 'adjusted_close': '100'},
                                {'date': '2026-09-08', 'adjusted_close': '102'}]
    assert result['coverage']['history_session_coverage'] == 'UNVERIFIED'
    assert result['coverage']['observed_adjusted_prices_complete'] is True
    issue = next(i for i in result['issues'] if i['code'] == 'UNVERIFIED_HISTORY_SESSION_COVERAGE')
    assert issue['blocks_calculation'] is False
    assert not any('missing sessions' in warning.lower() for warning in result['warnings'])
    assert result['usable_period'] == {'start': '2026-09-04', 'end': '2026-09-08'}
    assert result['data_environment'] == 'SYNTHETIC'


def test_consecutive_weekdays_do_not_certify_full_exchange_session_coverage(ledger, tmp_path):
    # Given provider observations even when weekday dates are consecutive.
    result = history(ledger, tmp_path, [{'date': '2026-09-08', 'adjClose': '102'},
                                      {'date': '2026-09-09', 'adjClose': '103'}])
    # Then provider-observed coverage is distinct from verified session coverage.
    assert result['status'] == 'AVAILABLE'
    assert result['coverage']['history_session_coverage'] == 'UNVERIFIED'
    assert result['coverage']['observed_adjusted_prices_complete'] is True
    assert any(i['code'] == 'UNVERIFIED_HISTORY_SESSION_COVERAGE' for i in result['issues'])


def test_unadjusted_prices_cannot_establish_total_return(ledger, tmp_path):
    # Given only unadjusted provider closes, when history is normalized.
    result = history(ledger, tmp_path, [{'date': '2026-09-08', 'close': '102'}])
    # Then adjusted-return evidence remains unavailable and blocking.
    assert result['status'] == 'UNAVAILABLE'
    assert result['prices'] == []
    assert result['usable_period'] is None
    assert any(i['code'] == 'MISSING_DIVIDEND_ADJUSTED_PRICE' and i['blocks_calculation']
               for i in result['issues'])


def test_pinned_backtest_calendar_still_blocks_an_actual_missing_observation(ledger):
    # Given an explicit synthetic three-session calendar and a missing middle price.
    sid = ledger.register_security({'ticker': 'FAKE', 'name': 'Fictional security',
        'asset_type': 'STOCK', 'currency': 'USD', 'source': 'Reviewed synthetic fixture'})['id']
    before = ledger.state()
    manifest = {'id': 'synthetic-session-fixture', 'data_environment': 'SYNTHETIC',
        'sessions': ['2026-09-08', '2026-09-09', '2026-09-10'],
        'series': {sid: [{'date': '2026-09-08', 'total_return_index': '100'},
                         {'date': '2026-09-10', 'total_return_index': '103'}]}}
    # When that calendar is used for a historical simulation.
    result = run(ledger, portfolio={sid: '1'}, start='2026-09-08', end='2026-09-10',
        policy={'starting_value': '1000', 'fee_per_trade': '0', 'contribution_schedule': [],
                'rebalance_frequency': 'BUY_AND_HOLD'}, manifest=manifest)
    # Then the missing pinned session prevents a financial result and leaves facts untouched.
    assert result['status'] == 'UNAVAILABLE'
    assert any(i['code'] == 'MISSING_HISTORY' and i['blocks_calculation'] for i in result['issues'])
    assert result['total_return'] is None
    assert ledger.state() == before


@pytest.mark.parametrize('rows', [
    [{'date': 'invalid', 'adjClose': '100'}],
    [{'date': '2026-09-08', 'adjClose': '100'}, {'date': '2026-09-08', 'adjClose': '101'}],
])
def test_invalid_or_duplicate_observation_dates_remain_external_errors(ledger, tmp_path, rows):
    with pytest.raises(DomainError) as error:
        history(ledger, tmp_path, rows)
    assert error.value.code == 2


def test_nonpositive_adjusted_observations_remain_unavailable(ledger, tmp_path):
    result = history(ledger, tmp_path, [{'date': '2026-09-08', 'adjClose': '0'}])
    assert result['status'] == 'UNAVAILABLE'
    assert result['prices'] == []
    assert any(i['blocks_calculation'] for i in result['issues'])


def test_invalid_adjusted_price_blocks_even_with_usable_provider_observations(ledger, tmp_path):
    # Given a positive adjusted observation followed by a nonpositive adjusted price.
    result = history(ledger, tmp_path, [{'date': '2026-09-08', 'adjClose': '100'},
                                      {'date': '2026-09-09', 'adjClose': '0'}])
    # Then retained observations never disguise invalid adjusted-return evidence as usable coverage.
    assert result['prices'] == [{'date': '2026-09-08', 'adjusted_close': '100'}]
    assert result['status'] == 'PARTIAL'
    assert result['coverage']['observed_adjusted_prices_complete'] is False
    assert any(i['code'] == 'INVALID_ADJUSTED_PRICE' and i['blocks_calculation']
               for i in result['issues'])
