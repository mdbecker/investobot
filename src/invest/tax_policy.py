"""Read-only annual positive-tax allowance and household loss-sale review."""

from datetime import date, timedelta
from decimal import Decimal, localcontext

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictBool

from invest.models import DomainError, decimal

ZERO = Decimal('0')


class AnnualTaxPolicy(BaseModel):
    """An attested household policy; missing facts remain explicitly unknown."""

    model_config = ConfigDict(extra='forbid')
    year: int = Field(ge=1900, le=9999)
    annual_allowance: Decimal | None = Field(default=None, ge=0, allow_inf_nan=False)
    short_term_rate: Decimal | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    long_term_rate: Decimal | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    currency: str | None = None
    taxable_history_complete: StrictBool | None = None
    covered_account_ids: list[str] | None = None
    data_environment: str | None = Field(default=None, pattern='^(REAL|SYNTHETIC)$')
    source: str | None = None
    as_of: AwareDatetime | None = None
    proposed_positive_tax_cost: Decimal | None = Field(default=None, ge=0, allow_inf_nan=False)
    id: str | None = None


def _plain(value):
    if value is None:
        return None
    text = format(value, 'f')
    if '.' in text:
        text = text.rstrip('0').rstrip('.')
    return '0' if text in {'', '-0'} else text


def _issue(code, message, *ids, calculation=True, proposal=True):
    return {'code': code, 'severity': 'ERROR' if calculation else 'WARNING',
            'affected_ids': list(ids), 'blocks_calculation': calculation,
            'blocks_proposal': proposal, 'blocks_execution_review': True, 'message': message}


def _result(issues, *, environment=None, as_of=None, **values):
    blocked = any(i['blocks_calculation'] for i in issues)
    return {'status': 'BLOCKED' if blocked else 'REVIEW_REQUIRED' if issues else 'AVAILABLE',
            'issues': issues, 'coverage': {}, 'as_of': as_of, 'sources': [],
            'manifest_ids': [], 'assumptions': [], 'environment': environment, **values}


def _day(value):
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _precision(values):
    # Decimal operations, including fees/rates, must preserve unusually precise inputs.
    return max(80, sum(len(format(value, 'f')) for value in values) + 32)


def _sale_facts(activity):
    """Use immutable execution and allocation facts, never remaining current lots."""
    quantity, price, fee = (decimal(activity[key]) for key in ('quantity', 'price', 'fee'))
    allocations = activity.get('lot_allocations')
    if quantity <= 0 or price < 0 or fee < 0 or not allocations:
        raise ValueError('Executed sale quantities, prices, fees and allocations are required')
    if len({a['lot_id'] for a in allocations}) != len(allocations):
        raise ValueError('Executed allocations contain duplicate lots')
    facts = []
    for allocation in allocations:
        used = decimal(allocation['quantity'])
        basis = decimal(allocation['basis_removed'])
        allocated_fee = decimal(allocation['fee_allocated'])
        term = allocation['term']
        if used <= 0 or basis < 0 or allocated_fee < 0 or term not in {'SHORT_TERM', 'LONG_TERM'}:
            raise ValueError('Executed allocation basis, fees and holding term are unresolved')
        with localcontext() as context:
            context.prec = _precision([used, price, basis, allocated_fee])
            gain = used * price - basis - allocated_fee
        if allocation.get('realized_gain') is not None and decimal(allocation['realized_gain']) != gain:
            raise ValueError('Accepted realized gain conflicts with execution and allocated basis')
        facts.append({'lot_id': allocation['lot_id'], 'quantity': used, 'basis': basis,
                      'fee': allocated_fee, 'term': term, 'gain': gain})
    with localcontext() as context:
        context.prec = _precision([quantity, fee, *[n for f in facts for n in
                                                   (f['quantity'], f['basis'], f['fee'], f['gain'])]])
        if sum((f['quantity'] for f in facts), ZERO) != quantity:
            raise ValueError('Accepted lot allocations do not equal executed sale quantity')
        if sum((f['fee'] for f in facts), ZERO) != fee:
            raise ValueError('Accepted fee allocations do not equal the execution fee')
    return facts


