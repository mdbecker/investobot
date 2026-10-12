"""Independent exact invariants; application calculations are never the oracle."""

import hashlib
import json
from decimal import Decimal
from fractions import Fraction

NAMES = frozenset({'financial_conservation','position_lot_consistency','basis_conservation',
    'immutable_provenance','idempotent_replay','same_state_recomputation','row_order_equivalence',
    'supported_error_codes','atomic_rejection','no_look_ahead','no_invalid_trading',
    'vector_permission_filter','research_continuity','missing_data_propagation','recovery_equivalence',
    'immutable_reads'})


def registry():
    return sorted(NAMES)


def _number(value):
    if value is None or isinstance(value,(bool,float)):
        raise ValueError('Exact authoritative quantity is unknown or not a decimal string')
    return Fraction(Decimal(str(value)))


def financial_projection(state):
    """Compare authoritative facts by sourced identities, not generated observation IDs."""
    securities={row['id']:row.get('cusip') or row.get('isin') or row.get('figi') or row['ticker']
                for row in state.get('securities',[])}
    def identity(row):
        return (row.get('account_id'),securities.get(row.get('security_id'),row.get('security')))
    positions=sorted([(identity(row),str(_number(row['quantity'])),
                       str(_number(row['market_value'])),row.get('currency','USD'),
                       row.get('as_of')) for row in state.get('positions',[])],key=str)
    lots=sorted([(identity(row),row.get('source_lot_id'),str(_number(row['remaining_quantity'])),
                 str(_number(row['remaining_adjusted_basis'])),row.get('acquisition_date'),
                 row.get('identity_status'),row.get('identity_source'))
                for row in state.get('lots',[])],key=str)
    cash=sorted([(row['account_id'],str(_number(row['amount'])),row.get('currency','USD'))
                 for row in state.get('cash_balances',[])],key=str)
    accounts=sorted([(a['id'],a.get('currency'),a.get('tax_status'),a.get('data_environment'))
                     for a in state.get('accounts',[])],key=str)
    return {'positions':positions,'lots':lots,'cash':cash,'accounts':accounts}


def fingerprint(state):
    return hashlib.sha256(json.dumps(financial_projection(state),sort_keys=True).encode()).hexdigest()


def _total(state):
    if 'cash' in state:
        return _number(state['cash'])+sum((_number(p['quantity'])*_number(p['price'])
            for p in state.get('positions',[])),Fraction())
    currencies={r.get('currency','USD') for r in state.get('accounts',[])}
    if currencies!={'USD'}:
        raise ValueError('Independent USD oracle needs one verified currency')
    return sum((_number(p['market_value']) for p in state.get('positions',[])),Fraction()) + sum(
        (_number(c['amount']) for c in state.get('cash_balances',[])),Fraction())


def _consistency(state):
    failures=[]
    for p in state.get('positions',[]):
        matching=[l for l in state.get('lots',[]) if l['account_id']==p['account_id'] and
                  l['security_id']==p['security_id']]
        if sum((_number(l['remaining_quantity']) for l in matching),Fraction())!=_number(p['quantity']):
            failures.append('Remaining lot quantities differ from accepted position')
        if _number(p['quantity'])*_number(p['price'])!=_number(p['market_value']):
            failures.append('Accepted position price/quantity/value disagree')
    return failures


