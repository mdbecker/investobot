"""Observable policy approval and dated tax evidence regressions from the October review."""

import copy

import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from test_prd_harvest_proposals import household as reviewed_household

from invest.models import DomainError
from invest.planning import get_policy, propose, save_policy
from invest.targets import save
from invest.tax import harvest_plan

household = reviewed_household

scenarios('features/mvp/review_policy_contracts.feature')


@given('a reviewed fictional household with a confirmed September gain', target_fixture='review')
def review(household):
    return household


@when(parsers.parse('the {path} proposal uses {evidence} tax evidence'))
def evaluate(review, path, evidence):
    policy = review['policy']
    if path == 'rebalance':
        policy['cash_floors']['tax'] = '100'
    budget = policy['annual_tax_budget']
    if evidence == 'wrong-year':
        budget['year'] = 2027
    elif evidence == 'stale':
        budget['as_of'] = '2026-09-01T00:00:00Z'
    elif evidence == 'future':
        budget['as_of'] = '2026-10-11T00:00:00Z'
    elif evidence == 'mixed-environment':
        budget['data_environment'] = 'REAL'
    save_policy(review['ledger'], policy, confirm=True)
    approved = get_policy(review['ledger'], policy['id'])
    review['before'] = copy.deepcopy(review['ledger'].state())
    if path == 'harvest':
        result = harvest_plan(review['ledger'].state(), approved, '2026-10-10')
        review['budget'] = result['annual_tax_budget']
    else:
        target = save(review['ledger'], {
            'name': 'Reviewed replacement allocation',
            'target_allocations': {review['replacement']: '1'},
            'planning_constraints': {'eligible_accounts': ['tax']}})
        review['before'] = copy.deepcopy(review['ledger'].state())
        result = propose(review['ledger'], target['id'], policy=policy['id'], mode='rebalance',
                         as_of='2026-10-10', prices=policy['harvest_review']['price_observations'])
        review['budget'] = result['tax_budget']
    review['result'] = result


@then(parsers.parse('taxable sales are blocked by {code} while accepted facts remain intact'))
def blocked(review, code):
    result, budget = review['result'], review['budget']
    assert code in {issue['code'] for issue in budget['issues']}
    assert budget['remaining_allowance'] is None
    assert not any(action['type'] == 'SELL' for action in result['proposed_actions'])
    if result.get('mode') == 'rebalance':
        assert any(action['type'] == 'BUY' for action in result['proposed_actions'])
    assert review['ledger'].state() == review['before']
    assert any(row['activity_id'] == 'fictional-prior-gain' for row in review['before']['activities'])


@then('the matching evidence retains eight dollars of consumption and permits a sale')
def matching(review):
    assert review['budget']['year_to_date_consumption'] == '8'
    assert review['budget']['remaining_allowance'] == '2'
    assert any(action['type'] == 'SELL' for action in review['result']['proposed_actions'])


@pytest.mark.parametrize('missing', ['can_buy', 'can_sell', 'can_hold'])
def test_approval_requires_each_explicit_permission(household, missing):
    policy = household['policy']
    del policy['permissions']['tax'][household['replacement']][missing]
    with pytest.raises(DomainError, match='booleans'):
        save_policy(household['ledger'], policy, confirm=True)
    assert household['ledger'].connection.execute('SELECT count(*) FROM trading_policy_versions').fetchone()[0] == 0


def test_approval_rejects_buy_allowed_hold_forbidden(household):
    household['policy']['permissions']['tax'][household['replacement']]['can_hold'] = False
    with pytest.raises(DomainError, match='hold'):
        save_policy(household['ledger'], household['policy'], confirm=True)


def test_restricted_inventory_stays_visible_without_forced_liquidation(household):
    ledger, policy = household['ledger'], household['policy']
    policy['permissions']['tax'][household['loss']].update(can_buy=False, can_sell=False, can_hold=False)
    save_policy(ledger, policy, confirm=True)
    target = save(ledger, {'name': 'Keep observed weights', 'target_allocations': {household['loss']: '1'},
                           'planning_constraints': {'eligible_accounts': ['tax']}})
    before = copy.deepcopy(ledger.state())
    result = propose(ledger, target['id'], policy=policy['id'], mode='rebalance', as_of='2026-10-10',
                     prices=policy['harvest_review']['price_observations'])
    assert 'RESTRICTED_HOLDING' in {issue['code'] for issue in result['issues']}
    assert not any(action['security'] == household['loss'] for action in result['proposed_actions'])
    assert ledger.state() == before
