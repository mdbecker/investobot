"""Unified MVP B31–B48: fixed fictional data, exact arithmetic and public domain behavior."""

import copy
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from invest.ledger import Ledger
from invest.models import DomainError
from invest.targets import save

scenarios('features/mvp/decisions.feature')


@pytest.fixture
def decision(tmp_path):
    return {'ledger': Ledger(tmp_path / 'decisions.db')}


@given(parsers.parse('a fictional SQLite household for decision {case}'))
def household(decision, case):
    ledger = decision['ledger']
    observed = ('2026-02-01' if case == 'B32' else '2026-03-01'
                if case in {'B33', 'B34', 'B38'} else '2026-10-01')
    quantity = '54' if case == 'B33' else '58' if case == 'B32' else '80'
    value = str(Decimal(quantity) * 100)
    cash = ('4600' if case == 'B33' else '4200' if case == 'B32'
            else '0' if case == 'B34' else '2000')
    ledger.apply({
        'account': {'id': 'ira', 'name': 'Fictional IRA', 'tax_status': 'TAX_FREE',
                    'currency': 'USD', 'history_complete': True},
        'positions': [{'security': 'WRAP', 'asset_type': 'ETF', 'quantity': quantity,
                       'price': '100', 'market_value': value, 'as_of': observed}],
        'lots': [{'id': 'fictional-wrap-lot', 'security': 'WRAP', 'quantity': quantity,
                  'remaining_quantity': quantity, 'cost_basis': str(Decimal(quantity) * 50),
                  'acquisition_date': '2024-01-01'}],
        'cash': cash, 'source_hash': 'fictional-decisions',
        'source_timestamp': observed,
        'data_environment': 'REAL' if case == 'B17' else 'SYNTHETIC',
        'positions_complete': True,
        'lots_complete': True})
    child = ledger.register_security({'ticker': 'CHILD', 'name': 'Fictional Child',
                                     'asset_type': 'ETF', 'currency': 'USD',
                                     'source': 'Fictional offline fixture'})
    stock = ledger.register_security({'ticker': 'COMP', 'name': 'Fictional Company',
                                     'asset_type': 'STOCK', 'currency': 'USD',
                                     'source': 'Fictional offline fixture'})
    decision.update(case=case, wrap=ledger.resolve('WRAP')['id'], child=child['id'],
                    stock=stock['id'], before=copy.deepcopy(ledger.state()))
    target = save(ledger, {
        'name': 'Fictional allocation',
        'target_allocations': {decision['wrap']: '0.5', decision['child']: '0.5'},
        'planning_constraints': {'eligible_accounts': ['ira'],
                                'permitted_securities': {'ira': [decision['child']]}}})
    decision['target'] = target['id']
    decision['policy'] = {
        'version': 'fictional-1', 'quarterly_months': [3, 6, 9, 12],
        'drift_trigger': '0.05', 'max_position_age_days': 120,
        'permissions': {'ira': {
            decision['wrap']: {'can_buy': False, 'can_sell': True, 'can_hold': True,
                               'share_increment': '1'},
            decision['child']: {'can_buy': True, 'can_sell': True, 'can_hold': True,
                                'share_increment': '0.001'}}}}
    decision['observations'] = {
        decision['wrap']: {'as_of': '2026-10-01', 'currency': 'USD', 'holdings': [
            {'security_id': decision['child'], 'weight': '0.5'}]},
        decision['child']: {'as_of': '2026-10-01', 'currency': 'USD', 'holdings': [
            {'security_id': decision['stock'], 'weight': '0.4',
             'issuer_id': 'CIK:0000123456', 'issuer_verified': True}]}}


