"""Unsupported instrument terms cannot become plain bonds by omitting a type label."""

import copy

import pytest

from invest.bonds import analyze


def plain_terms():
    return {'face_value': '1000', 'coupon': '0.05', 'clean_price': '98',
            'issue_date': '2021-01-15', 'settlement_date': '2026-10-08',
            'maturity': '2031-01-15', 'frequency': 2, 'day_count': 'ACTUAL_ACTUAL_BOND'}


@pytest.mark.parametrize('structure', [
    {'call_schedule': [{'date': '2028-01-15', 'price': '100'}]},
    {'conversion_ratio': '20', 'conversion_security': 'FICTIONAL-EQUITY'},
    {'structured_payoff': {'type': 'INDEX_LINKED', 'underlying': 'FICTIONAL-INDEX'}},
], ids=['callable_terms', 'convertible_terms', 'structured_terms'])
def test_unsupported_structural_terms_without_instrument_label_are_unavailable(structure):
    terms = dict(plain_terms(), **structure)
    before = copy.deepcopy(terms)
    assert 'instrument_type' not in terms
    result = analyze(terms)
    assert terms == before
    assert result['status'] == 'UNAVAILABLE'
    assert 'UNSUPPORTED_BOND_STRUCTURE' in {issue['code'] for issue in result['issues']}
    for metric in ['yield_to_maturity', 'yield_to_worst', 'call_yields', 'modified_duration', 'convexity']:
        assert metric not in result, 'Unsupported optionality cannot be priced as fixed cash flows'


def test_plain_fixed_coupon_control_remains_calculable():
    result = analyze(plain_terms())
    assert result['status'] == 'CALCULATED'
    assert float(result['yield_to_maturity']) > .05
    assert float(result['modified_duration']) > 0
