"""Bounded fixed synthetic operations; never consult a selected/private ledger."""

import copy
import hashlib
import json
from pathlib import Path

from benchmarks.financial_fixtures import DATE, build
from fuzz import oracles
from invest import backup, performance, search, tax
from invest.ledger import Ledger
from invest.models import DomainError
from invest.parsers.generic import parse_html
from invest.planning import propose


def _canonical(ledger):
    tables=['accounts','securities','positions','lots','cash_balances','activities','snapshots']
    value={table:ledger.rows(table) for table in tables}
    return hashlib.sha256(json.dumps(value,sort_keys=True,default=str).encode()).hexdigest()


def _projection(value):
    def walk(item):
        if isinstance(item,dict):
            return {k:walk(v) for k,v in sorted(item.items())
                    if k not in {'created_at','recorded_at','imported_at','updated_at'}}
        if isinstance(item,list):return [walk(v) for v in item]
        return item
    return walk(value)


def _html(snapshot,reverse=False,inconsistent=False):
    rows=list(snapshot['lots'])
    if reverse:rows.reverse()
    html=('<table><tr><th>Symbol</th><th>Quantity</th><th>Price</th><th>Market Value</th>'
          '<th>Cost Basis</th><th>Remaining Adjusted Basis</th><th>Acquisition Date</th>'
          '<th>Broker Lot ID</th><th>Asset Type</th></tr>')
    for index,lot in enumerate(rows):
        value='900' if inconsistent and index==0 else '500'
        html+=(f'<tr><td>{lot["security"]}</td><td>5</td><td>100</td><td>{value}</td>'
               f'<td>600</td><td>600</td><td>2024-01-01</td><td>{lot["source_lot_id"]}</td>'
               '<td>STOCK</td></tr>')
    html+='<tr><td>CASH</td><td></td><td></td><td>10000</td><td></td><td></td><td></td><td></td><td></td></tr></table>'
    return html


