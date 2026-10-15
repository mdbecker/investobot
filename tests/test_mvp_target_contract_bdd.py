"""Allocations cannot silently masquerade as executable trading authority."""
import copy
import json
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from invest.ledger import Ledger
from invest.models import DomainError, TargetInput
from invest.planning import propose, save_policy
from invest.targets import save

scenarios('features/mvp/target_contract.feature')


@pytest.fixture
def target_context(tmp_path):
    ledger = Ledger(tmp_path / 'targets.db')
    yield {'ledger': ledger}
    ledger.connection.close()


@given('a synthetic account with 200 cash and a registered investment')
def account(target_context):
    ctx = target_context
    ledger = ctx['ledger']
    ledger.apply({'account': {'id': 'ira', 'name': 'Synthetic IRA', 'tax_status': 'TAX_FREE'},
                  'data_environment': 'SYNTHETIC', 'positions': [], 'lots': [],
                  'cash': '200', 'cash_known': True, 'positions_complete': True,
                  'lots_complete': True, 'source_timestamp': '2026-10-13',
                  'source_hash': 'target-contract'})
    sid = ledger.register_security({'ticker': 'FICTION', 'name': 'Fictional stock',
                                   'asset_type': 'STOCK', 'currency': 'USD',
                                   'source': 'Synthetic identity', 'data_environment': 'SYNTHETIC'})['id']
    ctx.update(sid=sid, before=copy.deepcopy(ledger.state()), payload={
        'name': 'Entire allocation', 'data_environment': 'SYNTHETIC',
        'target_allocations': {sid: '1'},
        'planning_constraints': {'eligible_accounts': ['ira'], 'excluded_positions': []}})


@when(parsers.parse('a target is saved with legacy execution field "{field}"'))
def legacy(target_context, field):
    ctx = target_context
    values = {'permitted_securities': {'ira': [ctx['sid']]}, 'cash_minimums': {'ira': '150'},
              'trade_increments': {'ira': {ctx['sid']: '10'}}, 'price_max_age_days': 30}
    ctx['payload']['planning_constraints'][field] = values[field]
    with pytest.raises(DomainError, match=field):
        save(ctx['ledger'], ctx['payload'])


@then('the target is rejected without writing a target version')
def rejected(target_context):
    ledger = target_context['ledger']
    assert ledger.rows('targets') == []
    assert ledger.rows('target_versions') == []
    assert ledger.state() == target_context['before']


@when(parsers.parse('a contribution is proposed with "{permission}" policy permission'))
def contribution(target_context, permission):
    ctx = target_context
    target = save(ctx['ledger'], ctx['payload'])
    permissions = {} if permission == 'missing' else {ctx['sid']: {
        'can_buy': permission == 'allowed', 'can_sell': False, 'can_hold': True,
        'share_increment': '1'}}
    policy = save_policy(ctx['ledger'], {
        'version': 'explicit-policy', 'data_environment': 'SYNTHETIC',
        'source': 'Reviewed synthetic policy', 'fee_per_trade': '0',
        'cash_floors': {'ira': '75'}, 'minimum_notional': '1',
        'permissions': {'ira': permissions}}, confirm=True)
    ctx['result'] = propose(ctx['ledger'], target['id'], policy=policy['id'],
        mode='contributions-only', as_of='2026-10-13', prices={ctx['sid']: {
            'price': '100', 'source': 'Synthetic price', 'as_of': '2026-10-13',
            'currency': 'USD', 'data_environment': 'SYNTHETIC'}})


@then('no purchase is proposed and accepted facts remain unchanged')
def no_buy(target_context):
    assert target_context['result']['proposed_actions'] == []
    assert target_context['ledger'].state() == target_context['before']


@then('one share costs 100 and the remaining 100 preserves the policy cash floor')
def floor(target_context):
    action, = target_context['result']['proposed_actions']
    assert (action['type'], action['quantity'], action['notional']) == ('BUY', '1', '100')
    assert target_context['result']['cash_after'] == {'ira': '100'}
    assert target_context['ledger'].state() == target_context['before']


@when('the target documentation JSON is validated')
def onboarding(target_context):
    text = (Path(__file__).resolve().parents[1] / 'docs/targets.md').read_text()
    target_context['example'] = TargetInput.model_validate(json.loads(text.split('```json\n')[1].split('```')[0]))


@then('it contains only supported target fields')
def example(target_context):
    constraints = target_context['example'].planning_constraints.model_dump()
    assert set(constraints) <= {'eligible_accounts', 'excluded_positions', 'target_tolerance'}
