"""Confirmed corporate notices adjust inventory without inventing executions or gains."""

import copy
from decimal import Decimal, localcontext

from invest.models import DomainError, decimal


def apply(state, activity):
    from invest.ledger import activity_change_inplace

    account = next((row for row in state['accounts'] if row['id'] == activity['account_id']), None)
    from invest.security_identity import resolve

    if account is None:
        raise DomainError('Corporate action account/security does not resolve uniquely', 3)
    security = resolve(state['securities'], activity['security'])
    position = next((row for row in state['positions']
                     if row['account_id'] == account['id'] and row['security_id'] == security['id']), None)
    cash = next((row for row in state['cash_balances'] if row['account_id'] == account['id']), None)
    lots = [row for row in state['lots'] if row['account_id'] == account['id']
            and row['security_id'] == security['id']]
    if position is None or cash is None:
        raise DomainError('Corporate action needs known inventory and cash coverage', 3)
    numbers = [decimal(row[field]) for row in [activity, position, cash, *lots]
               for field in ('split_ratio', 'quantity', 'remaining_quantity', 'price', 'amount',
                             'fee', 'market_value', 'cost_basis', 'remaining_adjusted_basis')
               if row.get(field) is not None]
    with localcontext() as context:
        context.prec = max(100, sum(len(value.as_tuple().digits) + abs(value.as_tuple().exponent)
                                   for value in numbers) + 64)
        kind = activity['type']
        if kind == 'DIVIDEND_REINVESTMENT':
            amount = decimal(activity['amount'])
            if decimal(activity['quantity']) * decimal(activity['price']) != amount:
                raise DomainError('Reinvestment gross amount contradicts quantity and price', 3)
            old_ids = {row['id'] for row in lots}
            cash['amount'] = format(decimal(cash['amount']) + amount, 'f')
            purchase = copy.deepcopy(activity)
            purchase['type'] = 'BUY'
            changed, result = activity_change_inplace(state, purchase)
            for lot in changed['lots']:
                if lot['account_id'] == account['id'] and lot['security_id'] == security['id'] and lot['id'] not in old_ids:
                    lot['remaining_adjusted_basis'] = lot['cost_basis']
                    lot['basis_state'] = 'CONFIRMED_ACTIVITY'
                    lot['acquisition_reference'] = activity['activity_id']
                    lot['identity_status'] = 'ACTIVITY_DERIVED'
                    lot['saleable'] = False
            result['cash_change'] = format(decimal(activity.get('fee', '0')).copy_negate(), 'f')
            return changed, result
        if kind == 'STOCK_SPLIT':
            ratio = decimal(activity['split_ratio'])
            position['quantity'] = format(decimal(position['quantity']) * ratio, 'f')
            if position.get('price') is not None:
                from fractions import Fraction
                adjusted = Fraction(decimal(position['price'])) / Fraction(ratio)
                denominator = adjusted.denominator
                for factor in (2, 5):
                    while denominator % factor == 0:
                        denominator //= factor
                position['price'] = (format(Decimal(adjusted.numerator) / Decimal(adjusted.denominator), 'f')
                                     if denominator == 1 else None)
            for lot in lots:
                for field in ('quantity', 'remaining_quantity'):
                    lot[field] = format(decimal(lot[field]) * ratio, 'f')
            return state, {'cash_change': '0', 'cash_after': cash['amount'], 'warnings': []}
        snapshots = [row for row in state['snapshots'] if row['account']['id'] == account['id']
                     and row.get('status') != 'EVIDENCE_ONLY']
        latest = max(snapshots, key=lambda row: (row.get('imported_at', ''), row.get('id', '')), default={})
        quantity = decimal(position['quantity'])
        acquisitions = {event['activity_id'] for event in state['activities']
                        if event['account_id'] == account['id']
                        and event.get('security') in {security['id'], security['ticker']}
                        and event['type'] in {'BUY', 'DIVIDEND_REINVESTMENT'}}
        if (latest.get('lots_complete') is not True or quantity <= 0
                or sum((decimal(lot['remaining_quantity']) for lot in lots), Decimal(0)) != quantity
                or position.get('cost_basis') is None
                or any(lot.get('remaining_adjusted_basis') is None
                       or (lot.get('identity_status') != 'VERIFIED'
                           and not (lot.get('basis_state') == 'CONFIRMED_ACTIVITY'
                                    and lot.get('acquisition_reference') in acquisitions))
                       for lot in lots)):
            raise DomainError('Return of capital requires complete verified remaining lot basis', 3)
        active = sorted((lot for lot in lots if decimal(lot['remaining_quantity']) > 0), key=lambda row: row['id'])
        amount = decimal(activity['amount'])
        allocated = Decimal(0)
        for index, lot in enumerate(active):
            reduction = amount - allocated if index == len(active) - 1 else amount * decimal(lot['remaining_quantity']) / quantity
            basis = decimal(lot['remaining_adjusted_basis'])
            if reduction > basis:
                raise DomainError('Distribution exceeds a lot basis; review sourced gain treatment manually', 3)
            lot['remaining_adjusted_basis'] = format(basis - reduction, 'f')
            allocated += reduction
        position['cost_basis'] = format(sum((decimal(lot['remaining_adjusted_basis']) for lot in lots), Decimal(0)), 'f')
        cash['amount'] = format(decimal(cash['amount']) + amount, 'f')
        return state, {'cash_change': format(amount, 'f'), 'cash_after': cash['amount'], 'warnings': []}