def execute(case,root):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    records=case['records']
    if not isinstance(records,int) or not 1<=records<=25000:
        raise ValueError('Fixture records outside fixed bounds')
    dimensions={'accounts':1,'positions':records,'lots':records*2,'accepted_snapshots':1,'saved_plans':20}
    fixture=build(root,dimensions)
    ledger=fixture.ledger
    before=copy.deepcopy(ledger.planning_state())
    evidence={'cash_delta':'0','initial_basis':str(records*1200),'read_only':False,
              'before_canonical':_canonical(ledger)}
    trace=[];candidate=None;outputs=[];first_error=None;blocked=False
    mutations=set(case.get('mutations',[]))
    try:
        if 'missing_cash_coverage' in mutations:
            with ledger.connection:
                for row in ledger.rows('cash_balances'):
                    ledger.put('cash_balances',row['id'],dict(row,as_of=None,source_timestamp=None))
                for row in ledger.rows('snapshots'):
                    ledger.connection.execute('DELETE FROM snapshot_observations WHERE id=?',(row['id'],))
                    ledger.put('snapshots',row['id'],dict(row,cash_known=False))
            before=copy.deepcopy(ledger.planning_state())
            evidence['before_canonical']=_canonical(ledger);evidence['missing_cash']=True
        if any(op['name']=='vector' for op in case['operations']):
            corpus=[]
            for index in range(records):
                text=f'fictional permitted passage {index}'
                permission='DENIED' if 'denied_source' in mutations and index==0 else 'PERMITTED'
                corpus.append(dict(chunk_id=f'chunk-{index}',document_id=f'document-{index}',text=text,
                    source_url=f'https://fictional.example/source/{index}',source_date='2026-10-09',
                    permission=permission,license='Reviewed fictional source rights',
                    data_environment='SYNTHETIC',content_hash=hashlib.sha256(text.encode()).hexdigest(),
                    offset_start=0,offset_end=len(text),vector=[1.0]+[0.0]*383,
                    model_id='fictional-fuzz-384',dimension=384))
            search.store_chunks(ledger.path,corpus,confirmed=True)
            evidence['corpus']=corpus
        for index,operation in enumerate(case['operations']):
            name=operation['name'];params=operation['params'];prior=_canonical(ledger)
            code=0;outcome='SUCCESS';issues=[];value=None
            try:
                if name=='import':
                    inconsistent=params.get('template')=='inconsistent_value' or 'inconsistent_position_value' in mutations
                    candidate=parse_html(_html(fixture.snapshots[0],
                        reverse='reverse_independent_rows' in mutations,inconsistent=inconsistent),
                        fixture.accounts[0],as_of=DATE,positions_complete=True,lots_complete=True,
                        data_environment='SYNTHETIC')
                    value=candidate
                    if inconsistent:evidence['invalid_candidate']=True
                elif name=='reconcile':
                    if candidate is None:raise DomainError('Import a candidate before reconciliation')
                    value=ledger.reconcile(candidate)
                elif name=='apply':
                    if candidate is None:raise DomainError('Import a candidate before acceptance')
                    value=ledger.apply(candidate)
                    if value['status']=='UNCHANGED':
                        evidence['idempotent_replay']={'status':'UNCHANGED','before':prior,'after':_canonical(ledger)}
                elif name=='activity':
                    if params.get('type')!='DEPOSIT':raise DomainError('Unsupported fixed activity operation')
                    event=dict(activity_id=f'fictional-activity-{index}',account_id=fixture.accounts[0],
                        type='CASH_DEPOSIT',amount=params['amount'],date=params['date'],
                        event_timestamp=params['date']+'T12:00:00Z',source='Reviewed fictional bank confirmation')
                    value=ledger.record_activity(event,yes=True)
                    from decimal import Decimal
                    evidence['cash_delta']=str(Decimal(evidence['cash_delta'])+Decimal(params['amount']))
                elif name=='query':
                    kind=params.get('kind')
                    if kind=='summary':value=ledger.summary()
                    elif kind=='performance':
                        payload={'from_date':'2025-10-10','to_date':DATE,'scope':'HOUSEHOLD',
                            'data_environment':'SYNTHETIC','cash_flow_history_complete':True,
                            'checkpoints':[{'date':'2025-10-10','value':'1000','complete':True},
                                           {'date':DATE,'value':'1100','complete':True}],
                            'cash_flows':[{'date':'2026-01-01','amount':'100','classification':'EXTERNAL'}]
                                if 'missing_flow_boundary' in mutations else []}
                        value=performance.calculate(payload)
                    elif kind=='exposure':
                        provider=root/'provider.json';provider.write_text('{}')
                        from invest.portfolio_research_inputs import exposure_report
                        value=exposure_report(ledger)
                    else:raise DomainError('Unsupported fixed query kind')
                elif name=='tax':
                    if params.get('kind')!='lots':raise DomainError('Unsupported fixed tax kind')
                    value=tax.lots(ledger.planning_state(),DATE);evidence['tax_lots']=value['lots']
                elif name=='plan':
                    value=propose(ledger,fixture.target_id,policy=fixture.policy,
                                  mode=params['mode'],as_of=DATE,prices=fixture.prices)
                    evidence['plan_checked']=True
                elif name=='vector':
                    value=search.search(ledger.path,query=params['query'],top_k=min(records,10),
                        vector=[1.0]+[0.0]*383,model_id='fictional-fuzz-384')
                    evidence['vector_matches']=value['results']
                elif name=='backup':
                    archive=root/'roundtrip.tar.gz'
                    created=backup.create(ledger.path,archive,artifact_root=root)
                    if created['status']!='AVAILABLE':raise DomainError('Synthetic archive creation failed',3)
                    restored=backup.restore(archive,root/'restored.db',confirm=True)
                    if restored['status']!='AVAILABLE':raise DomainError('Synthetic archive restore failed',3)
                    copy_ledger=Ledger(root/'restored.db')
                    try:evidence['restored_state']=copy.deepcopy(copy_ledger.planning_state())
                    finally:copy_ledger.connection.close()
                    value={'status':'AVAILABLE','restored_fingerprint':oracles.fingerprint(evidence['restored_state'])}
                else:raise DomainError('Unsupported fixed operation')
                if isinstance(value,dict):
                    issues=value.get('issues',[])
                    if value.get('status') in {'BLOCKED','UNAVAILABLE','PARTIAL'} and any(
                            i.get('blocks_calculation') or i.get('blocks_proposals') or i.get('blocks_proposal')
                            for i in issues):
                        outcome='BLOCKED';blocked=True
            except DomainError as error:
                code=error.code;value={'error':str(error),'code':code}
                issues=getattr(error,'result',{}).get('issues',[])
                outcome='INPUT_ERROR' if code==1 or evidence.get('invalid_candidate') or name=='activity' else 'BLOCKED'
                if first_error is None:first_error=(outcome,code)
            after_operation=_canonical(ledger)
            trace.append({'operation':name,'exit_code':code,'outcome':outcome,'issues':issues,
                          'before_canonical':prior,'after_canonical':after_operation,
                          'actionable':bool(value.get('proposed_actions')) if isinstance(value,dict) else False})
            outputs.append(_projection(value))
        # Replay and reordering use actual public acceptance, not asserted model expectations.
        if candidate is not None and not evidence.get('invalid_candidate'):
            prior=_canonical(ledger);replayed=ledger.apply(candidate)
            evidence['idempotent_replay']={'status':replayed['status'],'before':prior,'after':_canonical(ledger)}
            evidence['row_order_equivalence']={'first':oracles.financial_projection(ledger.planning_state()),
                                              'second':None}
            reordered=copy.deepcopy(candidate);reordered['positions'].reverse();reordered['lots'].reverse()
            ledger.apply(reordered)
            evidence['row_order_equivalence']['second']=oracles.financial_projection(ledger.planning_state())
        after=copy.deepcopy(ledger.planning_state())
        evidence['read_only']=all(op['name'] in {'query','tax','vector','backup'} for op in case['operations'])
        evidence['after_canonical']=_canonical(ledger)
        if evidence['read_only'] and 'corpus' in evidence:
            evidence['before_canonical']=evidence['after_canonical'] if oracles.fingerprint(before)==oracles.fingerprint(after) else evidence['before_canonical']
        result={'observed_result':first_error[0] if first_error else 'BLOCKED' if blocked else 'SUCCESS',
            'exit_code':first_error[1] if first_error else 3 if blocked else 0,
            'stdout':json.dumps(outputs,sort_keys=True,default=str),'stderr':'',
            'before_fingerprint':oracles.fingerprint(before),'after_fingerprint':oracles.fingerprint(after),
            'substantive_output':oracles.financial_projection(after),
            'before_state':before,'after_state':after,'evidence':evidence,'operation_trace':trace}
        result['invariant_results']={name:oracles.check(name,before,after,result) for name in case['invariants']}
        return result
    finally:fixture.close()
