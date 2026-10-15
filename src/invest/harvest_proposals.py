"""Conditional loss-harvest proposals from immutable human-approved policies."""

import hashlib
import json
from datetime import date
from decimal import ROUND_FLOOR, Decimal, localcontext

from invest.financial_state import state_hash
from invest.models import DomainError, decimal
from invest.security_identity import resolve
from invest.simulations import simulate
from invest.tax import estimate_sale
from invest.tax_policy import _issue, _plain, harvest_plan, trade_annual_budget


def _latest_receipts(state):
    """Preserve receipt order for tied import times, matching SQLite projection."""
    latest = {}
    for row in sorted(state['snapshots'], key=lambda row: row['imported_at']):
        if row.get('status') != 'EVIDENCE_ONLY':
            latest[row['account']['id']] = row
    return latest


def _planning_fingerprint(state):
    inputs = {table: [dict(row) for row in state[table]] for table in (
        'accounts', 'securities', 'positions', 'lots', 'cash_balances', 'activities')}
    for table, field in (('accounts', 'metadata_history'), ('securities', 'classification_history')):
        for row in inputs[table]:
            row.pop(field, None)
    fields = ('id', 'imported_at', 'source_timestamp', 'source_hash', 'positions_complete',
              'lots_complete', 'cash_known', 'data_environment', 'institution_status')
    inputs['snapshots'] = [dict({key: row.get(key) for key in fields},
                              issues=row.get('issues', []), account={'id': account})
                          for account, row in _latest_receipts(state).items()]
    return state_hash(inputs)


