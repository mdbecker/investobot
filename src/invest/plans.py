"""Conservative deterministic proposals; only immutable plans are persisted."""

import copy
import hashlib
import json
import uuid
from datetime import date, datetime, timezone
from decimal import ROUND_FLOOR, Decimal

from invest.analytics import exposure
from invest.ledger import activity_change_inplace, household_currency
from invest.models import DomainError, decimal
from invest.scenarios import readonly_client, simulate
from invest.targets import allocation_diff
from invest.targets import show as target_show
from invest.tax import analyze

ZERO = Decimal('0')
SUPPORTED = {'STOCK', 'ETF', 'MUTUAL_FUND'}


def state_hash(state):
    """Canonical financial fingerprint, independent of incidental collection order."""
    numeric_fields = {'quantity', 'remaining_quantity', 'price', 'market_value', 'cost_basis',
                      'amount', 'fee', 'execution_price', 'gross_amount', 'net_amount'}
    def exact_decimal(value):
        text = format(value, 'f')
        return (text.rstrip('0').rstrip('.') if '.' in text else text) if value else '0'

    def canonical(value, field=None):
        if isinstance(value, dict):
            return {k: canonical(v, k) for k, v in sorted(value.items())}
        if isinstance(value, list):
            items = [canonical(v) for v in value]
            return sorted(items, key=lambda v: json.dumps(v, sort_keys=True, default=str))
        if isinstance(value, Decimal):
            return exact_decimal(value)
        if isinstance(value, str) and field in numeric_fields:
            try:
                return exact_decimal(decimal(value))
            except (ValueError, DomainError):
                return value
        return value
    return hashlib.sha256(json.dumps(canonical(state), sort_keys=True, default=str).encode()).hexdigest()


def _number(value):
    return format(value.normalize(), 'f') if value else '0'


def _floor(quantity, increment):
    return (quantity / increment).to_integral_value(rounding=ROUND_FLOOR) * increment


def _prices(state, target, supplied, as_of, warnings):
    """A quote assumption can revalue hypothetical state, never accepted state."""
    currency = household_currency(state)
    securities = {s['id']: s for s in state['securities']}
    needed = set(target['target_allocations']) - {'CASH'}
    needed |= {p['security_id'] for p in state['positions'] if decimal(p['quantity']) > 0}
    if not isinstance(supplied, dict) or set(supplied) - securities.keys():
        raise DomainError('Price assumptions must map registered canonical security IDs to observations')
    result = {}
    dated_prices = {}
    for position in state['positions']:
        if position.get('price') is not None and position.get('source_timestamp'):
            dated_prices.setdefault(position['security_id'], []).append(position)
    for sid in sorted(needed):
        observation = supplied.get(sid)
        if observation is None:
            known = dated_prices.get(sid, [])
            chosen = max(known, key=lambda p: p['source_timestamp'], default=None)
            observation = {'price': chosen['price'], 'as_of': chosen['source_timestamp'],
                           'currency': currency, 'source': 'ACCEPTED_SNAPSHOT'} if chosen else None
            if chosen and any(p['source_timestamp'] == chosen['source_timestamp'] and
                              decimal(p['price']) != decimal(chosen['price']) for p in known):
                warnings.append(f'{sid}: conflicting accepted prices; supply a verified price assumption')
                continue
        if observation is None:
            warnings.append(f'{sid}: price or source date unavailable')
            continue
        if not isinstance(observation, dict) or set(observation) - {'price', 'as_of', 'currency', 'source'}:
            raise DomainError('Price observations require price, as_of, currency and source')
        try:
            price = decimal(observation['price'])
            observed = date.fromisoformat(str(observation['as_of'])[:10])
            source = observation['source']
            observed_currency = observation['currency']
        except (KeyError, ValueError, TypeError) as exc:
            raise DomainError('Price observations require finite price, ISO as_of, currency and source') from exc
        if not isinstance(source, str) or not source.strip() or price <= 0:
            raise DomainError('Price must be positive and have explicit provenance')
        if observed_currency != currency or securities[sid].get('currency', currency) != currency:
            raise DomainError('Price/security currency differs; no FX model is configured', 3)
        age = (as_of - observed).days
        if age < 0 or age > target['planning_constraints']['price_max_age_days']:
            warnings.append(f'{sid}: stale or future price assumption excluded')
            continue
        result[sid] = dict(observation, price=_number(price))
    return result


