"""Observable exposure contracts with independently calculated synthetic amounts."""

import copy

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from invest.lookthrough import exposure, research_universe

scenarios('features/mvp/exposure_consistency.feature')


@pytest.fixture
def context():
    return {}


def observation(holdings, **overrides):
    return dict({'as_of': '2026-10-01', 'published_at': '2026-10-02',
                 'source_id': 'fictional-reviewed-source', 'data_environment': 'SYNTHETIC',
                 'holdings': holdings}, **overrides)


@given(parsers.parse('synthetic household exposure evidence for "{case}"'))
def evidence(context, case):
    state = {'accounts': [{'id': 'ira', 'currency': 'USD', 'data_environment': 'SYNTHETIC'}],
             'securities': [{'id': 'fund-a', 'asset_type': 'ETF'},
                            {'id': 'fund-b', 'asset_type': 'ETF'},
                            {'id': 'verified', 'asset_type': 'STOCK', 'ticker': 'SAME',
                             'issuer_id': 'CIK:0000123456',
                             'issuer_identity_evidence': 'Reviewed fictional issuer'}],
             'positions': [{'account_id': 'ira', 'security_id': 'fund-a',
                            'market_value': '1000'}], 'cash_balances': []}
    observed = {'identifier': 'source-only-001', 'ticker': 'SAME',
                'name': 'Fictional observed company', 'asset_type': 'STOCK', 'weight': '0.6'}
    observations = {'fund-a': observation([observed])}
    if case == 'verified nested issuer':
        observations = {'fund-a': observation([{'security_id': 'verified', 'weight': '0.5'},
                                              {'security_id': 'fund-b', 'weight': '0.5'}]),
                        'fund-b': observation([{'security_id': 'verified', 'weight': '1'}])}
    elif case == 'equal source tickers':
        state['positions'].append({'account_id': 'ira', 'security_id': 'fund-b',
                                   'market_value': '1000'})
        observations['fund-a']['holdings'][0]['weight'] = '1'
        observations['fund-b'] = observation([dict(observed, weight='1')],
                                             source_id='second-fictional-source')
    elif case in {'stale holdings', 'later publication', 'invalid weights', 'exact residues'}:
        observations['fund-a']['holdings'] = [{'security_id': 'verified', 'weight': '1'}]
        if case == 'stale holdings':
            observations['fund-a']['as_of'] = '2025-01-01'
        elif case == 'later publication':
            observations['fund-a']['published_at'] = '2026-10-11'
        elif case == 'invalid weights':
            observations['fund-a']['holdings'][0]['weight'] = '1.01'
        else:
            observations['fund-a']['holdings'][0]['weight'] = '0.333333333333333333333333333333'
    elif case == 'absent holdings':
        observations = {}
    elif case == 'missing mark':
        state['positions'][0]['market_value'] = None
        state['cash_balances'] = [{'account_id': 'ira', 'amount': '100'}]
    elif case == 'cycle':
        observations['fund-a']['holdings'] = [{'security_id': 'fund-a', 'weight': '1'}]
    elif case == 'depth limit':
        observations['fund-a']['holdings'] = [{'security_id': 'fund-b', 'weight': '1'}]
        observations['fund-b'] = observation([{'security_id': 'verified', 'weight': '1'}])
    elif case == 'research selection':
        observations['fund-a']['holdings'].append({'security_id': 'verified', 'weight': '0.4'})
    context.update(state=state, observations=observations, case=case)
    context['before'] = copy.deepcopy((state, observations))


@when('household exposure is calculated without changing its evidence')
def calculate(context):
    context['result'] = exposure(context['state'], context['observations'], as_of='2026-10-10',
                                 max_depth=1 if context['case'] == 'depth limit' else 8)


@then(parsers.parse('exposure satisfies "{case}" coverage and identity rules'))
def coverage(context, case):
    result = context['result']
    assert (context['state'], context['observations']) == context['before']
    assert result['known_value_subtotal'] == ('100' if case == 'missing mark' else
                                            '2000' if case == 'equal source tickers' else '1000')
    codes = {issue['code'] for issue in result['issues']}
    if case == 'observed partial':
        assert result['exposures'][0]['total_value'] == '600'
        assert result['exposures'][0]['ticker'] == 'SAME'
        assert result['unknown_exposure_value'] == '400'
        assert result['unresolved_identity_value'] == '600'
        assert result['exposures'][0]['contributions'][0]['path'][1]['security_id'] == 'fund-a'
    elif case == 'verified nested issuer':
        assert len(result['exposures']) == 1
        assert result['exposures'][0]['total_value'] == '1000'
        assert result['exposures'][0]['issuer_id'] == 'CIK:0000123456'
        assert len(result['exposures'][0]['contributions']) == 2
        assert result['complete'] is True
    elif case == 'equal source tickers':
        assert len(result['exposures']) == 2
        assert all(row['issuer_id'] is None for row in result['exposures'])
        assert result['unresolved_identity_value'] == '2000'
        assert result['unknown_exposure_value'] == '0'
    elif case == 'missing mark':
        assert result['total_value'] is None
        assert result['unknown_exposure_percentage'] is None
        assert all(row['percentage'] is None for row in result['exposures'])
        assert 'MISSING_VALUATION_MARK' in codes
    elif case == 'exact residues':
        assert result['exposures'][0]['total_value'] == '333.333333333333333333333333333'
        assert result['unknown_exposure_value'] == '666.666666666666666666666666667'
    else:
        expected = {'stale holdings': 'STALE_HOLDINGS', 'later publication': 'FUTURE_PUBLICATION',
                    'absent holdings': 'UNKNOWN_HOLDINGS', 'invalid weights': 'INVALID_HOLDINGS_WEIGHTS',
                    'cycle': 'FUND_CYCLE', 'depth limit': 'MAX_LOOKTHROUGH_DEPTH'}[case]
        assert expected in codes
        assert result['unknown_exposure_value'] == '1000'
        assert result['exposures'] == []
    assert result['numeric_complete'] is (case in {'verified nested issuer', 'equal source tickers'})
    assert result['evidence_complete'] is (case == 'verified nested issuer')


@when('the verified issuer research universe is selected')
def select(context):
    context['result'] = research_universe(context['state'], context['observations'],
                                         as_of='2026-10-10', min_exposure='0')


@then('verified company selection preserves observed unresolved amounts')
def selected(context):
    result = context['result']
    assert [row['issuer_id'] for row in result['companies']] == ['CIK:0000123456']
    assert result['companies'][0]['total_value'] == '400'
    assert result['unresolved_identity_value'] == '600'
    assert result['unknown_exposure_value'] == '0'
    assert result['filtered_exposure_value'] == '0'
    assert (context['state'], context['observations']) == context['before']
