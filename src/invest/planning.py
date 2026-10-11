"""Contribution-first deterministic proposals with immutable explicit trading policies."""

import copy
import hashlib
import json
import uuid
from datetime import date, datetime, timezone
from decimal import ROUND_FLOOR, Decimal, localcontext

from invest.ledger import household_currency
from invest.models import DomainError, decimal
from invest.plan_storage import save_plan
from invest.plans import state_hash
from invest.targets import allocation_diff, show

SUPPORTED = {'STOCK', 'ETF', 'MUTUAL_FUND'}


def _text(value):
    result = format(value, 'f')
    return result.rstrip('0').rstrip('.') if '.' in result else result


def _json(value):
    return json.dumps(value, sort_keys=True, default=str)


def _validate(policy):
    if not isinstance(policy, dict) or not policy.get('version'):
        raise DomainError('Trading policy needs an explicit version')
    permissions = policy.get('permissions')
    if not isinstance(permissions, dict):
        raise DomainError('Trading policy needs explicit account/security permissions')
    for rules in permissions.values():
        if not isinstance(rules, dict):
            raise DomainError('Trading permissions must map canonical securities')
        for rule in rules.values():
            if not isinstance(rule, dict):
                raise DomainError('Trading permission must be a structured rule')
            for field in ('can_buy', 'can_sell', 'can_hold'):
                if field in rule and not isinstance(rule[field], bool):
                    raise DomainError('Trading permissions require JSON booleans')
            if rule.get('share_increment') is not None and decimal(rule['share_increment']) <= 0:
                raise DomainError('Execution increment must be positive')
    if decimal(policy.get('minimum_notional', '25')) < 0:
        raise DomainError('Minimum notional must be nonnegative')
    if not 0 <= decimal(policy.get('drift_trigger', '0.05')) <= 1:
        raise DomainError('Drift trigger must be a fraction')
    if set(policy.get('quarterly_months', [3, 6, 9, 12])) != {3, 6, 9, 12}:
        if policy.get('exception_approved') is not True or not policy.get('exception_reason'):
            raise DomainError('Nonquarterly windows require an approved reasoned exception policy')
    for floor in policy.get('cash_floors', {}).values():
        if decimal(floor) < 0:
            raise DomainError('Cash floors must be nonnegative')
    return policy


def save_policy(ledger, policy, *, confirm=False):
    policy = copy.deepcopy(_validate(policy))
    if policy.get('data_environment') not in {'REAL', 'SYNTHETIC'} or not policy.get('source'):
        raise DomainError('Approved policy needs environment and explicit human source')
    identifier = policy.get('id') or policy['version']
    policy['id'] = identifier
    securities = {row['id'] for row in ledger.rows('securities')}
    accounts = {row['id'] for row in ledger.rows('accounts')}
    for account, rules in policy['permissions'].items():
        if account not in accounts or set(rules) - securities:
            raise DomainError('Policy references unknown accounts or canonical securities', 3)
    digest = hashlib.sha256(_json(policy).encode()).hexdigest()
    existing = ledger.connection.execute('SELECT policy_hash,payload_json FROM trading_policy_versions WHERE id=?',
                                         (identifier,)).fetchone()
    if existing and existing[0] != digest:
        raise DomainError('Trading policy versions are immutable', 3)
    if not confirm:
        return dict(policy, status='PREVIEW', committed=False)
    if existing:
        return dict(policy, status='UNCHANGED', committed=False)
    with ledger.connection:
        ledger.connection.execute('INSERT INTO trading_policy_versions VALUES (?,?,?,?)',
                                  (identifier, datetime.now(timezone.utc).isoformat(), digest, _json(policy)))
    return dict(policy, status='APPROVED', committed=True)


def get_policy(ledger, policy_id):
    row = ledger.connection.execute('SELECT payload_json FROM trading_policy_versions WHERE id=?',
                                    (policy_id,)).fetchone()
    if not row:
        raise DomainError('Approved trading policy does not exist', 3)
    return json.loads(row[0])