def check(name,before,after,result):
    """Unknown evidence fails explicitly; model narratives cannot establish correctness."""
    if name not in NAMES:
        return {'passed':False,'violations':['Unknown invariant ID']}
    violations=[]
    evidence=result.get('evidence',{})
    trace=result.get('operation_trace',[])
    try:
        if name=='financial_conservation':
            delta=evidence.get('cash_delta')
            if delta is None and before.get('activities')==after.get('activities'):
                delta='0'
            if _total(after)-_total(before)!=_number(delta):
                violations.append('Exact household total does not conserve the confirmed cash delta')
        elif name=='position_lot_consistency':violations.extend(_consistency(after))
        elif name=='basis_conservation':
            expected=evidence.get('initial_basis')
            actual=sum((_number(l['remaining_adjusted_basis']) for l in after['lots']),Fraction())
            if actual!=_number(expected):violations.append('Exact remaining adjusted basis was not conserved')
            tax_rows=evidence.get('tax_lots')
            if tax_rows is not None and sum((_number(l['cost_basis']) for l in tax_rows),Fraction())!=actual:
                violations.append('Tax output differs from independently summed remaining basis')
        elif name in {'immutable_reads','immutable_provenance'}:
            if fingerprint(before)!=fingerprint(after):violations.append('Read/recovery changed canonical financial provenance')
            if evidence.get('read_only') and evidence.get('before_canonical')!=evidence.get('after_canonical'):
                violations.append('Read changed persisted canonical rows')
        elif name=='idempotent_replay':
            replay=evidence.get('idempotent_replay')
            if not replay or replay['status']!='UNCHANGED' or replay['before']!=replay['after']:
                violations.append('Exact accepted input replay was not an unchanged no-op')
        elif name in {'same_state_recomputation','row_order_equivalence'}:
            proof=evidence.get(name)
            if not proof or proof['first']!=proof['second']:
                violations.append('Same facts recomputation/reordering changed substantive output')
        elif name=='supported_error_codes':
            if result.get('exit_code') not in {0,1,2,3,4}:violations.append('Unsupported actual process/domain exit code')
            if not trace:violations.append('Missing real execution trace')
        elif name=='atomic_rejection':
            rejected=[row for row in trace if row.get('exit_code')]
            if not rejected:violations.append('No actual rejected operation was observed')
            for row in rejected:
                if row['before_canonical']!=row['after_canonical']:
                    violations.append('Rejected operation partially wrote canonical rows')
        elif name=='missing_data_propagation':
            blocked=[r for r in trace if r.get('outcome')=='BLOCKED']
            if not blocked or not any(r.get('issues') for r in blocked):
                violations.append('Missing evidence did not propagate to a typed blocked outcome')
            if any(r.get('actionable') for r in blocked):violations.append('Incomplete data produced an actionable proposal')
        elif name=='no_invalid_trading':
            if result.get('observed_result')=='BLOCKED' and fingerprint(before)!=fingerprint(after):
                violations.append('Blocked proposal changed accepted financial facts')
            if evidence.get('missing_cash') and any(r.get('actionable') for r in trace):
                violations.append('Unknown cash funded an actionable proposal')
            if not evidence.get('plan_checked'):violations.append('No real planning evidence')
        elif name=='vector_permission_filter':
            corpus=evidence.get('corpus')
            matches=evidence.get('vector_matches')
            if corpus is None or matches is None:violations.append('No real vector/corpus evidence')
            else:
                index={r['chunk_id']:r for r in corpus}
                if not matches:violations.append('No permitted fixture match was retrieved')
                for row in matches:
                    item=index.get(row.get('chunk_id'))
                    if not item or item['permission']!='PERMITTED':violations.append('Denied/unknown source escaped retrieval filter')
                    elif row.get('source_url')!=item['source_url']:violations.append('Retrieved citation differs from accepted source')
        elif name=='recovery_equivalence':
            restored=evidence.get('restored_state')
            if restored is None or financial_projection(after)!=financial_projection(restored):
                violations.append('Verified restore differs from canonical financial facts')
        elif name=='no_look_ahead':
            observations=evidence.get('temporal_observations')
            if observations is None:violations.append('No temporal observations to verify')
            else:
                for row in observations:
                    if row['source_date']>row['decision_date']:violations.append('Future evidence used before its source date')
        elif name=='research_continuity':
            history=evidence.get('research_history')
            if history is None:violations.append('No immutable research history evidence')
            elif any(row['before']!=row['after'] for row in history):violations.append('Stored evidence was rewritten')
        else:violations.append('Required invariant implementation is absent')
    except (KeyError,TypeError,ValueError,ArithmeticError) as error:
        violations.append(f'Independent oracle evidence incomplete: {error}')
    return {'passed':not violations,'violations':violations}
