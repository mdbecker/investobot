"""Given sourced synthetic holdings, report numerical and evidence coverage separately."""

import copy

import pytest

from invest.lookthrough import exposure, research_universe


@pytest.fixture
def sourced_nested_holdings():
    state = {
        'accounts': [{'id': 'ira', 'currency': 'USD', 'data_environment': 'SYNTHETIC'}],
        'securities': [{'id': 'outer', 'asset_type': 'ETF'},
                       {'id': 'inner', 'asset_type': 'MUTUAL_FUND'},
                       {'id': 'company', 'asset_type': 'STOCK', 'issuer_id': 'fictional-issuer',
                        'issuer_identity_evidence': 'Reviewed fictional issuer source'}],
        'positions': [{'account_id': 'ira', 'security_id': 'outer', 'market_value': '1000',
                       'as_of': '2026-10-01'}],
        'cash_balances': [{'account_id': 'ira', 'amount': '0'}],
    }
    observations = {
        'outer': {'as_of': '2026-10-01', 'source_id': 'fictional-outer-source',
                  'source_hash': 'fictional-immutable-hash', 'data_environment': 'SYNTHETIC',
                  'holdings': [{'security_id': 'inner', 'weight': '1'}]},
        'inner': {'as_of': '2026-10-01', 'source_id': 'fictional-provider-record',
                  'data_environment': 'SYNTHETIC',
                  'holdings': [{'security_id': 'company', 'weight': '1'}]},
    }
    return state, observations


@pytest.mark.parametrize(('field', 'code'), [
    ('data_environment', 'UNKNOWN_DATA_ENVIRONMENT'),
    ('source_id', 'UNKNOWN_HOLDINGS_SOURCE'),
    ('as_of', 'UNKNOWN_HOLDINGS_DATE'),
])
def test_full_weights_without_evidence_keep_values_but_require_review(
        sourced_nested_holdings, field, code):
    # Given full numerical weights with one missing provenance fact.
    state, observations = sourced_nested_holdings
    observations['inner'].pop(field)
    before = copy.deepcopy((state, observations))
    # When direct exposure is calculated.
    result = exposure(state, observations, as_of='2026-10-10')
    # Then known values survive, while verified completeness and proposals are blocked.
    assert result['exposures'][0]['total_value'] == '1000'
    assert result['unknown_exposure_value'] == '0'
    assert result['complete'] is False
    assert result['status'] == 'PARTIAL'
    issue = next(issue for issue in result['issues'] if issue['code'] == code)
    assert issue['blocks_proposals'] and issue['blocks_execution_review']
    assert issue['blocks_calculation'] is False
    assert (state, observations) == before


def test_matching_sourced_nested_paths_preserve_provider_and_artifact_evidence(
        sourced_nested_holdings):
    state, observations = sourced_nested_holdings
    result = exposure(state, observations, as_of='2026-10-10')
    assert result['complete'] is True
    assert result['issues'] == []
    assert result['exposures'][0]['total_value'] == '1000'
    path = result['exposures'][0]['contributions'][0]['path']
    assert [row.get('security_id') for row in path] == [None, 'outer', 'inner']
    assert path[1]['source_hash'] == 'fictional-immutable-hash'
    assert path[2]['source_id'] == 'fictional-provider-record'
    assert path[2]['source_hash'] is None
    universe = research_universe(state, observations, as_of='2026-10-10')
    assert universe['complete'] is True
    assert universe['companies'][0]['total_value'] == '1000'


def test_unknown_constituents_are_not_redistributed(sourced_nested_holdings):
    state, observations = sourced_nested_holdings
    observations['inner']['holdings'][0]['weight'] = '0.6'
    result = exposure(state, observations, as_of='2026-10-10')
    assert result['exposures'][0]['total_value'] == '600'
    assert result['unknown_exposure_value'] == '400'
    assert result['complete'] is False
    assert 'PARTIAL_HOLDINGS' in {issue['code'] for issue in result['issues']}


def test_mismatched_nested_environment_blocks_actionable_research(sourced_nested_holdings):
    state, observations = sourced_nested_holdings
    observations['inner']['data_environment'] = 'REAL'
    result = research_universe(state, observations, as_of='2026-10-10')
    assert result['complete'] is False
    assert result['companies'] == []
    assert result['unknown_exposure_value'] == '1000'
    assert 'MIXED_DATA_ENVIRONMENT' in {issue['code'] for issue in result['issues']}