def _cash(state):
    return {c['account_id']: c['amount'] for c in state['cash_balances']}


def generate(ledger, client, target_id, as_of=None, prices=None, name=None, rates=None, version=None):
    """Retirement-first sales, conservative taxable budgets, then same-account buys.

    Budgets cap positive ST and LT realizations independently; losses do not
    increase budgets. This is deliberately conservative, not global optimization.
    """
    as_of = date.fromisoformat(as_of) if as_of else date.today()
    state = ledger.planning_state()
    household_currency(state)
    target = target_show(ledger, target_id, version=version)
    target = {k: v for k, v in target.items() if k != 'versions'}
    constraints = target['planning_constraints']
    working = copy.deepcopy(state)
    accounts = {a['id']: a for a in state['accounts']}
    securities = {s['id']: s for s in state['securities']}
    warnings, actions = [], []
    observations = _prices(state, target, {} if prices is None else prices, as_of, warnings)
    for p in working['positions']:
        source = p.get('source_timestamp')
        if decimal(p['quantity']) > 0 and (not source or (as_of - date.fromisoformat(source[:10])).days > constraints['price_max_age_days']):
            warnings.append(f"{p['id']}: stale or unknown source quantity freshness; verify holdings separately from quotes")
        observation = observations.get(p['security_id'])
        if observation:
            p['price'] = observation['price']
            p['market_value'] = _number(decimal(p['quantity']) * decimal(p['price']))
    baseline = copy.deepcopy(working)
    initial = allocation_diff(baseline, target)
    total = decimal(initial['total_value'])
    if total <= 0:
        raise DomainError('Planning requires a positive known household value', 3)
    initial_cash = _cash(working)
    cash_by_account = {account: decimal(amount) for account, amount in initial_cash.items()}
    household_cash_value = sum(cash_by_account.values(), ZERO)
    current_values = {row['security_id']: decimal(row['current_value'])
                      for row in initial['allocations']}
    target_values = {row['security_id']: decimal(row['target_value'])
                     for row in initial['allocations']}
    positions = {(p['account_id'], p['security_id']): p for p in working['positions']}
    tolerance_value = constraints_decimal(constraints, 'target_tolerance') * total
    eligible = constraints['eligible_accounts']
    permitted = constraints['permitted_securities']
    floors = constraints['cash_minimums']
    if not eligible:
        warnings.append('Account trading eligibility is unknown; no accounts eligible for planning')
    for account_id in eligible:
        if account_id not in accounts:
            raise DomainError('Planning account no longer exists', 3)
        if account_id not in permitted:
            warnings.append(f'{account_id}: permitted investments unknown; account excluded')
        if account_id not in initial_cash:
            warnings.append(f'{account_id}: cash unknown; account excluded')
        elif decimal(initial_cash[account_id]) < decimal(floors.get(account_id, '0')):
            warnings.append(f'{account_id}: current cash is below the required minimum')
    if set(accounts) - set(initial_cash):
        warnings.append('Household cash is incomplete; totals exclude unknown balances')
    for a in state['accounts']:
        snapshots = [s for s in state['snapshots'] if s['account']['id'] == a['id']]
        if not snapshots or not max(snapshots, key=lambda s: s['imported_at']).get('source_timestamp'):
            warnings.append(f"{a['id']}: source snapshot freshness unknown")
    budgets = {term: decimal(constraints[key]) if constraints[key] is not None else None
               for term, key in [('SHORT_TERM', 'short_term_gain_budget'), ('LONG_TERM', 'long_term_gain_budget')]}
    used_gains = {term: ZERO for term in budgets}

    def increment(account_id, sid):
        return decimal(constraints['trade_increments'].get(account_id, {}).get(sid, '1'))

    def allowed(account_id, sid, position=None):
        if account_id not in eligible or account_id not in permitted or account_id not in initial_cash:
            return False
        if accounts[account_id]['tax_status'] not in {'TAXABLE', 'TAX_DEFERRED', 'TAX_FREE'}:
            warnings.append(f'{account_id}: account tax classification unresolved')
            return False
        if sid not in permitted[account_id]:
            warnings.append(f'{account_id}/{sid}: investment not permitted')
            return False
        if position and position['id'] in constraints['excluded_positions']:
            warnings.append(f'{account_id}/{sid}: position excluded from trading')
            return False
        if securities[sid]['asset_type'] not in SUPPORTED:
            warnings.append(f'{sid}: individual bond or unsupported asset excluded from automatic trades')
            return False
        return sid in observations

    def apply_action(action):
        nonlocal household_cash_value
        account_id, sid = action['account_id'], action['security']
        key = (account_id, sid)
        previous = positions.get(key)
        previous_value = decimal(previous['market_value']) if previous else ZERO
        _, change = activity_change_inplace(working, action)
        # The shared accounting engine appends a position only for a new holding.
        p = previous if previous is not None else working['positions'][-1]
        positions[key] = p
        p.update(price=action['price'], market_value=_number(decimal(p['quantity']) * decimal(action['price'])),
                 as_of=as_of.isoformat())
        current_values[sid] = current_values.get(sid, ZERO) + decimal(p['market_value']) - previous_value
        cash_delta = decimal(change['cash_change'])
        cash_by_account[account_id] = decimal(change['cash_after'])
        household_cash_value += cash_delta
        current_values['CASH'] = household_cash_value
        actions.append(action)

    # Deterministic account preference minimizes taxable realizations first.
    candidates = sorted(list(working['positions']), key=lambda p: (
        accounts[p['account_id']]['tax_status'] == 'TAXABLE', p['account_id'], p['security_id']))
    for original in candidates:
        account_id, sid = original['account_id'], original['security_id']
        current = positions[(account_id, sid)]
        overweight = current_values[sid] - target_values[sid]
        if overweight <= tolerance_value or decimal(current['quantity']) <= 0:
            continue
        if not allowed(account_id, sid, current):
            continue
        price = decimal(observations[sid]['price'])
        step = increment(account_id, sid)
        quantity = _floor(min(decimal(current['quantity']), overweight / price), step)
        if quantity <= 0:
            continue
        base = dict(type='SELL', account_id=account_id, security=sid, price=_number(price),
                    date=as_of.isoformat(), fee='0')
        if accounts[account_id]['tax_status'] != 'TAXABLE':
            apply_action(dict(base, quantity=_number(quantity)))
            continue
        selection = analyze(working, account_id, sid, _number(quantity), _number(price),
                            as_of.isoformat(), method='MIN_TAX' if rates else 'HIFO', rates=rates)
        if selection['status'] == 'INSUFFICIENT_DATA':
            warnings.append(f'{account_id}/{sid}: lot/basis or source state unresolved; taxable sale excluded')
            continue
        if selection['tax_data_completeness']['household_history'] != 'COMPLETE':
            warnings.append(f'{account_id}: household tax history incomplete')
        # One action per exact lot permits explicit allocation and exact budget trimming.
        for lot in selection['selected_lots']:
            qty = _floor(decimal(lot['quantity']), step)
            unit_gain = decimal(lot['gain_loss']) / decimal(lot['quantity'])
            term = lot['term']
            if unit_gain > 0 and budgets[term] is not None:
                capacity = max(ZERO, budgets[term] - used_gains[term])
                limited = _floor(min(qty, capacity / unit_gain), step)
                if limited < qty:
                    warnings.append(f'{term}: realized gain budget limits taxable sale')
                qty = limited
            if qty <= 0:
                continue
            action = dict(base, quantity=_number(qty), method='SPECIFIC', lot_ids=[lot['id']],
                          lot_allocations=[{'lot_id': lot['id'], 'quantity': _number(qty)}])
            apply_action(action)
            used_gains[term] += max(ZERO, unit_gain * qty)

    # Buy only with known same-account cash, respecting household cash target and floors.
    desired_cash = total * decimal(target['target_allocations'].get('CASH', '0'))
    for sid in sorted(target['target_allocations']):
        if sid == 'CASH' or decimal(target['target_allocations'][sid]) <= 0:
            continue
        for account_id in sorted(eligible, key=lambda a: (accounts[a]['tax_status'] == 'TAXABLE', a)):
            underweight = target_values[sid] - current_values.get(sid, ZERO)
            if underweight <= tolerance_value:
                break
            position = positions.get((account_id, sid))
            if not allowed(account_id, sid, position):
                continue
            account_cash = max(ZERO, cash_by_account[account_id] - decimal(floors.get(account_id, '0')))
            household_cash = max(ZERO, household_cash_value - desired_cash)
            price = decimal(observations[sid]['price'])
            qty = _floor(min(underweight, account_cash, household_cash) / price, increment(account_id, sid))
            if qty > 0:
                apply_action(dict(type='BUY', account_id=account_id, security=sid, quantity=_number(qty),
                                  price=_number(price), date=as_of.isoformat(), fee='0'))
            elif account_cash <= 0:
                warnings.append(f'{account_id}/{sid}: insufficient cash after account minimum')

    ro_client = readonly_client(client)
    if actions:
        simulation = simulate(baseline, ro_client, actions, rates=rates)
        final = simulation['hypothetical_state']
        tax_analysis = {key: simulation[key] for key in
                        ('realized_gain_loss', 'short_term_gain_loss', 'long_term_gain_loss', 'estimated_tax_effect')}
        tax_analysis['analyses'] = simulation['tax_analyses']
        exposures = {'before': simulation['before_exposure'], 'after': simulation['after_exposure'],
                     'changes': simulation['exposure_changes']}
        warnings.extend(simulation['warnings'])
    else:
        final = baseline
        exp = exposure(baseline, ro_client)
        exposures = {'before': exp, 'after': exp, 'changes': []}
        tax_analysis = dict(realized_gain_loss='0', short_term_gain_loss='0', long_term_gain_loss='0',
                            estimated_tax_effect='0' if rates else None, analyses=[])
    proposed = allocation_diff(final, target)
    final_values = {row['security_id']: decimal(row['current_value'])
                    for row in proposed['allocations']}
    final_cash = {account: decimal(amount) for account, amount in _cash(final).items()}
    if final_values != current_values or final_cash != cash_by_account or decimal(proposed['total_value']) != total:
        raise DomainError('Inconsistent authoritative simulation and incremental planning balances', 3)
    tolerance = constraints_decimal(constraints, 'target_tolerance')
    remaining = any(abs(decimal(r['difference_weight'])) > tolerance for r in proposed['allocations'])
    if remaining:
        warnings.append('Target cannot be fully achieved under known constraints, cash and trade increments')
    for analysis in tax_analysis['analyses']:
        if analysis.get('potential_wash_sale_conflict'):
            warnings.append('Potential household wash-sale conflict requires human review')
    # Qualitative exposure limitations alone do not turn known retirement trades into unknown tax data.
    critical = bool(remaining or any(any(word in w.lower() for word in
                    ('unknown', 'unresolved', 'stale', 'conflict', 'incomplete', 'below the required'))
                    for w in warnings))
    latest = {}
    for snap in state['snapshots']:
        account_id = snap['account']['id']
        if account_id not in latest or snap['imported_at'] > latest[account_id]['imported_at']:
            latest[account_id] = snap
    plan = dict(id=str(uuid.uuid4()), name=name or target['name'], target_version_id=target['version_id'],
        target=target, source_snapshot_ids=[latest[a]['id'] for a in sorted(latest)],
        source_snapshot_dates={a: s.get('source_timestamp') for a, s in latest.items()},
        source_state_hash=state_hash(state), source_state=state,
        created_at=datetime.now(timezone.utc).isoformat(), as_of=as_of.isoformat(),
        market_data_as_of={sid: o['as_of'] for sid, o in observations.items()},
        assumptions={'prices': observations, 'tax_rates': rates, 'planning_constraints': constraints,
                     'algorithm': 'Retirement first; known lots; positive ST/LT gain caps; same-account cash; deterministic heuristic, not globally optimal',
                     'price_basis': 'Hypothetical marks supplied or accepted dated snapshots; actual prices unchanged',
                     'fees': 'Zero assumed for generated trades; confirm broker fees before acting',
                     'gain_budget_policy': 'Positive realizations capped separately; losses do not increase budgets',
                     'cash_return': 'Zero in hypothetical historical risk; no performance forecast'},
        proposed_actions=actions, tax_analysis=tax_analysis, exposure_analysis=exposures,
        current_allocation=initial, proposed_allocation=proposed,
        remaining_target_drift=proposed['allocations'], cash_before=initial_cash, cash_after=_cash(final),
        turnover=_number(sum((decimal(a['quantity']) * decimal(a['price']) for a in actions), ZERO)),
        trade_count=len(actions), warnings=list(dict.fromkeys(warnings)),
        status='REVIEW_REQUIRED' if critical else 'READY_FOR_HUMAN_REVIEW')
    from invest.plan_storage import save_plan
    save_plan(ledger, plan)
    return plan