@when('the pinned decision is evaluated')
def evaluate(decision):
    case = decision['case']
    if case <= 'B38':
        from invest.planning import propose

        as_of = '2026-10-10'
        mode = 'contributions-only'
        if case in {'B32', 'B33', 'B34', 'B38'}:
            mode = 'rebalance'
            as_of = '2026-02-10' if case == 'B32' else '2026-03-10'
        if case == 'B35':
            prices = {decision['wrap']: '100', decision['child']: '3001'}
        else:
            prices = {decision['wrap']: '100', decision['child']: '100'}
        if case == 'B36':
            del decision['policy']['permissions']['ira'][decision['child']]['share_increment']
            as_of = '2027-10-10'
        if case == 'B17':
            decision['policy']['baseline_environment'] = 'REAL'
            decision['policy']['price_environment'] = 'SYNTHETIC'
        if case == 'B31_UNKNOWN_FEE':
            decision['policy']['fee_per_trade'] = None
        if case == 'B31_UNCONFIRMED_CASH':
            decision['policy']['cash_confirmation'] = {'ira': False}
        if case == 'B31_UNKNOWN_POLICY':
            decision['policy']['permissions']['ira'][decision['child']]['can_buy'] = 'true'
        decision['result'] = propose(decision['ledger'], decision['target'],
                                     policy=decision['policy'], mode=mode, as_of=as_of,
                                     prices=prices)
        if case == 'B37':
            from invest.plan_storage import load_plan, summaries

            decision['saved_actions'] = copy.deepcopy(decision['result']['proposed_actions'])
            decision['ledger'].record_activity({
                'activity_id': 'fictional-deposit-2', 'account_id': 'ira',
                'type': 'CASH_DEPOSIT', 'date': '2026-10-11', 'amount': '100'}, yes=True)
            decision['loaded'] = load_plan(decision['ledger'], decision['result']['id'])
            decision['listed'] = summaries(decision['ledger'])
    elif case <= 'B44' or case == 'B47':
        from invest.lookthrough import exposure, research_universe

        observations = decision['observations']
        if case == 'B40':
            observations[decision['child']]['holdings'] = [
                {'security_id': decision['wrap'], 'weight': '1'}]
        if case == 'B41':
            observations[decision['wrap']]['holdings'] = [
                {'security_id': decision['stock'], 'weight': '0.65',
                 'issuer_id': 'CIK:0000123456', 'issuer_verified': True}]
        if case == 'B42':
            observations[decision['wrap']]['as_of'] = '2026-01-01'
        state = decision['ledger'].state()
        if case == 'B44':
            state['cash_balances'].append({'account_id': 'eur', 'currency': 'EUR',
                                          'amount': '100'})
        if case == 'B43':
            state['positions'].append({**state['positions'][0], 'account_id': 'second',
                                       'quantity': '10', 'market_value': '1000'})
        as_of = '2020-01-01' if case == 'B47' else '2026-10-10'
        try:
            decision['result'] = (research_universe(state, observations, as_of=as_of,
                                                    top=20, min_exposure='0')
                                  if case in {'B42', 'B43'} else
                                  exposure(state, observations, as_of=as_of))
        except DomainError as error:
            decision['error'] = error
    else:
        from invest.backtest import compare, run

        manifest = {'id': 'fictional-history-1', 'environment': 'SYNTHETIC',
                    'data_environment': 'SYNTHETIC', 'series': {security: [
                        {'date': '2020-01-02', 'total_return_index': '100'},
                        {'date': '2020-01-03', 'total_return_index': '110'},
                        {'date': '2020-01-06', 'total_return_index': '99'}]
                        for security in [decision['wrap'], decision['child']]}}
        first = run(decision['ledger'], portfolio='current', start='2020-01-02',
                    end='2020-01-06', policy=decision['policy'], manifest=manifest)
        decision['result'] = first
        if case in {'B45', 'B46'}:
            second_manifest = copy.deepcopy(manifest)
            if case == 'B46':
                second_manifest['series'][decision['child']].pop(0)
            second = run(decision['ledger'], portfolio={decision['wrap']: '0.5',
                                                       decision['child']: '0.5'},
                         start='2020-01-02', end='2020-01-06', policy=decision['policy'],
                         manifest=second_manifest)
            decision['comparison'] = compare(decision['ledger'], [first['id'], second['id']])


