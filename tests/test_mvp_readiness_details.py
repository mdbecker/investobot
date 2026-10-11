"""Readiness inspects independent accepted coverage, not merely present rows."""

import copy

import pytest

from invest.ledger import Ledger
from invest.readiness import check


@pytest.fixture
def ledger(tmp_path):
    instance = Ledger(tmp_path / 'fictional-readiness.db')
    yield instance
    instance.connection.close()


def observation(*, date='2026-10-09', positions_complete=True, lots_complete=True,
                holding=False):
    payload = {
        'account': {'id': 'fictional', 'name': 'Fictional readiness account',
                    'tax_status': 'TAXABLE', 'history_complete': True},
        'positions': [], 'lots': [], 'cash': '100', 'cash_known': True,
        'positions_complete': positions_complete, 'lots_complete': lots_complete,
        'source_timestamp': date, 'source_hash': f'fictional:{date}:{holding}',
        'imported_at': '2026-10-10T12:00:00Z', 'data_environment': 'SYNTHETIC',
    }
    if holding:
        payload['positions'] = [{
            'security': 'FICTIONAL', 'name': 'Fictional stock', 'asset_type': 'STOCK',
            'quantity': '1', 'price': '100', 'market_value': '100', 'cost_basis': '90',
            'displayed_price_precision': 2, 'displayed_market_value_precision': 2,
        }]
        payload['lots'] = [{
            'id': 'fictional-lot', 'security': 'FICTIONAL',
            'acquisition_date': '2025-01-01', 'quantity': '1', 'remaining_quantity': '1',
            'cost_basis': '90', 'remaining_adjusted_basis': '90',
            'source_lot_id': 'fictional-lot', 'identity_status': 'VERIFIED',
            'identity_source': 'Reviewed fictional broker lot record',
        }]
    return payload


def preflight(ledger, *, as_of='2026-10-10'):
    before = copy.deepcopy(ledger.state())
    result = check(ledger.planning_state(), as_of=as_of)
    assert ledger.state() == before, 'Readiness must not update accepted facts or observations'
    assert result['proposals_allowed'] is False
    assert result['execution_review_allowed'] is False
    return result


def require_issue(result, code):
    issues = [issue for issue in result['issues'] if issue['code'] == code]
    assert issues, f'Missing typed {code}: {result}'
    assert result['status'] != 'AVAILABLE'
    assert result['next_human_actions']
    assert all(isinstance(issue['blocks_proposals'], bool) for issue in issues)
    assert all(isinstance(issue['blocks_calculation'], bool) for issue in issues)


def test_partial_empty_positions_do_not_establish_complete_inventory(ledger):
    ledger.apply(observation(positions_complete=False))
    assert ledger.rows('positions') == []
    require_issue(preflight(ledger), 'INCOMPLETE_POSITION_COVERAGE')


def test_matched_observed_lot_does_not_establish_complete_lot_history(ledger):
    ledger.apply(observation(lots_complete=False, holding=True))
    assert ledger.rows('positions')[0]['lot_state'] == 'RESOLVED'
    require_issue(preflight(ledger), 'UNKNOWN_LOT_COVERAGE')


def test_unknown_cash_source_date_is_not_freshened_by_import_time(ledger):
    ledger.apply(observation(date=None), allow_older=True,
                 justification='Human reviewed fictional undated page; source date remains unknown')
    cash = ledger.rows('cash_balances')[0]
    assert cash['amount'] == '100'
    assert cash['as_of'] is None
    require_issue(preflight(ledger), 'UNKNOWN_CASH_FRESHNESS')


def test_future_cash_observation_cannot_support_historical_readiness(ledger):
    ledger.apply(observation(date='2026-10-11'))
    require_issue(preflight(ledger), 'FUTURE_CASH_OBSERVATION')


def test_future_empty_inventory_still_has_observation_chronology(ledger):
    ledger.apply(observation(date='2026-10-11'))
    require_issue(preflight(ledger), 'FUTURE_POSITION_OBSERVATION')


def test_explicit_complete_empty_inventory_is_distinct_from_unknown_inventory(ledger):
    ledger.apply(observation())
    result = preflight(ledger)
    assert result['status'] == 'AVAILABLE'
    assert result['calculation_allowed'] is True
    assert result['issues'] == []
