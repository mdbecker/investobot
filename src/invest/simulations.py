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
    numbers = []
    financial_fields = {'quantity', 'remaining_quantity', 'price', 'market_value',
                        'cost_basis', 'remaining_adjusted_basis', 'amount', 'fee'}

    def supplied_numbers(value):
        if isinstance(value, dict):
            for key, cell in value.items():
                if key in financial_fields and cell is not None:
                    numbers.append(decimal(cell))
                elif isinstance(cell, (dict, list)):
                    supplied_numbers(cell)
        elif isinstance(value, list):
            for cell in value:
                supplied_numbers(cell)
    supplied_numbers(state)
    supplied_numbers(actions)
    with localcontext() as context:
        context.prec = max(100, sum(len(number.as_tuple().digits) + abs(number.as_tuple().exponent)
                                   for number in numbers) + 64)
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
            from invest.security_identity import resolve

            security = resolve(working['securities'], action['security'])
            position = next(row for row in working['positions']
                            if row['account_id'] == action['account_id'] and row['security_id'] == security['id'])
            position.update(price=str(action['price']), market_value=str(
                decimal(position['quantity']) * decimal(action['price'])),
                valuation_state='HYPOTHETICAL', as_of=action['date'])
        if any(row.get('market_value') is None for row in working['positions']):
            raise DomainError('Simulation needs explicit valuation assumptions for every holding', 3)
        total = sum((decimal(row['market_value']) for row in working['positions']), Decimal(0))
        total += sum((decimal(row['amount']) for row in working['cash_balances']), Decimal(0))
        return {'mode': 'HYPOTHETICAL', 'after': working,
                'household_value_after': str(total), 'issues': []}