def constraints_decimal(constraints, key):
    return decimal(constraints[key])


def persisted(ledger, plan_id):
    from invest.plan_storage import load_plan
    return load_plan(ledger, plan_id)


def show(ledger, plan_id):
    plan = persisted(ledger, plan_id)
    if plan['source_state_hash'] != state_hash(ledger.planning_state()):
        return dict(plan, status='STALE', generated_status=plan['status'])
    return plan


SUMMARY_FIELDS = ('id', 'name', 'target_version_id', 'created_at', 'as_of', 'status',
                  'generated_status', 'trade_count', 'turnover', 'tax_summary', 'drift_summary',
                  'warning_count', 'warnings_preview')


def plan_summary(plan, current_state_hash=None):
    """Summarize saved metrics without recalculating financial analysis or writing state."""
    original_status = plan.get('generated_status', plan.get('status'))
    status = plan.get('status')
    if current_state_hash is not None and plan.get('source_state_hash') != current_state_hash:
        status = 'STALE'
    tax = plan.get('tax_analysis') or {}
    drift = plan.get('remaining_target_drift') or []
    differences = [abs(decimal(row['difference_weight'])) for row in drift
                   if row.get('difference_weight') is not None]
    tolerance = ((plan.get('target') or {}).get('planning_constraints') or {}).get('target_tolerance')
    warnings = plan.get('warnings') or []
    return dict(
        **{key: plan.get(key) for key in ('id', 'name', 'target_version_id', 'created_at',
                                         'as_of', 'trade_count')},
        status=status, generated_status=original_status,
        storage_identity=plan.get('storage_identity'),
        turnover=str(plan['turnover']) if plan.get('turnover') is not None else None,
        tax_summary={key: str(tax[key]) if tax.get(key) is not None else None for key in
                     ('short_term_gain_loss', 'long_term_gain_loss', 'estimated_tax_effect')},
        drift_summary=dict(maximum_absolute_weight_drift=_number(max(differences)) if differences else None,
                           positions_outside_tolerance=sum(value > decimal(tolerance) for value in differences)
                           if tolerance is not None else None),
        warning_count=plan.get('_warning_count', len(warnings)), warnings_preview=warnings[:5])


