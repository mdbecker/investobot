"""P01–P08 public operations with independent exact fixture checks."""

import hashlib
import json
import re
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from benchmarks.financial_fixtures import DATE, build, digest, persist, seed_plans
from benchmarks.operations import Prepared
from invest import performance, plans, tax, tax_policy
from invest.financial_state import state_hash
from invest.planning import propose
from invest.simulations import simulate


def foundation_projection(value):
    """Compare the approved removal of eligible calendar metadata, keeping all facts."""
    if isinstance(value, list):
        return [foundation_projection(item) for item in value]
    if not isinstance(value, dict):
        return value
    plan = value.get('algorithm_version') == 'contribution-first-hifo-1'
    if plan and 'cadence' in value and value['cadence'] != {'eligible': True}:
        raise ValueError('Unexpected reference calendar outcome; financial comparison is invalid')
    return {key: foundation_projection(item) for key, item in value.items()
            if not (plan and key == 'cadence')}

MANIFEST = json.loads((Path(__file__).parent/'cases.json').read_text())
CASES = {case['id']:case for case in MANIFEST['cases']}
SUPPORTED_CASES = frozenset(CASES)


def _performance(dimensions, *, flows=False, incomplete=False, account=False):
    checkpoints = []
    cash_flows = []
    months = dimensions['history_years']*12
    density=dimensions.get('history_density',1)
    size=(months+1)*density
    elapsed=(date(2016+dimensions['history_years'],1,1)-date(2016,1,1)).days
    for i in range(size):
        day = (date(2016+i//12,i%12+1,1) if density==1 else
               date(2016,1,1)+timedelta(days=elapsed*i//(size-1))).isoformat()
        value = 1000+i*100 if flows else 1000
        checkpoints.append(dict(date=day, value=str(value), complete=not(incomplete and i==size-1)))
        if flows and i:
            checkpoints[-1]['timing'] = 'AFTER_FLOW'
            cash_flows.append(dict(date=day, amount='100', classification='EXTERNAL'))
    return dict(from_date=checkpoints[0]['date'],to_date=checkpoints[-1]['date'],
        scope='ACCOUNT' if account else 'HOUSEHOLD',data_environment='SYNTHETIC',
        cash_flow_history_complete=True,checkpoints=checkpoints,cash_flows=cash_flows,
        fee_method='NET_OF_FEES')


def prepare(case_id, root, dimensions, *, reuse=False):
    """Build outside timing; each mutation can restore its original real SQLite input."""
    root = Path(root)
    if case_id not in SUPPORTED_CASES:
        raise ValueError(f'Unsupported measured operation: {case_id}')
    metadata_path=root/'financial-workload.json'
    metadata=json.loads(metadata_path.read_text()) if reuse else {}
    if reuse and (metadata['case_id']!=case_id or metadata['dimensions']!=dimensions):
        raise ValueError('Financial workload recipe dimensions or case differ')
    fixture = build(root, dimensions,concentrated_target=case_id=='P07.quarterly-proposal',reuse=reuse)
    ledger = fixture.ledger
    family, name = case_id.split('.',1)
    account, sid = fixture.accounts[0], fixture.securities[0]
    counts = {'accounts':len(ledger.rows('accounts')),
              'positions':len(ledger.rows('positions')),
              'lots':len(ledger.rows('lots')),
              'accepted_snapshots':len(ledger.rows('snapshots'))}
    cleanup = []
    before = state_hash(ledger.planning_state())
    expected_total = Decimal(dimensions['positions']*1000+dimensions['accounts']*10000)
    plan_ids = []
    if family=='P05':
        payload=_performance(dimensions,flows=name=='linked-flow-metrics',
            incomplete=name=='incomplete-coverage',account=name=='account-performance')
        counts['history_checkpoints']=len(payload['checkpoints'])
        counts['history_flows']=len(payload['cash_flows'])
        counts['history_years']=date.fromisoformat(payload['to_date']).year-date.fromisoformat(payload['from_date']).year
        if not reuse:
            fixture.input_state_hash=digest({'financial':fixture.input_state_hash,'performance':payload})
        operation=lambda:performance.calculate(payload)
    elif family=='P06':
        if name=='budget' and not reuse:
            for index,price in enumerate(('100','150')):
                ledger.record_activity(dict(activity_id=f'fictional-budget-sale-{index}',
                    account_id=account,security=fixture.securities[index],type='SELL',quantity='1',
                    price=price,fee='0',date=DATE,event_timestamp=DATE+'T12:00:00Z',
                    source='Reviewed fictional confirmed lot-specific sale',
                    lot_allocations=[dict(lot_id=f'{account}:lot:{index:05}:0',quantity='1')]),yes=True)
            fixture.freeze()
            before=state_hash(ledger.planning_state())
        state=ledger.planning_state()
        counts['confirmed_sales']=sum(a.get('type')=='SELL' for a in state['activities'])
        rates=dict(ordinary_income_rate='0.35',long_term_capital_gains_rate='0.15')
        if name=='lots':operation=lambda:tax.lots(state,DATE)
        elif name=='specific-disposal':
            lot_id=f'{account}:lot:00000:0'
            operation=lambda:tax.analyze(state,account,sid,'1','100',DATE,method='SPECIFIC',
                                        lot_ids=[lot_id],rates=rates)
        elif name=='budget':
            policy=dict(year=2026,annual_allowance='1000',short_term_rate='0.35',long_term_rate='0.15',
                currency='USD',taxable_history_complete=True,covered_account_ids=fixture.accounts,
                data_environment='SYNTHETIC',source='Reviewed fictional annual policy',
                as_of=DATE+'T12:00:00Z')
            operation=lambda:tax_policy.annual_budget(state,policy)
        elif name=='harvest-candidates':operation=lambda:tax.harvest_candidates(state,DATE)
        else:
            policy=dict(loss_sale_date=DATE,security=sid,spouse_history_complete=True,
                outside_account_history_complete=True,dividend_reinvestment_history_complete=True,
                data_environment='SYNTHETIC',scheduled_acquisitions=[dict(security_id=sid,
                    account_id=account,date=DATE,quantity='1',activity_id='fictional-scheduled-buy',
                    source='Reviewed fictional scheduled acquisition')] if name=='household-wash-review' else [])
            operation=lambda:tax_policy.harvest_plan(state,policy,DATE)
    elif family=='P07':
        operation=lambda:propose(ledger,fixture.target_id,policy=fixture.policy,
                                 mode='contributions-only',as_of=DATE,prices=fixture.prices)
    elif family=='P08':
        if reuse:plan_ids=metadata['plan_ids']
        else:
            plan_ids=seed_plans(fixture,dimensions['saved_plans']);fixture.freeze()
        before=state_hash(ledger.planning_state())
        counts.update(existing_plans=dimensions['saved_plans'],output_plans=dimensions['saved_plans'])
        operation=(lambda:plans.list_plans(ledger)) if name=='list' else (lambda:plans.show(ledger,plan_ids[0]))
    else:raise ValueError(f'Not a financial workload: {case_id}')

    if family=='P08':counts['saved_plans']=dimensions['saved_plans']
    if reuse:
        counts.update(metadata['counts'])
    if not reuse:
        persist(fixture,dimensions,concentrated_target=case_id=='P07.quarterly-proposal')
        metadata_path.write_text(json.dumps(dict(version=1,case_id=case_id,dimensions=dimensions,
            plan_ids=plan_ids,counts=counts,pinned=locals().get('pinned')),sort_keys=True))

    raw_operation=operation
    raw_result=None

    def substantive(value):
        # Generated run UUIDs and ingestion wall clocks are incidental, not financial
        # facts. Preserve their relationship structure with consistent local labels.
        identities={}
        def walk(item):
            if isinstance(item,dict):
                return {key:walk(cell) for key,cell in sorted(item.items())
                        if key not in {'created_at','updated_at','recorded_at','imported_at',
                                       'retrieval_timestamp','retrieved_at','source_age_seconds'}}
            if isinstance(item,list):return [walk(cell) for cell in item]
            if isinstance(item,Decimal):return format(item,'f')
            if isinstance(item,str) and re.fullmatch(r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}',item):
                return identities.setdefault(item,f'generated-identity-{len(identities)}')
            return item
        return walk(foundation_projection(value))

    def operation():
        nonlocal raw_result
        raw_result=raw_operation()
        return substantive(raw_result)

    immutable_performance = family == 'P05' and name != 'hypothetical-risk'
    immutable_state = ledger.planning_state() if immutable_performance else None
    immutable_fk = (not ledger.connection.execute('PRAGMA foreign_key_check').fetchall()
                    if immutable_performance else None)
    if immutable_performance:
        immutable_inventory_ok = (len(immutable_state['positions']) == dimensions['positions']
            and len(immutable_state['lots']) == dimensions['lots']
            and all(Decimal(p['quantity']) == 10 for p in immutable_state['positions'])
            and all(Decimal(l['remaining_adjusted_basis']) == 600 for l in immutable_state['lots']))
        immutable_preserved = state_hash(immutable_state) == before
        ledger.connection.execute('PRAGMA query_only=ON')
        initial_changes = ledger.connection.total_changes
        initial_version = ledger.connection.execute('PRAGMA data_version').fetchone()[0]

    def guard():
        if (ledger.connection.execute('PRAGMA query_only').fetchone()[0] != 1
                or ledger.connection.total_changes != initial_changes
                or ledger.connection.execute('PRAGMA data_version').fetchone()[0] != initial_version):
            raise ValueError('Immutable performance fixture guard changed')

    def verify(projected):
        """Check exact fixture facts independently of the implementation's success label."""
        result=raw_result
        from benchmarks.operations import retain_native
        retain_native(case_id, result)
        if immutable_performance:
            guard()
        state=immutable_state if immutable_performance else ledger.planning_state()
        valid_fk=immutable_fk if immutable_performance else not ledger.connection.execute('PRAGMA foreign_key_check').fetchall()
        inventory_ok=immutable_inventory_ok if immutable_performance else (len(state['positions'])==dimensions['positions'] and
            len(state['lots'])==dimensions['lots'] and
            all(Decimal(p['quantity'])==(9 if family=='P06' and name=='budget' and
                p['account_id']==account and p['security_id'] in fixture.securities[:2] else 10)
                for p in state['positions']) and
            all(Decimal(l['remaining_adjusted_basis'])==(480 if family=='P06' and name=='budget' and
                l['id'] in {f'{account}:lot:00000:0',f'{account}:lot:00001:0'} else 600)
                for l in state['lots']))
        preserved=immutable_preserved if immutable_performance else state_hash(state)==before
        semantic=True
        if family=='P05' and name!='hypothetical-risk':
            semantic=result['status']==('UNAVAILABLE' if name=='incomplete-coverage' else 'AVAILABLE')
            if name!='incomplete-coverage':semantic=semantic and Decimal(result['twr']['return'])==0
            else:semantic=semantic and any(i['code']=='PARTIAL_VALUATION_CHECKPOINT' for i in result['issues'])
        elif family=='P06':
            if name=='specific-disposal':semantic=Decimal(result['long_term_gain_loss'])==-20
            elif name=='lots':semantic=len(result['lots'])==dimensions['lots'] and all(Decimal(l['cost_basis'])==600 for l in result['lots'])
            elif name=='budget':semantic=result.get('status')=='AVAILABLE' and Decimal(result['remaining_allowance'])==Decimal('995.5')
            elif name=='household-wash-review':semantic=bool(result['wash_review']['conflicts']) and result['legal_wash_sale_safe'] is None
            else:semantic=bool(result) and result.get('legal_wash_sale_safe') is None
        elif family=='P07':
            if name=='simulate':semantic=Decimal(result['household_value_after'])==expected_total
            elif name.endswith('proposal'):semantic=result.get('status') not in {'BLOCKED','UNAVAILABLE'} and bool(result.get('id'))
            else:semantic=bool(result)
        elif family=='P08':
            if name=='persist-20-plans':semantic=len(set(result['plan_ids']))==20 and ledger.connection.execute('SELECT count(*) FROM plan_runs').fetchone()[0]==dimensions['saved_plans']
            elif name=='list':semantic=len(result['plans'])==dimensions['saved_plans']
            elif name=='compare-20':semantic=len(result['plans'])==20
            elif name=='show':semantic=bool(result.get('storage_identity',{}).get('manifest_hash'))
            else:semantic=(root/'report.md').exists() and len((root/'report.md').read_text())>100 and (
                result['export']['content_hash']==hashlib.sha256((root/'report.md').read_bytes()).hexdigest())
        facts={}
        def fact(key,expected,observed):
            facts[key]=dict(passed=expected==observed and semantic and valid_fk and inventory_ok,
                            expected=json.loads(json.dumps(expected,default=str)),
                            observed=json.loads(json.dumps(observed,default=str)))
        if family=='P05':
            complete=name!='incomplete-coverage'
            xirr=result['xirr']['annualized_return']
            # XIRR is explicitly a float64 root statistic, unlike exact cash/basis.
            # Keep the raw value in the operation output and use a stated oracle
            # tolerance only when checking the independently known zero root.
            fact('independent-dated-flow-results',
                 {'twr':None if not complete else '0',
                  'zero_xirr_within_1e-12':True if complete else None,
                  'cagr':None if not complete else 0.0,
                  'net_contributions':str((len(payload['checkpoints'])-1)*100) if name=='linked-flow-metrics' else '0'},
                 {'twr':result['twr']['return'],
                  'zero_xirr_within_1e-12':None if not complete else xirr is not None and abs(xirr)<=1e-12,
                  'cagr':result['cagr']['annualized_return'],
                  'net_contributions':result['net_external_contributions']})
            facts['independent-dated-flow-results']['absolute_statistical_tolerance']=1e-12
            facts['independent-dated-flow-results']['raw_xirr']=xirr
            fact('account-scope-correct','ACCOUNT' if name=='account-performance' else 'HOUSEHOLD',result['scope'])
            fact('missing-coverage-typed',['PARTIAL_VALUATION_CHECKPOINT'] if name=='incomplete-coverage' else [],
                 [i['code'] for i in result['issues']])
        elif family=='P06':
            fact('exact-adjusted-basis',str(dimensions['lots']*600-(240 if name=='budget' else 0)),
                 str(sum(Decimal(l['remaining_adjusted_basis']) for l in state['lots'])))
            if name=='budget':
                fact('positive-cost-budget-losses-do-not-refill',
                     {'signed_gain':'10','positive_cost':'4.5','remaining':'995.5'},
                     {'signed_gain':result['realized_signed_net_gain'],
                      'positive_cost':result['year_to_date_consumption'],
                      'remaining':result['remaining_allowance']})
            else:
                fact('positive-cost-budget-losses-do-not-refill',0,
                     sum(1 for a in state['activities'] if a.get('type')=='SELL'))
            fact('wash-uncertainty-explicit',None,result.get('legal_wash_sale_safe'))
        elif family=='P07':
            actions=result.get('proposed_actions',[])
            simulated=simulate(state,actions) if actions else {'household_value_after':str(expected_total)}
            fact('authoritative-simulation-conservation',expected_total,
                 Decimal(result['household_value_after']) if name=='simulate' else Decimal(simulated['household_value_after']))
            fact('approved-policy-and-cash-gates',True,not any(
                i.get('blocks_proposals') for i in result.get('issues',[])))
            fact('complete-holdings-coverage',dimensions['positions'],len(state['positions']))
        elif family=='P08':
            rows=ledger.connection.execute('SELECT id FROM plan_runs').fetchall()
            fact('20-distinct-immutable-plan-identities',dimensions['saved_plans'],len({row[0] for row in rows}))
            fact('all-20-projections-compared',20,len(plans.compare(ledger,*[r[0] for r in rows[:20]])['plans']))
            fact('report-source-pinning',True,all(
                plans.show(ledger,r[0]).get('storage_identity',{}).get('manifest_hash')==
                ledger.connection.execute("SELECT checksum FROM schema_migrations WHERE id='001'").fetchone()[0]
                for r in rows))
        values=facts
        if not CASES[case_id]['mutates'] and family not in {'P07'}:
            for value in values.values():value['passed'] &= preserved
        return values

    closed=False
    def close():
        nonlocal closed
        if closed:return
        closed=True
        try:
            if immutable_performance:
                # Final independent native inventory proof precedes PASS publication.
                final_state = ledger.planning_state()
                final_fk = ledger.connection.execute('PRAGMA foreign_key_check').fetchall()
                guard()
                if state_hash(final_state) != before or final_fk:
                    raise ValueError('Immutable performance fixture inventory changed')
            for call in cleanup:call()
        finally:
            fixture.close()
    from benchmarks.correctness_projection import project
    return Prepared(operation=operation,verify=verify,counts=counts,
        input_state_hash=digest(project({'financial':substantive(ledger.planning_state()),
                                'performance':payload if family=='P05' else None,
                                'policy':locals().get('policy'), 'trading_policy':fixture.policy,
                                'prices':fixture.prices, 'target':fixture.target_id})),
        reset=guard if immutable_performance else fixture.reset,close=close,
        storage_roots=(root,), connection=ledger.connection)