def annual_budget(state, policy, proposed_positive_tax_cost='0'):
    """Conservative USD tax-year headroom from confirmed immutable sale facts."""
    policy = AnnualTaxPolicy.model_validate(policy)
    proposed = decimal(proposed_positive_tax_cost)
    if proposed < 0:
        raise DomainError('Proposed positive tax cost must be nonnegative')
    issues, sales, facts = [], [], []
    accounts = {a['id']: a for a in state.get('accounts', [])}
    taxable = {key for key, account in accounts.items() if account.get('tax_status') == 'TAXABLE'}
    cutoff = policy.as_of.date() if policy.as_of else None
    if policy.currency != 'USD':
        issues.append(_issue('UNSUPPORTED_TAX_CURRENCY', 'Annual tax allowance requires explicit USD units'))
    if policy.annual_allowance is None:
        issues.append(_issue('UNKNOWN_ANNUAL_TAX_ALLOWANCE', 'Approve an explicit annual tax-dollar allowance'))
    if policy.short_term_rate is None or policy.long_term_rate is None:
        issues.append(_issue('UNKNOWN_TAX_RATE', 'Both short- and long-term marginal rates are required'))
    if policy.taxable_history_complete is not True:
        issues.append(_issue('INCOMPLETE_TAXABLE_HISTORY', 'Attest coverage of all taxable accounts and earlier sales'))
    if policy.covered_account_ids is not None and not taxable <= set(policy.covered_account_ids):
        issues.append(_issue('INCOMPLETE_TAXABLE_HISTORY', 'Policy account coverage omits a taxable account',
                             *sorted(taxable - set(policy.covered_account_ids))))
    if not policy.source or not policy.source.strip() or cutoff is None:
        issues.append(_issue('UNKNOWN_TAX_HISTORY_ATTESTATION', 'A sourced timestamped history attestation is required'))
    if policy.data_environment is None:
        issues.append(_issue('UNKNOWN_DATA_ENVIRONMENT', 'Tax policy must identify its data environment'))
    for account_id, account in accounts.items():
        if account.get('active', True) and account.get('tax_status', 'OTHER') == 'OTHER':
            issues.append(_issue('UNKNOWN_ACCOUNT_TAX_STATUS', 'Classify the account before household tax budgeting', account_id))
        if account_id in taxable and account.get('currency') != 'USD':
            issues.append(_issue('UNSUPPORTED_TAX_CURRENCY', 'Taxable account currency is not known USD', account_id))
    seen = set()
    for activity in state.get('activities', []):
        if activity.get('type') != 'SELL':
            continue
        account_id = activity.get('account_id')
        if account_id not in accounts:
            issues.append(_issue('UNKNOWN_ACTIVITY_ACCOUNT', 'Confirmed sale account does not resolve', account_id))
            continue
        if account_id not in taxable:
            continue
        identifier = activity.get('activity_id')
        if not identifier or identifier in seen:
            issues.append(_issue('ACTIVITY_ID_CONFLICT', 'Confirmed sales require unique immutable activity IDs', identifier))
            continue
        seen.add(identifier)
        try:
            executed = _day(activity['date'])
        except (ValueError, KeyError, TypeError):
            issues.append(_issue('UNKNOWN_ACTIVITY_DATE', 'Confirmed sale date is unresolved', identifier))
            continue
        if executed.year != policy.year or (cutoff is not None and executed > cutoff):
            continue
        if activity.get('currency', accounts[account_id].get('currency')) != 'USD':
            issues.append(_issue('UNSUPPORTED_TAX_CURRENCY', 'Sale currency is not known USD', identifier))
            continue
        if activity.get('data_environment') is None:
            issues.append(_issue('UNKNOWN_DATA_ENVIRONMENT',
                'Confirmed sale must retain accepted data-environment provenance', identifier))
            continue
        if activity.get('data_environment') != policy.data_environment:
            issues.append(_issue('MIXED_DATA_ENVIRONMENT', 'Policy and confirmed sale environments differ', identifier))
            continue
        try:
            sale_facts = _sale_facts(activity)
        except (ValueError, KeyError, TypeError, DomainError):
            issues.append(_issue('UNKNOWN_REALIZED_SALE_FACTS',
                'Accepted allocated basis, fee and term are required; current lots cannot reconstruct them', identifier))
            continue
        facts.extend(sale_facts)
        sales.append(identifier)
    rates = {'SHORT_TERM': policy.short_term_rate, 'LONG_TERM': policy.long_term_rate}
    numbers = [proposed, *[value for value in rates.values() if value is not None],
               *[fact['gain'] for fact in facts]]
    if policy.annual_allowance is not None:
        numbers.append(policy.annual_allowance)
    with localcontext() as context:
        context.prec = _precision(numbers)
        signed = sum((f['gain'] for f in facts), ZERO)
        costs = {term: sum((max(ZERO, f['gain']) * rate for f in facts if f['term'] == term), ZERO)
                 if rate is not None else None for term, rate in rates.items()}
        reliable = not any(i['blocks_calculation'] for i in issues)
        consumption = sum(costs.values(), ZERO) if reliable else None
        remaining = max(ZERO, policy.annual_allowance - consumption) if reliable else None
        if remaining is not None and proposed > remaining:
            issues.append(_issue('ANNUAL_TAX_BUDGET_EXCEEDED',
                'Proposed positive estimated tax cost exceeds remaining annual headroom', calculation=False))
    output = _result(issues, environment=policy.data_environment,
        as_of=policy.as_of.isoformat() if policy.as_of else None,
        year=policy.year, currency=policy.currency, annual_allowance=_plain(policy.annual_allowance),
        year_to_date_consumption=_plain(consumption), remaining_allowance=_plain(remaining),
        short_term_positive_tax_cost=_plain(costs['SHORT_TERM']) if reliable else None,
        long_term_positive_tax_cost=_plain(costs['LONG_TERM']) if reliable else None,
        realized_signed_net_gain=_plain(signed) if reliable else None,
        known_realized_signed_net_gain=_plain(signed), proposed_positive_tax_cost=_plain(proposed),
        gain_realizing_sale_allowed=reliable and remaining is not None and proposed <= remaining,
        cash_only_proposal_allowed=True, confirmed_sale_ids=sales,
        limitation='Conservative planning allowance, not a prediction of final tax liability')
    output['coverage'] = {'taxable_history_complete': policy.taxable_history_complete is True,
                          'taxable_account_ids': sorted(taxable), 'known_confirmed_sale_count': len(sales),
                          'sale_facts_complete': not any(i['code'] == 'UNKNOWN_REALIZED_SALE_FACTS' for i in issues)}
    output['sources'] = [policy.source] if policy.source else []
    output['assumptions'] = {'losses_replenish_allowance': False, 'saved_proposals_consume_allowance': False,
                             'short_term_rate': _plain(policy.short_term_rate),
                             'long_term_rate': _plain(policy.long_term_rate)}
    if any(issue['code'] == 'ANNUAL_TAX_BUDGET_EXCEEDED' for issue in issues):
        output['status'] = 'BLOCKED'
    return output


