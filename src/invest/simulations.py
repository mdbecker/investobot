"""Deterministic disposable simulation using the authoritative ledger event transform."""

import copy
import hashlib
import json
from decimal import Decimal, localcontext

from invest.ledger import activity_change_inplace, household_currency
from invest.models import DomainError, decimal


def simulate(state, actions):
    household_currency(state)
    if not isinstance(actions, list):
        raise DomainError('Simulation actions must be an array')
    working = copy.deepcopy(state)
    with localcontext() as context:
        context.prec = 100
        for index, original in enumerate(actions):
            action = copy.deepcopy(original)
            if action.get('type') not in {'BUY', 'SELL'}:
                raise DomainError('Portfolio proposal simulation supports explicit buys and sells')
            before_lots = {row['id'] for row in working['lots']}
            working, _ = activity_change_inplace(working, action)
            digest = hashlib.sha256(json.dumps(action, sort_keys=True, default=str).encode()).hexdigest()
            for row in working['lots']:
                if row['id'] not in before_lots:
                    row['id'] = f'hypothetical-{index}-{digest}'
            matches = [row for row in working['securities']
                       if action['security'] in {row['id'], row.get('ticker')}]
            if len(matches) != 1:
                raise DomainError('Hypothetical security must resolve uniquely', 3)
            position = next(row for row in working['positions']
                            if row['account_id'] == action['account_id'] and row['security_id'] == matches[0]['id'])
            position.update(price=str(action['price']), market_value=str(
                decimal(position['quantity']) * decimal(action['price'])),
                valuation_state='HYPOTHETICAL', as_of=action['date'])
        if any(row.get('market_value') is None for row in working['positions']):
            raise DomainError('Simulation needs explicit valuation assumptions for every holding', 3)
        total = sum((decimal(row['market_value']) for row in working['positions']), Decimal(0))
        total += sum((decimal(row['amount']) for row in working['cash_balances']), Decimal(0))
        return {'mode': 'HYPOTHETICAL', 'after': working,
                'household_value_after': str(total), 'issues': []}