@then(parsers.parse('decision {case} satisfies its financial acceptance contract'))
def acceptance(decision, case):
    result = decision.get('result', {})
    actions = result.get('proposed_actions', [])
    if case == 'B17':
        assert result['status'] == 'BLOCKED'
        assert any(issue['code'] == 'MIXED_DATA_ENVIRONMENT' for issue in result['issues'])
        assert not actions
    elif case in {'B31_UNKNOWN_FEE', 'B31_UNCONFIRMED_CASH', 'B31_UNKNOWN_POLICY'}:
        expected = {'B31_UNKNOWN_FEE': 'UNKNOWN_EXECUTION_FEES',
                    'B31_UNCONFIRMED_CASH': 'UNCONFIRMED_CASH',
                    'B31_UNKNOWN_POLICY': 'INVALID_POLICY'}[case]
        assert result['status'] in {'BLOCKED', 'REVIEW_REQUIRED'}
        assert any(issue['code'] == expected for issue in result['issues'])
        if case == 'B31_UNKNOWN_FEE':
            assert result['status'] == 'REVIEW_REQUIRED'
            assert result['assumptions']['fee_per_trade'] is None
        else:
            assert not actions
    elif case in {'B31', 'B35'}:
        assert actions
        assert all(action['type'] == 'BUY' for action in actions)
        assert all(action['security'] == decision['child'] for action in actions)
        assert Decimal(result['cash_after']['ira']) >= 0
        if case == 'B35':
            quantity = Decimal(actions[0]['quantity'])
            assert quantity % Decimal('0.001') == 0
            assert 0 < quantity < 1
    elif case in {'B32', 'B33'}:
        assert not any(action['type'] == 'SELL' for action in actions)
        assert result['cadence']['eligible'] is False
    elif case == 'B34':
        assert any(action['type'] == 'SELL' and action['security'] == decision['wrap']
                   for action in actions)
    elif case == 'B36':
        assert result['status'] == 'BLOCKED'
        codes = {issue['code'] for issue in result['issues']}
        assert {'UNKNOWN_EXECUTION_PRECISION', 'STALE_POSITIONS'} <= codes
    elif case == 'B37':
        assert decision['loaded']['proposed_actions'] == decision['saved_actions']
        assert next(row for row in decision['listed'] if row['id'] == result['id'])['status'] == 'STALE'
    elif case == 'B38':
        from invest.simulations import simulate

        simulated = simulate(decision['before'], actions)
        assert simulated['after'] == result['simulation']['after']
        assert Decimal(result['simulation']['household_value_after']) == Decimal('10000')
    elif case == 'B39':
        issuer = next(row for row in result['exposures'] if row.get('issuer_id') == 'CIK:0000123456')
        assert Decimal(issuer['total_value']) == 1600
        assert len(issuer['contributions']) == 1
    elif case == 'B40':
        assert Decimal(result['unknown_exposure_value']) == 8000
        assert any(issue['code'] == 'FUND_CYCLE' for issue in result['issues'])
    elif case == 'B41':
        assert Decimal(result['unknown_exposure_value']) == 2800
        issuer = next(row for row in result['exposures'] if row.get('issuer_id') == 'CIK:0000123456')
        assert Decimal(issuer['total_value']) == 5200
    elif case == 'B42':
        assert result['complete'] is False
        assert Decimal(result['stale_exposure_value']) == 8000
    elif case == 'B43':
        assert len(result['companies']) == 1
        assert result['companies'][0]['issuer_id'] == 'CIK:0000123456'
        assert Decimal(result['companies'][0]['total_value']) == 1800
        assert Decimal(result['unknown_exposure_value']) == 7200
    elif case == 'B44':
        assert isinstance(decision.get('error'), DomainError)
        assert decision['error'].code == 3
    elif case == 'B45':
        assert decision['comparison']['status'] == 'COMPARABLE'
        assert decision['comparison']['start'] == '2020-01-02'
        assert decision['comparison']['end'] == '2020-01-06'
        assert decision['comparison']['assumptions']['cash_return'] == '0'
    elif case == 'B46':
        assert decision['comparison']['status'] == 'INCOMPARABLE'
        assert any(issue['code'] == 'MISSING_HISTORY' for issue in decision['comparison']['issues'])
    elif case == 'B47':
        assert Decimal(result['unknown_exposure_value']) == 8000
        assert any(issue['code'] == 'FUTURE_OBSERVATION' for issue in result['issues'])
    elif case == 'B48':
        assert result['mode'] == 'HYPOTHETICAL_CURRENT_ALLOCATION'
        assert result['assumptions']['cash_return'] == '0'
        assert result['assumptions']['modeled_taxes'] is False
        assert Decimal(result['total_return']) == Decimal('-0.01')
    if case != 'B37':
        assert decision['ledger'].state() == decision['before']
        assert decision['ledger'].rows('market_data_cache') == []