class HarvestReviewPolicy(BaseModel):
    """Explicit household review scope; no implicit replacement permission."""

    model_config = ConfigDict(extra='forbid')
    loss_sale_date: date
    security: str
    spouse_history_complete: StrictBool | None = None
    outside_account_history_complete: StrictBool | None = None
    dividend_reinvestment_history_complete: StrictBool | None = None
    data_environment: str = Field(pattern='^(REAL|SYNTHETIC)$')
    replacement: dict | None = None
    scheduled_acquisitions: list[dict] = Field(default_factory=list)
    price_observations: dict[str, dict] = Field(default_factory=dict)


def harvest_plan(state, policy, as_of):
    """Inspect known household acquisitions; legal outcomes remain human review."""
    if isinstance(policy, dict) and 'harvest_review' in policy:
        from invest.harvest_proposals import conditional_harvest

        return conditional_harvest(state, policy, as_of)
    policy = HarvestReviewPolicy.model_validate(policy)
    observed = _day(as_of)
    sale = policy.loss_sale_date
    issues, conflicts, candidates = [], [], []
    securities = state.get('securities', [])
    matched = [s for s in securities if policy.security in {
        s.get('id'), s.get('ticker'), s.get('cusip'), s.get('isin'), s.get('figi')}]
    if len(matched) != 1:
        return _result([_issue('SECURITY_IDENTITY_CONFLICT',
            'Loss-sale security must resolve to one canonical identity', policy.security)],
            environment=policy.data_environment, as_of=observed.isoformat(),
            wash_review={'conflicts': []}, replacement_candidates=[],
            guaranteed_tax_savings=None, legal_wash_sale_safe=None)
    security = matched[0]
    accounts = {a['id']: a for a in state.get('accounts', [])}
    if policy.spouse_history_complete is not True or policy.outside_account_history_complete is not True:
        issues.append(_issue('UNKNOWN_OUTSIDE_ACCOUNT_HISTORY',
            'Untracked spouse or outside-account acquisitions require review', calculation=False))
    if policy.dividend_reinvestment_history_complete is not True:
        issues.append(_issue('UNKNOWN_DIVIDEND_REINVESTMENTS',
            'Automatic dividend reinvestment coverage is not attested', calculation=False))
    start, end = sale - timedelta(days=30), sale + timedelta(days=30)

    def matches(item):
        if item.get('security_id') is not None:
            return item['security_id'] == security['id']
        return item.get('security') in {security['id'], security.get('ticker')}

    acquisitions = []
    activity_lot_refs = set()
    for event in state.get('activities', []):
        if event.get('type') in {'BUY', 'DIVIDEND_REINVESTMENT'} and matches(event):
            acquisitions.append({'activity_id': event.get('activity_id'),
                'account_id': event.get('account_id'), 'date': event.get('date'),
                'source': event.get('source'), 'kind': event['type'],
                'data_environment': event.get('data_environment')})
            activity_lot_refs.update(a.get('lot_id') for a in event.get('lot_allocations') or [])
    for lot in state.get('lots', []):
        if matches(lot) and lot['id'] not in activity_lot_refs:
            acquisitions.append({'lot_id': lot['id'], 'account_id': lot.get('account_id'),
                'date': lot.get('acquisition_date'), 'source': lot.get('identity_source'),
                'kind': 'OBSERVED_ACQUISITION', 'data_environment': lot.get('data_environment')})
    for scheduled in policy.scheduled_acquisitions:
        if not scheduled.get('source') or not scheduled.get('activity_id'):
            issues.append(_issue('UNVERIFIED_SCHEDULED_ACQUISITION',
                'Future acquisition evidence requires an explicit ID and source', calculation=False))
            continue
        if matches(scheduled):
            acquisitions.append({**scheduled, 'kind': 'EXPLICIT_SCHEDULED_ACQUISITION'})
    for acquisition in acquisitions:
        try:
            acquired = _day(acquisition['date'])
        except (ValueError, TypeError, KeyError):
            issues.append(_issue('UNKNOWN_ACQUISITION_DATE',
                'An acquisition date is missing; its wash window cannot be excluded',
                acquisition.get('account_id'), calculation=False))
            continue
        if not start <= acquired <= end:
            continue
        account = accounts.get(acquisition.get('account_id'))
        if account is None:
            issues.append(_issue('UNKNOWN_ACQUISITION_ACCOUNT',
                'Household acquisition account does not resolve', calculation=False))
            continue
        conflict = {'activity_id': None, 'lot_id': None, **acquisition,
                    'date': acquired.isoformat(), 'security_id': security['id'],
                    'tax_status': account.get('tax_status', 'OTHER')}
        conflicts.append(conflict)
    if conflicts:
        ira = [c for c in conflicts if c['tax_status'] in {'TAX_FREE', 'TAX_DEFERRED'}]
        issues.append(_issue('HOUSEHOLD_IRA_ACQUISITION_CONFLICT' if ira else 'POTENTIAL_WASH_SALE_CONFLICT',
            'Known household acquisitions fall within thirty days of the proposed loss sale',
            *sorted({c['account_id'] for c in conflicts}), calculation=False))
    replacement = policy.replacement
    if replacement:
        if replacement.get('substantially_identical') is not False:
            issues.append(_issue('SUBSTANTIAL_IDENTITY_REVIEW',
                'Substantial identity is unresolved; similarity cannot establish legal safety', calculation=False))
        if replacement.get('approved_for_purchase') is not True:
            issues.append(_issue('REPLACEMENT_PERMISSION_REQUIRED',
                'Replacement purchase permission must be explicitly approved in the saved policy', calculation=False))
        candidates.append({**replacement, 'legal_wash_sale_safe': None,
                           'guaranteed_tax_savings': None})
    # Gross observed loss is evidence only; unknown fees/rates prevent a net tax estimate.
    loss_lots = []
    for position in state.get('positions', []):
        if not matches(position) or accounts.get(position.get('account_id'), {}).get('tax_status') != 'TAXABLE':
            continue
        inventory = [lot for lot in state.get('lots', []) if matches(lot)
                     and lot.get('account_id') == position.get('account_id')]
        try:
            values = [decimal(lot['remaining_quantity']) for lot in inventory]
            quantity = decimal(position['quantity'])
            with localcontext() as context:
                context.prec = _precision([quantity, *values])
                represented = sum(values, ZERO)
            if represented != quantity or position.get('lot_state') == 'UNRESOLVED':
                raise ValueError('Whole-position lot consistency is unknown')
            price = decimal(position['price'])
        except (ValueError, KeyError, TypeError, DomainError):
            issues.append(_issue('UNRESOLVED_TAXABLE_LOTS',
                'Whole-position quantities and a supported mark are required for a loss estimate',
                position.get('account_id')))
            continue
        for lot in inventory:
            if decimal(lot['remaining_quantity']) <= 0:
                continue
            try:
                basis = decimal(lot['remaining_adjusted_basis'])
                quantity = decimal(lot['remaining_quantity'])
                with localcontext() as context:
                    context.prec = _precision([basis, quantity, price])
                    gross_gain = quantity * price - basis
            except (ValueError, KeyError, TypeError, DomainError):
                issues.append(_issue('UNKNOWN_REMAINING_BASIS',
                    'Broker-adjusted remaining basis is required; do not reconstruct it', lot['id']))
                continue
            if gross_gain < 0:
                loss_lots.append({'lot_id': lot['id'], 'account_id': lot['account_id'],
                    'security_id': security['id'], 'remaining_quantity': _plain(quantity),
                    'remaining_adjusted_basis': _plain(basis),
                    'observed_gross_gain_loss': _plain(gross_gain), 'estimated_net_tax_effect': None})
    issues.append(_issue('HUMAN_WASH_SALE_REVIEW',
        'Human original-source and legal review remains required even without a known conflict', calculation=False))
    result = _result(issues, environment=policy.data_environment, as_of=observed.isoformat(),
        loss_sale_date=sale.isoformat(), security_id=security['id'], loss_lots=loss_lots,
        wash_review={'window_start': start.isoformat(), 'window_end': end.isoformat(),
                     'conflicts': sorted(conflicts, key=lambda c: (c['date'], c['account_id'],
                         c.get('activity_id') or c.get('lot_id') or ''))},
        replacement_candidates=candidates, proposed_actions=[], guaranteed_tax_savings=None,
        legal_wash_sale_safe=None)
    result['coverage'] = {'spouse_history_complete': policy.spouse_history_complete is True,
        'outside_account_history_complete': policy.outside_account_history_complete is True,
        'dividend_reinvestment_history_complete': policy.dividend_reinvestment_history_complete is True}
    return result