def list_policies(ledger):
    return {'policies': [{'id': row[0], 'approved_at': row[1], 'policy_hash': row[2]}
                         for row in ledger.connection.execute(
                             'SELECT id,approved_at,policy_hash FROM trading_policy_versions ORDER BY approved_at DESC,id')]}


def propose(ledger, target_id, *, policy, mode, as_of, prices):
    """Direct dictionaries are synthetic domain previews; production uses approved IDs."""
    baseline = ledger.planning_state()
    with localcontext() as context:
        amounts = [decimal(row['market_value']) for row in baseline['positions']]
        amounts.extend(decimal(row['amount']) for row in baseline['cash_balances'])
        context.prec = max(100, sum(len(value.as_tuple().digits) + abs(value.as_tuple().exponent)
                                   for value in amounts) + 64)
        return _propose(ledger, target_id, policy, mode, as_of, prices, baseline)


def _propose(ledger, target_id, supplied, mode, as_of, prices, baseline):
    from invest.simulations import simulate

    day = date.fromisoformat(as_of)
    if mode not in {'contributions-only', 'rebalance'}:
        raise DomainError('Plan mode must be contributions-only or rebalance')
    preview = isinstance(supplied, dict)
    policy = copy.deepcopy(supplied if preview else get_policy(ledger, supplied))
    target = show(ledger, target_id)
    accounts = {row['id']: row for row in baseline['accounts']}
    securities = {row['id']: row for row in baseline['securities']}
    positions = {(row['account_id'], row['security_id']): row for row in baseline['positions']}
    cash = {row['account_id']: decimal(row['amount']) for row in baseline['cash_balances']}
    values = {}
    for position in baseline['positions']:
        sid = position['security_id']
        values[sid] = values.get(sid, Decimal(0)) + decimal(position['market_value'])
    total = sum(values.values(), sum(cash.values(), Decimal(0)))
    weights = {sid: decimal(weight) for sid, weight in target['target_allocations'].items()}
    issues, actions = [], []

    def issue(code, message, *, blocking=True, account=None, security=None):
        issues.append({'code': code, 'message': message, 'blocks_calculation': blocking,
                       'blocks_proposals': blocking, 'blocks_execution_review': True,
                       'account_id': account, 'security_id': security})

    try:
        _validate(policy)
    except (DomainError, TypeError, ValueError) as error:
        issue('INVALID_POLICY', str(error))
    currency = household_currency(baseline)
    environments = {row['data_environment'] for row in baseline['accounts'] + baseline['snapshots']
                    if row.get('data_environment')}
    environment = policy.get('data_environment') or next(iter(environments), None)
    price_environment = policy.get('price_environment', environment)
    if (policy.get('baseline_environment', environment) != price_environment or
            environments - {environment} or environment not in {'REAL', 'SYNTHETIC'}):
        issue('MIXED_DATA_ENVIRONMENT', 'Planning inputs need one explicit source environment')
    if preview and environment != 'SYNTHETIC':
        issue('UNAPPROVED_TRADING_POLICY', 'Real proposals require an immutable approved trading policy')
    if preview:
        issue('SYNTHETIC_DOMAIN_PREVIEW', 'Supplied policy dictionary is synthetic preview only', blocking=False)
    max_age = policy.get('max_position_age_days', 120)
    for position in baseline['positions']:
        source = position.get('source_timestamp')
        if not source:
            issue('UNKNOWN_POSITION_DATE', 'Holding source date is unknown')
        elif (day - date.fromisoformat(source[:10])).days > max_age:
            issue('STALE_POSITIONS', 'Accepted quantities are stale')
        elif date.fromisoformat(source[:10]) > day:
            issue('FUTURE_POSITION_DATE', 'Planning cannot use later observations')
    permissions = policy.get('permissions', {})
    eligible = target['planning_constraints'].get('eligible_accounts', [])
    normalized_prices = {}
    for sid, observation in (prices or {}).items():
        if sid not in securities:
            raise DomainError('Prices require canonical registered securities')
        if isinstance(observation, dict):
            price = decimal(observation['price'])
            if (observation.get('data_environment', environment) != environment or
                    observation.get('currency', currency) != currency):
                issue('MIXED_DATA_ENVIRONMENT', 'Price currency or environment differs')
            if not observation.get('as_of') or not observation.get('source'):
                issue('UNKNOWN_PRICE_PROVENANCE', 'Price observation requires date and source')
            elif not 0 <= (day - date.fromisoformat(observation['as_of'][:10])).days <= 7:
                issue('STALE_PRICES', 'Price assumption is stale or future-dated')
        else:
            price = decimal(observation)
            if not preview:
                issue('UNKNOWN_PRICE_PROVENANCE', 'Approved proposals require sourced price observations')
        if price <= 0:
            issue('INVALID_PRICE', 'Executable prices must be positive')
        else:
            normalized_prices[sid] = price
    scenario_baseline = copy.deepcopy(ledger.state())
    values = {}
    for position in scenario_baseline['positions']:
        sid = position['security_id']
        if sid in normalized_prices:
            position['price'] = _text(normalized_prices[sid])
            position['market_value'] = _text(decimal(position['quantity']) * normalized_prices[sid])
        values[sid] = values.get(sid, Decimal(0)) + decimal(position['market_value'])
    total = sum(values.values(), sum(cash.values(), Decimal(0)))
    for account in eligible:
        if account not in cash:
            issue('UNKNOWN_CASH_COVERAGE', 'Account cash is unknown', account=account)
        if policy.get('cash_confirmation', {}).get(account) is False:
            issue('UNCONFIRMED_CASH', 'Cash is not confirmed', account=account)
        for sid, rule in permissions.get(account, {}).items():
            if (rule.get('can_buy') is True or rule.get('can_sell') is True) and not rule.get('share_increment'):
                issue('UNKNOWN_EXECUTION_PRECISION', 'Explicit execution increment required', account=account, security=sid)
    fee_assumption = policy.get('fee_per_trade')
    fee = decimal(fee_assumption) if fee_assumption is not None else Decimal(0)
    if fee < 0:
        issue('INVALID_POLICY', 'Fees must be nonnegative')
    if fee_assumption is None:
        issue('UNKNOWN_EXECUTION_FEES', 'Zero modeled fee is hypothetical; verify actual fees', blocking=False)
    drift = max((abs(values.get(sid, Decimal(0)) / total - weight)
                 for sid, weight in weights.items() if sid != 'CASH'), default=Decimal(0)) if total else Decimal(0)
    quarterly = day.month in policy.get('quarterly_months', [3, 6, 9, 12]) and drift > decimal(policy.get('drift_trigger', '0.05'))
    cadence = mode == 'contributions-only' or quarterly
    used = {event['account_id'] for event in baseline['activities'] if event.get('type') in {'BUY', 'SELL'}
            and event.get('date', '')[:7] == as_of[:7]}
    for account in set(eligible) & used:
        issue('MONTHLY_CADENCE_USED', 'Confirmed trading already used this account month', account=account)
    tax_budget = None
    if policy.get('annual_tax_budget'):
        from invest.tax_policy import annual_budget

        tax_budget = annual_budget(baseline, policy['annual_tax_budget'])
    headroom = decimal(tax_budget['remaining_allowance']) if tax_budget and tax_budget.get('remaining_allowance') is not None else None
    spent = Decimal(0)
    minimum = decimal(policy.get('minimum_notional', '25'))
    floors = {account: decimal(value) for account, value in policy.get('cash_floors', {}).items()}

    def add(kind, account, sid, amount):
        nonlocal spent
        rule = permissions.get(account, {}).get(sid, {})
        permission = 'can_buy' if kind == 'BUY' else 'can_sell'
        if sid not in securities:
            issue('UNRESOLVED_SECURITY', 'Policy security is not canonical', blocking=False)
            return
        if rule.get(permission) is not True:
            if permission not in rule:
                issue('UNKNOWN_TRADING_PERMISSION', 'Account/security eligibility is unknown', blocking=False)
            return
        if sid not in normalized_prices:
            issue('UNKNOWN_PRICE', 'Security has no sourced price assumption', blocking=False)
            return
        position = positions.get((account, sid))
        if position and position['id'] in target['planning_constraints'].get('excluded_positions', []):
            return
        if securities[sid]['asset_type'] not in SUPPORTED:
            issue('INDIVIDUAL_BOND_REQUIRES_SCENARIO', 'Unsupported automatic trade needs explicit scenario', blocking=False)
            return
        price = normalized_prices[sid]
        increment = decimal(rule['share_increment'])
        quantity = (amount / price / increment).to_integral_value(rounding=ROUND_FLOOR) * increment
        if quantity <= 0:
            return
        if quantity * price < minimum:
            issue('BELOW_MINIMUM_NOTIONAL', 'Trade below explicit minimum notional', blocking=False)
            return
        action = {'type': kind, 'account_id': account, 'security': sid, 'quantity': _text(quantity),
                  'price': _text(price), 'date': as_of, 'fee': _text(fee)}
        if kind == 'SELL':
            lots = [row for row in baseline['lots'] if row['account_id'] == account and row['security_id'] == sid
                    and decimal(row['remaining_quantity']) > 0]
            taxable = accounts[account]['tax_status'] == 'TAXABLE'
            if accounts[account]['tax_status'] == 'OTHER':
                issue('UNKNOWN_ACCOUNT_TAX_CLASSIFICATION', 'Sale needs authoritative account tax treatment', blocking=False)
                return
            if taxable and any(row.get('cost_basis') is None or not row.get('acquisition_date')
                               or row.get('identity_status') != 'VERIFIED' for row in lots):
                issue('UNRESOLVED_LOTS', 'Taxable sale requires verified acquisition dates and basis', blocking=False)
                return
            def basis_per_share(row):
                if row.get('remaining_adjusted_basis') is not None:
                    return decimal(row['remaining_adjusted_basis']) / decimal(row['remaining_quantity'])
                return decimal(row['cost_basis']) / decimal(row['quantity'])
            lots.sort(key=lambda row: (-basis_per_share(row), row['id']))
            consistent_lots = sum((decimal(row['remaining_quantity']) for row in lots), Decimal(0)) == decimal(positions[account, sid]['quantity'])
            if taxable and not consistent_lots:
                issue('UNRESOLVED_LOTS', 'Whole-position lots do not reconcile', blocking=False)
                return
            selected, remaining, cost = [], quantity, Decimal(0)
            for lot in lots:
                used_quantity = min(remaining, decimal(lot['remaining_quantity']))
                if used_quantity <= 0:
                    continue
                basis = basis_per_share(lot) * used_quantity
                if taxable:
                    if headroom is None or tax_budget['status'] == 'BLOCKED' or not lot.get('acquisition_date'):
                        issue('UNKNOWN_TAX_BUDGET', 'Taxable sale requires annual coverage and exact lots', blocking=False)
                        return
                    acquired = date.fromisoformat(lot['acquisition_date'])
                    try:
                        anniversary = acquired.replace(year=acquired.year + 1)
                    except ValueError:
                        anniversary = acquired.replace(year=acquired.year + 1, day=28)
                    long_term = day > anniversary
                    rate = decimal(policy['annual_tax_budget']['long_term_rate' if long_term else 'short_term_rate'])
                    cost += max(Decimal(0), used_quantity * price - basis) * rate
                selected.append({'lot_id': lot['id'], 'quantity': _text(used_quantity)})
                remaining -= used_quantity
            if cost + spent > (headroom if headroom is not None else Decimal(0)):
                issue('ANNUAL_TAX_BUDGET_EXCEEDED', 'Sale exceeds conservative annual positive tax allowance', blocking=False)
                return
            spent += cost
            if consistent_lots:
                action['lot_allocations'] = selected
        actions.append(action)
        delta = quantity * price
        values[sid] = values.get(sid, Decimal(0)) + (delta if kind == 'BUY' else -delta)
        cash[account] += -delta - fee if kind == 'BUY' else delta - fee

    blocking = any(item['blocks_calculation'] for item in issues)
    if not blocking and total > 0:
        def purchases():
            for sid, weight in sorted(weights.items(), key=lambda pair: pair[0]):
                if sid == 'CASH':
                    continue
                for account in sorted(eligible):
                    available = max(Decimal(0), cash[account] - floors.get(account, Decimal(0)) - fee)
                    shortage = max(Decimal(0), total * weight - values.get(sid, Decimal(0)))
                    add('BUY', account, sid, min(shortage, available))
        purchases()
        post_cash_drift = max((abs(values.get(sid, Decimal(0)) / total - weight)
                               for sid, weight in weights.items() if sid != 'CASH'),
                              default=Decimal(0))
        quarterly = (day.month in policy.get('quarterly_months', [3, 6, 9, 12]) and
                     post_cash_drift > decimal(policy.get('drift_trigger', '0.05')))
        cadence = mode == 'contributions-only' or quarterly
        if mode == 'rebalance' and quarterly:
            for account, sid in sorted(positions):
                if account not in eligible:
                    continue
                surplus = max(Decimal(0), values.get(sid, Decimal(0)) - total * weights.get(sid, Decimal(0)))
                add('SELL', account, sid, min(surplus, decimal(positions[account, sid]['quantity']) * normalized_prices.get(sid, Decimal(0))))
            purchases()
    simulation = simulate(scenario_baseline, actions) if actions else {'after': scenario_baseline,
        'household_value_after': _text(total)}
    final = simulation['after']
    expected_total = total - fee * len(actions)
    if decimal(simulation['household_value_after']) != expected_total:
        raise DomainError('Authoritative simulation disagrees with planned household value', 3)
    final_cash = {row['account_id']: decimal(row['amount']) for row in final['cash_balances']}
    if final_cash != cash:
        raise DomainError('Authoritative simulation disagrees with account cash', 3)
    final_values = {}
    for position in final['positions']:
        sid = position['security_id']
        final_values[sid] = final_values.get(sid, Decimal(0)) + decimal(position['market_value'])
    if final_values != values:
        raise DomainError('Authoritative simulation disagrees with security values', 3)
    proposed = allocation_diff(final, target)
    plan = {'id': str(uuid.uuid4()), 'name': 'Contribution-first proposal', 'created_at': datetime.now(timezone.utc).isoformat(),
            'as_of': as_of, 'source_state': baseline, 'source_state_hash': state_hash(baseline),
            'target': target, 'target_version_id': target['version_id'], 'policy': policy,
            'policy_id': policy.get('id', policy['version']), 'mode': mode, 'executed': False,
            'algorithm_version': 'contribution-first-hifo-1', 'data_environment': environment,
            'manifest_ids': sorted({observation['manifest_id'] for observation in (prices or {}).values()
                                    if isinstance(observation, dict) and observation.get('manifest_id')}),
            'proposed_actions': actions, 'issues': issues, 'simulation': simulation,
            'cash_after': {key: _text(value) for key, value in final_cash.items()},
            'cadence': {'eligible': cadence and not bool(set(eligible) & used)},
            'tax_budget': tax_budget, 'estimated_tax_budget_consumption': _text(spent),
            'tax_analysis': {'estimated_tax_effect': _text(spent)},
            'assumptions': {'prices': prices, 'fee_per_trade': fee_assumption,
                            'policy_approval': 'SYNTHETIC_DOMAIN_PREVIEW' if preview else 'APPROVED'},
            'remaining_target_drift': proposed['allocations'], 'trade_count': len(actions),
            'turnover': _text(sum((decimal(action['quantity']) * decimal(action['price']) for action in actions), Decimal(0))),
            'warnings': [item['message'] for item in issues],
            'status': 'BLOCKED' if blocking else 'REVIEW_REQUIRED' if issues else 'READY_FOR_HUMAN_REVIEW'}
    save_plan(ledger, plan)
    return plan