@when('the extended pinned decision is evaluated')
def extended_evaluate(decision):
    case = decision['case']
    ledger = decision['ledger']
    if case.startswith('P_'):
        from invest.planning import propose

        if case == 'P_CONFIRMED_CADENCE':
            ledger.record_activity({
                'activity_id': 'fictional-confirmed-buy', 'account_id': 'ira',
                'type': 'BUY', 'date': '2026-10-05', 'security': 'WRAP',
                'quantity': '1', 'price': '100'}, yes=True)
        if case == 'P_CASH_FLOOR':
            decision['policy']['cash_floors'] = {'ira': '1900'}
        if case == 'P_MINIMUM_NOTIONAL':
            decision['policy']['minimum_notional'] = '2500'
        if case == 'P_INDIVIDUAL_BOND':
            row = ledger.resolve('CHILD')
            row['asset_type'] = 'BOND'
            ledger.put('securities', row['id'], row)
        if case == 'P_LOSS_BUDGET':
            decision['policy']['annual_tax_budget'] = {
                'year': 2026, 'allowed_estimated_tax': '100',
                'confirmed_positive_tax_consumption': '100',
                'confirmed_realized_losses': '5000', 'coverage_complete': True,
                'short_term_rate': '0.3', 'long_term_rate': '0.15', 'currency': 'USD'}
        decision['before'] = copy.deepcopy(ledger.state())
        options = dict(policy=decision['policy'], mode='contributions-only',
                       as_of='2026-10-10',
                       prices={decision['wrap']: '100', decision['child']: '100'})
        decision['result'] = propose(ledger, decision['target'], **options)
        if case == 'P_UNCONFIRMED_CADENCE':
            decision['repeat'] = propose(ledger, decision['target'], **options)
    elif case.startswith('L_'):
        from invest.lookthrough import exposure, research_universe

        observations = decision['observations']
        if case == 'L_DEPTH_BOUND':
            previous = decision['wrap']
            for depth in range(9):
                security = ledger.register_security({
                    'ticker': f'LAYER{depth}', 'name': f'Fictional layer {depth}',
                    'asset_type': 'ETF', 'currency': 'USD', 'source': 'Fictional fixture'})
                observations[previous] = {
                    'as_of': '2026-10-01', 'currency': 'USD',
                    'holdings': [{'security_id': security['id'], 'weight': '1'}]}
                previous = security['id']
            observations[previous] = {
                'as_of': '2026-10-01', 'currency': 'USD', 'holdings': [
                    {'security_id': decision['stock'], 'weight': '1',
                     'issuer_id': 'CIK:0000123456', 'issuer_verified': True}]}
        if case == 'L_UNKNOWN_ISSUER':
            observations[decision['child']]['holdings'][0].update(
                issuer_verified=False, issuer_name='Fictional Company')
        if case == 'L_PUBLICATION_CUTOFF':
            observations[decision['wrap']]['published_at'] = '2026-10-11'
        if case == 'L_MINIMUM_TIES':
            observations[decision['wrap']]['holdings'] = [
                {'security_id': f'company-{issuer}', 'weight': weight,
                 'issuer_id': issuer, 'issuer_verified': True, 'asset_type': 'STOCK'}
                for issuer, weight in [('CIK:0000000002', '0.1'),
                                      ('CIK:0000000001', '0.1'),
                                      ('CIK:0000000003', '0.001')]]
        state = ledger.state()
        decision['before'] = copy.deepcopy(state)
        decision['result'] = (research_universe(state, observations, as_of='2026-10-10',
                                                top=20, min_exposure='0.01')
                              if case in {'L_UNKNOWN_ISSUER', 'L_MINIMUM_TIES'} else
                              exposure(state, observations, as_of='2026-10-10'))
    else:
        from invest.backtest import compare, run

        manifest = {'id': 'extended-history', 'data_environment': 'SYNTHETIC',
                    'sessions': ['2020-01-02', '2020-01-03', '2020-01-06'],
                    'series': {security: [
                        {'date': day, 'total_return_index': value}
                        for day, value in [('2020-01-02', '100'), ('2020-01-03', '110'),
                                           ('2020-01-06', '99')]]
                        for security in [decision['wrap'], decision['child']]}}
        if case == 'H_SESSION_GAP':
            manifest['series'][decision['wrap']].pop(1)
        policy = copy.deepcopy(decision['policy'])
        policy['fee_per_trade'] = '0'
        policy['contribution_schedule'] = []
        decision['result'] = run(ledger, portfolio='current', start='2020-01-02',
                                 end='2020-01-06', policy=policy, manifest=manifest)
        if case in {'H_FEE_MISMATCH', 'H_CASH_SCHEDULE_MISMATCH'}:
            if case == 'H_FEE_MISMATCH':
                policy['fee_per_trade'] = '1'
            else:
                policy['contribution_schedule'] = [{'date': '2020-01-03', 'amount': '100'}]
            other = run(ledger, portfolio='current', start='2020-01-02',
                        end='2020-01-06', policy=policy, manifest=manifest)
            decision['comparison'] = compare(ledger, [decision['result']['id'], other['id']])
        if case == 'H_PINNED_READ':
            manifest['series'][decision['wrap']][-1]['total_return_index'] = '999999'
            decision['comparison'] = compare(ledger, [decision['result']['id'],
                                                       decision['result']['id']])


