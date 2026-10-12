"""Dense conventional contributions have one independently known zero-rate root."""

from datetime import date, timedelta

import pytest

from invest.performance import calculate


@pytest.mark.parametrize('count', [480, 1920])
def test_dense_complete_contributions_keep_all_flows_and_resolve_unique_zero_xirr(count):
    first, last = date(2016, 10, 10), date(2026, 10, 10)
    checkpoints = [{'date': first.isoformat(), 'value': '1000', 'complete': True}]
    flows = []
    for index in range(1, count + 1):
        day = first + timedelta(days=(last - first).days * index // count)
        checkpoints.append({'date': day.isoformat(), 'value': str(1000 + index * 100),
                            'complete': True, 'timing': 'AFTER_FLOW'})
        flows.append({'date': day.isoformat(), 'amount': '100', 'classification': 'EXTERNAL'})
    result = calculate({'from_date': str(first), 'to_date': str(last), 'scope': 'HOUSEHOLD',
        'data_environment': 'SYNTHETIC', 'cash_flow_history_complete': True,
        'checkpoints': checkpoints, 'cash_flows': flows, 'fee_method': 'NET_OF_FEES'})
    # Every contribution is retained in the terminal value; one sign change makes
    # the root unique, and the undiscounted investor cash movements sum to zero.
    assert result['status'] == 'AVAILABLE', result['issues']
    assert result['twr']['return'] == '0'
    assert result['xirr']['status'] == 'AVAILABLE'
    assert abs(result['xirr']['return']) < 1e-12


def test_dense_nonconventional_flows_keep_explicit_complexity_review():
    flows = [{'date': (date(2026, 1, 1) + timedelta(days=index)).isoformat(),
              'amount': '100' if index % 2 else '-100'} for index in range(129)]
    result = calculate({'from_date': '2026-01-01', 'to_date': '2026-10-10',
        'scope': 'HOUSEHOLD', 'data_environment': 'SYNTHETIC',
        'cash_flow_history_complete': True, 'cash_flows': [],
        'investor_cash_flows': flows, 'checkpoints': [
            {'date': '2026-01-01', 'value': '1000', 'complete': True},
            {'date': '2026-10-10', 'value': '1000', 'complete': True}]})
    assert result['xirr']['status'] == 'UNAVAILABLE'
    assert 'XIRR_UNAVAILABLE_COMPLEXITY' in {row['code'] for row in result['issues']}