def conditional_harvest(state, policy, as_of):
    from invest.planning import ApprovedPolicy

    scope = policy['harvest_review']
    result = harvest_plan(state, scope, as_of)
    result.update(policy_id=policy.get('id'), policy_version=policy.get('version'),
        policy_hash=getattr(policy, 'policy_hash', None), source_state_hash=_planning_fingerprint(state),
        proposed_actions=[], simulated_cash={}, estimated_net_tax_effect=None,
        wash_sale_certified=False, mode='CONDITIONAL_HARVEST')
    issues = result['issues']
    for account, receipt in _latest_receipts(state).items():
        issues.extend(dict(source_issue, account_id=account)
                      for source_issue in receipt.get('issues', []))

    def issue(code, message, *, calculation=True):
        issues.append(_issue(code, message, calculation=calculation))

    digest = hashlib.sha256(json.dumps(policy, sort_keys=True, default=str).encode()).hexdigest()
    if not isinstance(policy, ApprovedPolicy) or policy.policy_hash != digest:
        issue('UNAPPROVED_HARVEST_POLICY', 'Resolve an immutable saved policy before proposing trades')
    if scope['loss_sale_date'] != as_of:
        issue('HARVEST_DATE_MISMATCH', 'Policy sale date must match the requested analysis date')
    environment = policy['data_environment']
    if scope.get('data_environment') != environment:
        issue('MIXED_DATA_ENVIRONMENT', 'Harvest scope and approved policy environments differ')
    fee = policy.get('fee_per_trade')
    if fee is None:
        issue('UNKNOWN_FEES', 'Approve explicit sale and replacement fees')
    budget_policy = policy.get('annual_tax_budget')
    if budget_policy is None:
        issue('UNKNOWN_ANNUAL_TAX_BUDGET', 'Approve annual tax rates, allowance and household coverage')
        budget = None
    else:
        budget = trade_annual_budget(state, budget_policy, as_of)
        budget['remaining_headroom'] = budget['remaining_allowance']
        issues.extend(budget['issues'])
        if any(row['code'] == 'UNKNOWN_TAX_RATE' for row in budget['issues']):
            issue('UNKNOWN_TAX_RATES', 'Both short- and long-term tax rates are required')
    result['annual_tax_budget'] = budget
    replacement = scope.get('replacement') or {}
    if not replacement.get('source') or not replacement.get('source_locator'):
        issue('UNVERIFIED_REPLACEMENT', 'Replacement comparison requires a reviewed source and locator')
    try:
        replacement_security = resolve(state['securities'], replacement.get('security'))
    except DomainError:
        replacement_security = None
        issue('UNVERIFIED_REPLACEMENT', 'Replacement must resolve to a canonical security')
    source_security = result.get('security_id')
    if replacement_security and (replacement_security['id'] == source_security or
            replacement_security.get('asset_type') in {'BOND', 'TREASURY', 'OTHER'}):
        issue('UNVERIFIED_REPLACEMENT', 'Replacement cannot be the loss-sale security or an unsupported asset')
    accounts = {row['id']: row for row in state['accounts']}
    positions = {(row['account_id'], row['security_id']): row for row in state['positions']}
    lots = {row['id']: row for row in state['lots']}
    cash = {row['account_id']: row for row in state['cash_balances']}
    prices = scope.get('price_observations', {})
    observed = date.fromisoformat(as_of)

    def mark(identity):
        evidence = prices.get(identity, {})
        if not evidence.get('source') or evidence.get('price') is None or not evidence.get('as_of'):
            issue('UNKNOWN_PRICE_PROVENANCE', 'Both trade prices require dated original-source evidence')
            return None
        if evidence.get('data_environment') != environment:
            issue('MIXED_DATA_ENVIRONMENT', 'Trade price environment differs from the approved policy')
        if evidence.get('currency') != 'USD':
            issue('CURRENCY_MISMATCH', 'Harvest estimates require explicit matching USD prices')
        try:
            age = (observed - date.fromisoformat(evidence['as_of'][:10])).days
            value = decimal(evidence['price'])
            if age < 0 or age > policy.get('max_position_age_days', 120):
                issue('STALE_PRICE', 'Price observation lies outside the approved freshness window')
            if value <= 0:
                raise ValueError('Nonpositive price')
            return value
        except (ValueError, TypeError, DomainError):
            issue('UNKNOWN_PRICE_PROVENANCE', 'Price and observation date must be valid')
            return None

    sale_price = mark(source_security)
    buy_price = mark(replacement_security['id']) if replacement_security else None
    grouped = {}
    for candidate in result.get('loss_lots', []):
        grouped.setdefault(candidate['account_id'], []).append(candidate)
    for account_id, candidates in grouped.items():
        account = accounts[account_id]
        if account.get('data_environment') != environment:
            issue('MIXED_DATA_ENVIRONMENT', 'Accepted account provenance differs from the approved policy')
        if account.get('currency') != 'USD':
            issue('CURRENCY_MISMATCH', 'Harvest account currency must be USD')
        position = positions[(account_id, source_security)]
        for row, maximum in ((position, policy.get('max_position_age_days', 120)),
                             (cash.get(account_id), policy.get('max_cash_age_days', 120))):
            try:
                stamp = row.get('source_timestamp') or row.get('as_of')
                age = (observed - date.fromisoformat(stamp[:10])).days
                if age < 0 or age > maximum:
                    issue('STALE_FINANCIAL_STATE', 'Confirmed inventory or cash is outside its freshness window')
            except (AttributeError, TypeError, ValueError):
                issue('UNKNOWN_CASH' if row is None else 'UNKNOWN_FINANCIAL_DATE',
                      'Confirmed cash and inventory need dated source evidence')
        permissions = policy['permissions'].get(account_id, {})
        sell_rule = permissions.get(source_security, {})
        buy_rule = permissions.get(replacement_security['id'], {}) if replacement_security else {}
        if sell_rule.get('can_sell') is not True:
            issue('SELL_PERMISSION_REQUIRED', 'Loss-sale permission must be explicitly approved')
        if (buy_rule.get('can_buy') is not True or buy_rule.get('can_hold') is not True
                or replacement.get('approved_for_purchase') is not True):
            issue('REPLACEMENT_PERMISSION_REQUIRED', 'Replacement purchase must be explicitly approved')
        for rule in (sell_rule, buy_rule):
            if rule.get('share_increment') is None:
                issue('UNKNOWN_EXECUTION_INCREMENT', 'Both trades need explicit execution increments')
        for candidate in candidates:
            lot = lots[candidate['lot_id']]
            if sale_price is not None and (sale_price * decimal(candidate['remaining_quantity']) >=
                                           decimal(candidate['remaining_adjusted_basis'])):
                issue('NOT_A_LOSS_AT_PROPOSED_PRICE', 'Current sourced sale price does not support a loss')
            if (lot.get('identity_status') != 'VERIFIED' or lot.get('saleable') is not True
                    or not lot.get('source_lot_id') or not lot.get('identity_source')):
                issue('UNVERIFIED_LOT_IDENTITY', 'Loss sales require independently verified saleable lot identity')
            if lot.get('data_environment') != environment:
                issue('MIXED_DATA_ENVIRONMENT', 'Lot provenance differs from the approved policy')
    # Legal review remains mandatory, but otherwise complete evidence can support
    # explicitly conditional arithmetic. Known household conflicts suppress actions.
    if any(row['code'] != 'HUMAN_WASH_SALE_REVIEW' and
           (row.get('blocks_proposal', False) or row.get('blocks_proposals', False)
            or row.get('blocks_calculation', False)) for row in issues):
        result['status'] = 'BLOCKED' if any(row.get('blocks_calculation', False) for row in issues) else 'REVIEW_REQUIRED'
        return result
    actions, estimate, estimates = [], Decimal(0), []
    with localcontext() as context:
        context.prec = max(100, len(str(state)) + len(str(policy)))
        for account_id, candidates in sorted(grouped.items()):
            quantity = sum((decimal(row['remaining_quantity']) for row in candidates), Decimal(0))
            increment = decimal(policy['permissions'][account_id][source_security]['share_increment'])
            if quantity % increment:
                issue('INVALID_EXECUTION_INCREMENT', 'Exact lot quantities violate approved sale increments')
                continue
            notional = quantity * sale_price
            trade_fee = decimal(fee)
            minimum = decimal(policy.get('minimum_notional', '25'))
            starting = decimal(cash[account_id]['amount'])
            floor = decimal(policy.get('cash_floors', {}).get(account_id, '0'))
            available = starting + notional - trade_fee * 2 - floor
            buy_increment = decimal(policy['permissions'][account_id][replacement_security['id']]['share_increment'])
            buy_quantity = (available / buy_price / buy_increment).to_integral_value(rounding=ROUND_FLOOR) * buy_increment
            if available <= 0 or buy_quantity <= 0:
                issue('INSUFFICIENT_REPLACEMENT_CASH', 'Sale proceeds cannot fund a replacement above the approved floor')
                continue
            if min(notional, buy_quantity * buy_price) < minimum:
                issue('MINIMUM_NOTIONAL', 'Conditional trades fall below the approved minimum notional')
                continue
            allocations = [{'lot_id': row['lot_id'], 'quantity': row['remaining_quantity']} for row in candidates]
            sale = estimate_sale([(lots[candidate['lot_id']], candidate['remaining_quantity'])
                                  for candidate in candidates], sale_price, as_of, trade_fee,
                                 {'LONG_TERM': budget_policy['long_term_rate'],
                                  'SHORT_TERM': budget_policy['short_term_rate']})
            estimates.append(sale)
            estimate += decimal(sale['estimated_tax_effect'])
            actions.extend([
                dict(type='SELL', account_id=account_id, security=source_security, quantity=_plain(quantity),
                     price=_plain(sale_price), notional=_plain(notional), fee=_plain(trade_fee),
                     date=as_of, lot_allocations=allocations, sale_estimate=sale, conditional=True),
                dict(type='BUY', account_id=account_id, security=replacement_security['id'],
                     quantity=_plain(buy_quantity), price=_plain(buy_price), notional=_plain(buy_quantity * buy_price),
                     fee=_plain(trade_fee), date=as_of, conditional=True)])
        if any(row['code'] != 'HUMAN_WASH_SALE_REVIEW' for row in issues):
            result.update(status='BLOCKED', proposed_actions=[])
            return result
        if actions:
            simulation = simulate(state, actions)
            result['simulated_cash'] = {row['account_id']: _plain(decimal(row['amount']))
                                       for row in simulation['after']['cash_balances']}
            result.update(proposed_actions=actions, estimated_net_tax_effect=_plain(estimate))
            result['tax_analysis'] = {key: _plain(sum((decimal(sale[key]) for sale in estimates), Decimal(0)))
                                      for key in ('realized_gain_loss', 'short_term_gain_loss',
                                                  'long_term_gain_loss', 'estimated_tax_effect',
                                                  'positive_estimated_tax_cost')}
            result['estimated_tax_budget_consumption'] = result['tax_analysis']['positive_estimated_tax_cost']
    result.update(status='REVIEW_REQUIRED', assumptions={
        'losses_replenish_allowance': False, 'signed_tax_effect_is_conditional': True,
        'wash_adjustments_applied': False}, sources=[policy['source'], replacement.get('source')])
    return result
