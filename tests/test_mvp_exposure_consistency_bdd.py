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
                            'market_value': '1000'}],
             'cash_balances': [{'account_id': 'ira', 'amount': '0'}]}
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
    elif case in {'missing cash', 'accepted parser issue', 'source diagnostic',
                  'provisional issuer', 'conflicting issuer', 'later observed evidence'}:
        observations['fund-a']['holdings'] = [{'security_id': 'verified', 'weight': '1'}]
        if case == 'missing cash':
            state['cash_balances'] = []
        elif case == 'accepted parser issue':
            state['snapshots'] = [{'account': {'id': 'ira'}, 'positions_complete': True,
                'cash_known': True, 'issues': [{'code': 'PROVISIONAL_ADAPTER',
                    'message': 'Fictional adapter awaits reviewed originals',
                    'blocks_acceptance': False, 'blocks_calculation': False,
                    'blocks_proposals': True, 'blocks_execution_review': True}]}]
        elif case == 'source diagnostic':
            observations['fund-a']['issues'] = [{'code': 'SOURCE_PERMISSION_UNKNOWN',
                'message': 'Original-source reuse has not been reviewed', 'severity': 'WARNING',
                'blocks_acceptance': False, 'blocks_calculation': False,
                'blocks_proposals': True, 'blocks_execution_review': True}]
        elif case == 'provisional issuer':
            observations['fund-a']['provisional'] = True
        elif case == 'conflicting issuer':
            observations['fund-a']['holdings'][0].update(issuer_id='different-issuer',
                                                        issuer_verified=True)
        else:
            observations['fund-a']['observed_at'] = '2026-10-11'
    context.update(state=state, observations=observations, case=case)
    context['before'] = copy.deepcopy((state, observations))


@when('household exposure is calculated without changing its evidence')
def calculate(context):
    context['result'] = exposure(context['state'], context['observations'], as_of='2026-10-10',
                                 max_depth=1 if context['case'] == 'depth limit' else 8)


@then('600 dollars is attributed to the observed company and 400 dollars remains unknown')
def partial_disclosure(context):
    result = context['result']
    assert (context['state'], context['observations']) == context['before']
    assert result['known_value_subtotal'] == '1000'
    assert result['exposures'][0]['total_value'] == '600'
    assert result['exposures'][0]['ticker'] == 'SAME'
    assert result['unknown_exposure_value'] == '400'
    assert result['unresolved_identity_value'] == '600'
    assert result['exposures'][0]['contributions'][0]['path'][1]['security_id'] == 'fund-a'
    assert result['numeric_complete'] is False
    assert result['evidence_complete'] is False


@then('one verified issuer has 1000 dollars across two contribution paths')
def combined_issuer(context):
    result = context['result']
    assert (context['state'], context['observations']) == context['before']
    assert result['known_value_subtotal'] == '1000'
    assert len([row for row in result['exposures'] if row['asset_type'] != 'CASH']) == 1
    assert result['exposures'][0]['total_value'] == '1000'
    assert result['exposures'][0]['issuer_id'] == 'CIK:0000123456'
    assert len(result['exposures'][0]['contributions']) == 2
    assert result['complete'] is True
    assert result['numeric_complete'] is True
    assert result['evidence_complete'] is True


@then('two separate observations retain 2000 dollars of unresolved issuer identity')
def separate_tickers(context):
    result = context['result']
    assert (context['state'], context['observations']) == context['before']
    assert result['known_value_subtotal'] == '2000'
    assert len([row for row in result['exposures'] if row['asset_type'] != 'CASH']) == 2
    assert all(row['issuer_id'] is None for row in result['exposures'])
    assert result['unresolved_identity_value'] == '2000'
    assert result['unknown_exposure_value'] == '0'
    assert result['numeric_complete'] is True
    assert result['evidence_complete'] is False


@then('the known 1000 dollar subtotal has no household total or percentages')
def incomplete_cash(context):
    result = context['result']
    assert (context['state'], context['observations']) == context['before']
    assert 'UNKNOWN_CASH_COVERAGE' in {row['code'] for row in result['issues']}
    assert result['total_value'] is None
    assert result['known_value_subtotal'] == '1000'
    assert all(row['percentage'] is None for row in result['exposures'])
    assert result['evidence_complete'] is False


@then(parsers.parse('exposure satisfies "{case}" coverage and identity rules'))
def coverage(context, case):
    result = context['result']
    assert (context['state'], context['observations']) == context['before']
    assert result['known_value_subtotal'] == ('100' if case == 'missing mark' else '1000')
    codes = {issue['code'] for issue in result['issues']}
    if case == 'missing mark':
        assert result['total_value'] is None
        assert result['unknown_exposure_percentage'] is None
        assert all(row['percentage'] is None for row in result['exposures'])
        assert 'MISSING_VALUATION_MARK' in codes
    elif case == 'exact residues':
        assert result['exposures'][0]['total_value'] == '333.333333333333333333333333333'
        assert result['unknown_exposure_value'] == '666.666666666666666666666666667'
    elif case == 'stale holdings':
        assert 'STALE_HOLDINGS' in codes
        assert result['exposures'][0]['total_value'] == '1000'
        assert result['stale_exposure_value'] == '1000'
        assert result['unknown_exposure_value'] == '0'
    else:
        expected = {'stale holdings': 'STALE_HOLDINGS', 'later publication': 'FUTURE_PUBLICATION',
                    'absent holdings': 'UNKNOWN_HOLDINGS', 'invalid weights': 'INVALID_HOLDINGS_WEIGHTS',
                    'cycle': 'FUND_CYCLE', 'depth limit': 'MAX_LOOKTHROUGH_DEPTH'}[case]
        assert expected in codes
        assert result['unknown_exposure_value'] == '1000'
        assert all(row['total_value'] == '0' for row in result['exposures'])
    assert result['numeric_complete'] is (case == 'stale holdings')
    assert result['evidence_complete'] is False


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


@then(parsers.parse('source uncertainty is preserved for "{case}"'))
def uncertainty(context, case):
    result = context['result']
    assert (context['state'], context['observations']) == context['before']
    codes = {row['code'] for row in result['issues']}
    if case == 'accepted parser issue':
        assert 'PROVISIONAL_ADAPTER' in codes
    elif case == 'source diagnostic':
        issue = next(row for row in result['issues'] if row['code'] == 'SOURCE_PERMISSION_UNKNOWN')
        assert issue['message'] == 'Original-source reuse has not been reviewed'
        assert issue['severity'] == 'WARNING'
        assert issue['blocks_acceptance'] is False
    elif case == 'provisional issuer':
        assert all(row['issuer_id'] is None for row in result['exposures'])
        assert result['unresolved_identity_value'] == '1000'
    elif case == 'conflicting issuer':
        assert 'ISSUER_IDENTITY_CONFLICT' in codes
        assert all(row['issuer_id'] != 'different-issuer' for row in result['exposures'])
    else:
        assert 'FUTURE_OBSERVATION' in codes
        assert result['unknown_exposure_value'] == '1000'
    assert result['evidence_complete'] is False
