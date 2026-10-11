"""Compact immutable plan retrieval, summaries and scenario entry point."""


from invest.financial_state import state_hash as state_hash
from invest.models import DomainError, decimal
from invest.scenarios import simulate as simulate


def _number(value):
    return format(value.normalize(), 'f') if value else '0'


def generate(ledger, client, target_id, as_of=None, prices=None, name=None, rates=None, version=None):
    from invest.proposal_generation import generate as propose_scenario

    return propose_scenario(ledger, client, target_id, as_of, prices, name, rates, version,
                            simulator=simulate, fingerprint=state_hash)


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
    result = dict(
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
    result.update({key: plan[key] for key in ('mode', 'data_environment', 'issues') if key in plan})
    return result


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
