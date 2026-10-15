"""Only observed retired target defaults may disappear from paired evidence."""

from copy import deepcopy

import pytest

from benchmarks.correctness_projection import project


def target():
    return {'target_allocations': {'security-1': '1'}, 'planning_constraints': {
        'eligible_accounts': ['tax'], 'excluded_positions': [], 'target_tolerance': '0.01'}}


def legacy_target():
    value = target()
    value['planning_constraints'].update(permitted_securities={}, cash_minimums={},
                                         trade_increments={}, price_max_age_days=1)
    return value


def test_observed_reference_target_defaults_compare_to_current_target_without_mutation():
    native = {'target': legacy_target(), 'policy': {'permissions': {'tax': {
        'security-1': {'can_buy': True, 'can_sell': False, 'can_hold': True}}}},
        'cash_after': {'tax': '500'}, 'proposed_actions': [{'quantity': '4', 'price': '100'}]}
    before = deepcopy(native)
    candidate = dict(native, target=target())
    assert project(native) == project(candidate)
    assert native == before


@pytest.mark.parametrize(('field', 'value'), [
    ('permitted_securities', {'tax': ['security-1']}), ('cash_minimums', {'tax': '500'}),
    ('trade_increments', {'tax': {'security-1': '1'}}), ('price_max_age_days', 7),
    ('price_max_age_days', True), ('cash_minimums', None),
])
def test_material_or_unknown_retired_target_rules_cannot_be_projected(field, value):
    native = legacy_target()
    native['planning_constraints'][field] = value
    with pytest.raises(ValueError, match='retired target'):
        project(native)


@pytest.mark.parametrize('field', ['target_allocations', 'eligible_accounts', 'excluded_positions',
                                 'target_tolerance', 'permissions', 'cash_after', 'proposed_actions'])
def test_financial_permissions_and_supported_target_changes_remain_detectable(field):
    baseline = {'target': legacy_target(), 'policy': {'permissions': {'tax': 'explicit'}},
                'cash_after': {'tax': '500'}, 'proposed_actions': [{'quantity': '4'}]}
    changed = deepcopy(baseline)
    if field == 'target_allocations':
        changed['target'][field] = {'security-1': '0.5', 'CASH': '0.5'}
    elif field in {'eligible_accounts', 'excluded_positions', 'target_tolerance'}:
        changed['target']['planning_constraints'][field] = {
            'eligible_accounts': [], 'excluded_positions': ['tax:security-1'],
            'target_tolerance': '0.02'}[field]
    elif field == 'permissions':
        changed['policy'][field] = {'tax': 'denied'}
    elif field == 'cash_after':
        changed[field]['tax'] = '499'
    else:
        changed[field][0]['quantity'] = '5'
    assert project(baseline) != project(changed)


def test_same_named_policy_rules_are_never_removed():
    policy = {'eligible_accounts': ['tax'], 'cash_minimums': {}, 'price_max_age_days': 1}
    assert project({'policy': policy}) == {'policy': policy}