@then(parsers.parse('extended decision {case} preserves its declared constraint'))
def extended_acceptance(decision, case):
    result = decision['result']
    actions = result.get('proposed_actions', [])
    if case == 'P_CONFIRMED_CADENCE':
        assert not actions
        assert any(issue['code'] == 'MONTHLY_CADENCE_USED' for issue in result['issues'])
    elif case == 'P_UNCONFIRMED_CADENCE':
        assert actions
        assert decision['repeat']['proposed_actions'] == actions
        assert decision['repeat']['cadence']['eligible'] is True
    elif case == 'P_CASH_FLOOR':
        assert actions
        assert Decimal(result['cash_after']['ira']) >= 1900
        assert sum(Decimal(action['quantity']) * Decimal(action['price'])
                   for action in actions) <= 100
    elif case == 'P_MINIMUM_NOTIONAL':
        assert not actions
        assert any(issue['code'] == 'BELOW_MINIMUM_NOTIONAL' for issue in result['issues'])
    elif case == 'P_INDIVIDUAL_BOND':
        assert not any(action['security'] == decision['child'] for action in actions)
        assert any(issue['code'] == 'INDIVIDUAL_BOND_REQUIRES_SCENARIO'
                   for issue in result['issues'])
    elif case == 'P_LOSS_BUDGET':
        assert Decimal(result['tax_budget']['remaining_headroom']) == 0
        assert not any(action['type'] == 'SELL' for action in actions)
    elif case == 'L_DEPTH_BOUND':
        assert Decimal(result['unknown_exposure_value']) == 8000
        assert any(issue['code'] == 'MAX_LOOKTHROUGH_DEPTH' for issue in result['issues'])
    elif case == 'L_UNKNOWN_ISSUER':
        assert result['companies'] == []
        assert Decimal(result['unresolved_issuer_value']) == 1600
    elif case == 'L_MINIMUM_TIES':
        assert [row['issuer_id'] for row in result['companies']] == [
            'CIK:0000000001', 'CIK:0000000002']
        assert all(Decimal(row['total_value']) == 800 for row in result['companies'])
        assert Decimal(result['unknown_exposure_value']) == Decimal('6392')
        assert Decimal(result['filtered_exposure_value']) == 8
    elif case == 'L_PUBLICATION_CUTOFF':
        assert Decimal(result['unknown_exposure_value']) == 8000
        assert any(issue['code'] == 'FUTURE_PUBLICATION' for issue in result['issues'])
    elif case == 'H_SESSION_GAP':
        assert result['status'] == 'UNAVAILABLE'
        assert result['total_return'] is None
        assert any(issue['code'] == 'MISSING_HISTORY' for issue in result['issues'])
    elif case in {'H_FEE_MISMATCH', 'H_CASH_SCHEDULE_MISMATCH'}:
        assert decision['comparison']['status'] == 'INCOMPARABLE'
        assert any(issue['code'] == 'ASSUMPTION_MISMATCH'
                   for issue in decision['comparison']['issues'])
    elif case == 'H_PINNED_READ':
        assert decision['comparison']['status'] == 'COMPARABLE'
        assert all(Decimal(row['total_return']) == Decimal('-0.01')
                   for row in decision['comparison']['runs'])
    assert decision['ledger'].state() == decision['before']
