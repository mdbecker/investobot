"""Explicit fictional approved policy setup for persistence regression fixtures.

This helper only prepares evidence and calls the canonical planner. It computes
no actions, fetches no prices, and is not an application compatibility interface.
"""
from invest.models import DomainError
from invest.planning import propose, save_policy


def saved_proposal(ledger, unused_client, target_id, *, as_of, prices=None, name=None, **unused):
    if prices is not None and not isinstance(prices, dict):
        raise DomainError('Prices must be an object')
    state = ledger.planning_state()
    permissions = {}
    for account in state['accounts']:
        permissions[account['id']] = {security['id']: {
            'can_buy': True, 'can_sell': True, 'can_hold': True, 'share_increment': '0.001'}
            for security in state['securities']}
    policy = save_policy(ledger, {'version': 'fictional-persistence-fixture',
        'data_environment': 'SYNTHETIC', 'source': 'Explicit fictional regression policy',
        'max_position_age_days': 1, 'minimum_notional': '0', 'fee_per_trade': '0', 'cash_floors': {},
        'permissions': permissions}, confirm=True)
    observations = {position['security_id']: {'price': position['price'],
        'as_of': as_of, 'currency': 'USD', 'data_environment': 'SYNTHETIC',
        'source': 'Explicit fictional regression price'}
        for position in state['positions'] if position.get('price') is not None}
    for identity, observation in (prices or {}).items():
        observations[identity] = dict(observation, data_environment='SYNTHETIC')
    return propose(ledger, target_id, policy=policy['id'], mode='rebalance',
                   as_of=as_of, prices=observations)


def account_fixture(ctx, status, account='ira'):
    ledger = ctx['ledger']
    ledger.apply({'account': {'id': account, 'name': 'Fictional account', 'tax_status': status},
        'data_environment': 'SYNTHETIC', 'positions': [], 'lots': [], 'cash': '100',
        'cash_known': True, 'positions_complete': True, 'lots_complete': True,
        'source_hash': 'fictional-independent-account', 'source_timestamp': '2026-10-08'})
    sid = ledger.register_security({'ticker': 'FIXTURE', 'asset_type': 'STOCK',
        'name': 'Fictional fixture', 'currency': 'USD', 'source': 'Reviewed fictional identity',
        'data_environment': 'SYNTHETIC'})['id']
    ctx['payload'] = {'name': 'Fictional persisted target', 'data_environment': 'SYNTHETIC',
        'target_allocations': {sid: '1'}, 'planning_constraints': {'eligible_accounts': [account]}}