def _projected(ledger, plan_ids=None):
    from invest.plan_storage import summaries
    return summaries(ledger, plan_ids)


def list_plans(ledger):
    plans = _projected(ledger)
    current = state_hash(ledger.planning_state()) if plans else None
    return {'plans': [dict(plan['summary'], status='STALE' if plan['source_state_hash'] != current else plan['summary']['generated_status']) for plan in plans]}


def compare(ledger, *plan_ids):
    if len(plan_ids) < 2:
        raise DomainError('Compare at least two plans')
    selected = {p['id']: p for p in _projected(ledger, plan_ids)}
    if any(pid not in selected for pid in plan_ids):
        raise DomainError('Plan does not exist')
    plans = [selected[pid] for pid in plan_ids]
    current = state_hash(ledger.planning_state())
    source_same = len({p['source_state_hash'] for p in plans}) == 1
    prices_same = len({p['price_assumptions_hash'] for p in plans}) == 1
    tax_same = len({p['tax_assumptions_hash'] for p in plans}) == 1
    warnings = []
    if not source_same:
        warnings.append('Plans use different source snapshots; comparisons are not a common baseline')
    if not prices_same:
        warnings.append('Plans use different price assumptions')
    if not tax_same:
        warnings.append('Plans use different configured tax rates')
    date_same = len({p['as_of'] for p in plans}) == 1
    if not date_same:
        warnings.append('Plans use different analysis dates')
    return dict(plans=[dict(p['summary'], status='STALE' if p['source_state_hash'] != current else p['summary']['generated_status']) for p in plans],
                same_source_snapshot=source_same, same_price_assumptions=prices_same,
                same_tax_assumptions=tax_same, same_analysis_date=date_same, warnings=warnings,
                ranking=None)
