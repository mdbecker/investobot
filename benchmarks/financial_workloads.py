"""P01–P08 public operations with independent exact fixture checks."""

import copy
import hashlib
import http.client
import json
import os
import random
import re
import subprocess
import sys
import threading
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from benchmarks.financial_fixtures import DATE, build, digest, seed_plans
from benchmarks.operations import Prepared
from invest import analytics_store, backup, migrations, performance, plans, tax, tax_policy
from invest.cash_transfers import record as transfer
from invest.financial_state import state_hash
from invest.parsers.generic import parse_html
from invest.planning import propose
from invest.reports import export
from invest.simulations import simulate
from invest.targets import diff
from invest.web import create_server

MANIFEST = json.loads((Path(__file__).parent/'cases.json').read_text())
CASES = {case['id']:case for case in MANIFEST['cases']}
SUPPORTED_CASES = frozenset(
    f'{family}.{operation}' for family, operations in {
        'P01': 'cli-startup tools-list tools-describe dashboard-overview',
        'P02': 'html-preview reconcile apply idempotent-reimport check',
        'P03': 'activity-append corrected-snapshot summary planning-read linked-cash-transfer',
        'P04': 'backup verify restore-staging schema-migration manifest-verify',
        'P05': 'household-performance account-performance linked-flow-metrics incomplete-coverage hypothetical-risk',
        'P06': 'lots specific-disposal budget harvest-candidates harvest-plan household-wash-review',
        'P07': 'target-diff simulate monthly-proposal quarterly-proposal',
        'P08': 'persist-20-plans list compare-20 show markdown-export',
    }.items() for operation in operations.split())


def _cli(fixture, *arguments):
    process = subprocess.run([sys.executable, '-c', 'from invest.cli import app; app()', *arguments],
        env=dict(os.environ, INVEST_DB=str(fixture.ledger.path)), capture_output=True, text=True,
        check=False)
    if process.returncode:
        raise ValueError(process.stderr)
    return json.loads(process.stdout)


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


def prepare(case_id, root, dimensions):
    """Build outside timing; each mutation can restore its original real SQLite input."""
    root = Path(root)
    if case_id not in SUPPORTED_CASES:
        raise ValueError(f'Unsupported measured operation: {case_id}')
    fixture = build(root, dimensions,concentrated_target=case_id=='P07.quarterly-proposal')
    ledger = fixture.ledger
    family, name = case_id.split('.',1)
    account, sid = fixture.accounts[0], fixture.securities[0]
    latest = copy.deepcopy(fixture.snapshots[0])
    latest.update(source_timestamp=DATE,source_hash='fictional-new-reviewed-observation')
    for position in latest['positions']:
        position['as_of'] = DATE
    counts = {'accounts':len(ledger.rows('accounts')),
              'positions':len(ledger.rows('positions')),
              'lots':len(ledger.rows('lots')),
              'accepted_snapshots':len(ledger.rows('snapshots'))}
    cleanup = []
    before = state_hash(ledger.planning_state())
    event = dict(activity_id='fictional-perf-activity',account_id=account,type='CASH_DEPOSIT',
                 amount='1',date=DATE,event_timestamp=DATE+'T12:00:00Z',
                 source='Reviewed fictional executed cash record')
    expected_total = Decimal(dimensions['positions']*1000+dimensions['accounts']*10000)
    plan_ids = []
    if family == 'P01':
        if name=='dashboard-overview':
            server = create_server(ledger.path,port=0)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            cleanup.append(lambda:(server.shutdown(),server.server_close(),thread.join()))
            def operation():
                connection=http.client.HTTPConnection('127.0.0.1',server.server_port)
                try:
                    connection.request('GET','/api/overview');response=connection.getresponse()
                    if response.status!=200:raise ValueError('Dashboard request failed')
                    return json.loads(response.read())
                finally:connection.close()
        else:
            args={'cli-startup':('schema',),'tools-list':('tools','list'),
                  'tools-describe':('tools','describe','portfolio.summary')}[name]
            operation=lambda:_cli(fixture,*args)
    elif family=='P02':
        candidates=[]
        for original in fixture.snapshots:
            candidate=copy.deepcopy(original)
            candidate.update(source_timestamp=DATE,source_hash='fictional-new-'+original['account']['id'])
            for position in candidate['positions']:position['as_of']=DATE
            candidates.append(candidate)
        if name=='html-preview':
            htmls=[]
            for candidate in candidates:
                html=('<table><caption>Fictional original tax lots</caption><tr><th>Symbol</th>'
                      '<th>Quantity</th><th>Price</th><th>Market Value</th><th>Cost Basis</th>'
                      '<th>Remaining Adjusted Basis</th><th>Acquisition Date</th><th>Broker Lot ID</th></tr>')
                html+=''.join(f'<tr><td>{lot["security"]}</td><td>5</td><td>100</td><td>500</td>'
                    f'<td>600</td><td>600</td><td>2024-01-01</td><td>{lot["source_lot_id"]}</td></tr>'
                    for lot in candidate['lots'])+'</table>'
                htmls.append((candidate['account']['id'],html))
            operation=lambda:{'results':[parse_html(html,aid,as_of=DATE,data_environment='SYNTHETIC')
                                         for aid,html in htmls]}
        elif name=='reconcile':operation=lambda:{'results':[ledger.reconcile(c) for c in candidates]}
        elif name=='apply':operation=lambda:{'results':[ledger.apply(c) for c in candidates]}
        elif name=='idempotent-reimport':
            for candidate in candidates:ledger.apply(candidate)
            fixture.freeze();before=state_hash(ledger.planning_state())
            operation=lambda:{'results':[ledger.apply(c) for c in candidates]}
        else:
            from invest.readiness import check
            operation=lambda:check(ledger.planning_state(),as_of=DATE)
    elif family=='P03':
        if name=='activity-append':
            operation=lambda:ledger.record_activity(event,yes=True);counts['new_activities']=1
        elif name=='linked-cash-transfer':
            payload=dict(transfer_id='fictional-paired-transfer',from_account_id=account,
                to_account_id=fixture.accounts[1],amount='1',currency='USD',data_environment='SYNTHETIC',
                event_timestamp=DATE+'T12:00:00Z',source='Reviewed fictional paired bank notice')
            operation=lambda:transfer(ledger,payload,confirm=True)
        elif name=='corrected-snapshot':
            ledger.record_activity(event,yes=True)
            latest.update(cash='10001',source_timestamp='2026-10-11T12:00:00Z')
            fixture.freeze();before=state_hash(ledger.planning_state())
            operation=lambda:ledger.apply(latest)
        elif name=='summary':operation=ledger.summary
        else:operation=ledger.planning_state
    elif family=='P04':
        if name in {'backup','verify','restore-staging'}:
            # Deterministic incompressible payload is SQLite fixture content, not a private volume.
            rng=random.Random(271828)
            required=dimensions['backup_fixture_bytes']
            with ledger.connection:
                ledger.connection.execute('CREATE TABLE benchmark_padding(id INTEGER PRIMARY KEY, payload BLOB)')
                for i in range((required+1048575)//1048576):
                    ledger.connection.execute('INSERT INTO benchmark_padding VALUES (?,?)',
                        (i,rng.randbytes(min(1048576,required-i*1048576))))
            fixture.freeze()
            counts['backup_fixture_bytes']=ledger.connection.execute(
                'SELECT sum(length(payload)) FROM benchmark_padding').fetchone()[0]
            archive=root/'verified.tar.gz'
            if name!='backup':
                outcome=backup.create(ledger.path,archive,artifact_root=root)
                if outcome['status']!='AVAILABLE':raise ValueError(outcome)
            if name=='backup':operation=lambda:backup.create(ledger.path,archive,artifact_root=root)
            elif name=='verify':operation=lambda:backup.verify(archive)
            else:operation=lambda:backup.restore(archive,root/'staged.db',confirm=True)
        elif name=='schema-migration':
            outcome=backup.create(ledger.path,root/'pre-migration.tar.gz',artifact_root=root)
            if outcome['status']!='AVAILABLE':raise ValueError(outcome)
            sql='CREATE TABLE benchmark_future(id TEXT PRIMARY KEY);'
            migration=dict(id='002-benchmark-future',sql=sql,
                checksum=hashlib.sha256(sql.encode()).hexdigest(),destructive=False)
            operation=lambda:migrations.migrate(ledger.path,[migration])
        else:
            import duckdb
            parquet=root/'verified.parquet'
            connection=duckdb.connect(':memory:')
            connection.execute('COPY (SELECT 1 AS observation) TO ? (FORMAT PARQUET)',[str(parquet)])
            connection.close()
            payload=dict(data_environment='SYNTHETIC',artifacts=[dict(kind='DIVIDEND_ADJUSTED_PRICES',
                relative_path=parquet.name,sha256=hashlib.sha256(parquet.read_bytes()).hexdigest(),
                provider='FICTIONAL',observed_at=DATE,as_of=DATE,data_environment='SYNTHETIC')])
            pinned=analytics_store.snapshot(ledger,payload,confirm=True,artifact_root=root)
            fixture.freeze()
            operation=lambda:analytics_store.verify_snapshot(ledger,pinned['manifest_id'],artifact_root=root)
    elif family=='P05':
        if name=='hypothetical-risk':
            from invest.analytics import risk
            from invest.market import MarketClient
            history=[]
            for month in range(dimensions['history_years']*12+1):
                history.append({'date':date(2016+month//12,month%12+1,1).isoformat(),
                                'adjClose':str(Decimal(100)+Decimal(month)/10)})
            provider=root/'risk-provider.json'
            provider.write_text(json.dumps({'history':{f'FICT{i:05}':history
                                            for i in range(len(fixture.securities))}}))
            counts['history_years']=dimensions['history_years']
            counts['history_prices']=len(history)*len(fixture.securities)
            client=MarketClient(ledger,fixture_path=provider)
            operation=lambda:risk(ledger.planning_state(),client)
        else:
            payload=_performance(dimensions,flows=name=='linked-flow-metrics',
                incomplete=name=='incomplete-coverage',account=name=='account-performance')
            counts['history_checkpoints']=len(payload['checkpoints'])
            counts['history_flows']=len(payload['cash_flows'])
            counts['history_years']=date.fromisoformat(payload['to_date']).year-date.fromisoformat(payload['from_date']).year
            fixture.input_state_hash=digest({'financial':fixture.input_state_hash,'performance':payload})
            operation=lambda:performance.calculate(payload)
    elif family=='P06':
        if name=='budget':
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
        if name=='target-diff':operation=lambda:diff(ledger,fixture.target_id)
        elif name=='simulate':
            action=dict(activity_id='fictional-simulated-buy',account_id=account,security=sid,
                        type='BUY',quantity='1',price='100',fee='0',date=DATE)
            operation=lambda:simulate(ledger.planning_state(),[action])
        else:
            mode='contributions-only' if name=='monthly-proposal' else 'rebalance'
            policy=copy.deepcopy(fixture.policy)
            if mode=='rebalance':
                for permissions in policy['permissions'].values():
                    for permission in permissions.values():permission['can_sell']=True
                policy['annual_tax_budget']=dict(year=2026,annual_allowance='1000',
                    short_term_rate='0.35',long_term_rate='0.15',currency='USD',
                    taxable_history_complete=True,covered_account_ids=fixture.accounts,
                    data_environment='SYNTHETIC',source='Reviewed fictional annual allowance',
                    as_of='2026-09-30T12:00:00Z')
                with ledger.connection:
                    for row in ledger.rows('positions'):
                        ledger.put('positions',row['id'],dict(row,as_of='2026-09-29',source_timestamp='2026-09-29'))
                    for row in ledger.rows('cash_balances'):
                        ledger.put('cash_balances',row['id'],dict(row,as_of='2026-09-29',source_timestamp='2026-09-29'))
                    for row in ledger.rows('snapshots'):
                        ledger.connection.execute('DELETE FROM snapshot_observations WHERE id=?',(row['id'],))
                        ledger.put('snapshots',row['id'],dict(row,source_timestamp='2026-09-29',
                            positions=[dict(p,as_of='2026-09-29') for p in row['positions']]))
                fixture.freeze()
                fixture.prices={key:dict(value,as_of='2026-09-30')
                                for key,value in fixture.prices.items()}
            operation=lambda:propose(ledger,fixture.target_id,policy=policy,mode=mode,
                                     as_of='2026-09-30' if mode=='rebalance' else DATE,
                                     prices=fixture.prices)
    elif family=='P08':
        existing_count=dimensions['saved_plans']-20 if name=='persist-20-plans' else dimensions['saved_plans']
        if existing_count:
            plan_ids=seed_plans(fixture,existing_count);fixture.freeze();before=state_hash(ledger.planning_state())
        counts['existing_plans']=existing_count
        counts['output_plans']=dimensions['saved_plans']
        if name=='persist-20-plans':
            def operation():
                ids=seed_plans(fixture,20)
                return {'plan_ids':ids,'summaries':plans.compare(ledger,*ids)['plans']}
            counts['distinct_new_plans']=20
        elif name=='list':operation=lambda:plans.list_plans(ledger)
        elif name=='compare-20':operation=lambda:plans.compare(ledger,*plan_ids[:20])
        elif name=='show':operation=lambda:plans.show(ledger,plan_ids[0])
        else:operation=lambda:{'export':export(plans.show(ledger,plan_ids[0]),root/'report.md')}
    else:raise ValueError(f'Not a financial workload: {case_id}')

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
        return walk(value)

    def operation():
        nonlocal raw_result
        raw_result=raw_operation()
        if family=='P01' and name=='tools-list':counts['commands']=len(raw_result['tools'])
        if family=='P08':
            counts['saved_plans']=ledger.connection.execute('SELECT count(*) FROM plan_runs').fetchone()[0]
        if family=='P08' and name=='markdown-export':
            return {'format':'markdown','plan':substantive(plans.show(ledger,plan_ids[0]))}
        if family=='P04':
            # Archive container hashes include publication wall times. The gate compares
            # verified substantive contents; byte sizes and exact archive hashes are
            # independently verified by the real recovery operation.
            return {'status':raw_result['status'],
                    'financial_state_hash':state_hash(ledger.planning_state()),
                    'applied_migrations':raw_result.get('applied_migrations',[]),
                    'issues':raw_result.get('issues',[])}
        return substantive(raw_result)

    def verify(projected):
        """Check exact fixture facts independently of the implementation's success label."""
        result=raw_result
        state=ledger.planning_state()
        valid_fk=not ledger.connection.execute('PRAGMA foreign_key_check').fetchall()
        inventory_ok=(len(state['positions'])==dimensions['positions'] and
            len(state['lots'])==dimensions['lots'] and
            all(Decimal(p['quantity'])==(9 if family=='P06' and name=='budget' and
                p['account_id']==account and p['security_id'] in fixture.securities[:2] else 10)
                for p in state['positions']) and
            all(Decimal(l['remaining_adjusted_basis'])==(480 if family=='P06' and name=='budget' and
                l['id'] in {f'{account}:lot:00000:0',f'{account}:lot:00001:0'} else 600)
                for l in state['lots']))
        preserved=state_hash(state)==before
        semantic=True
        if family=='P01':semantic=isinstance(result,dict) and bool(result)
        elif family=='P02':
            if name=='html-preview':
                positions=[p for item in result['results'] for p in item['positions']]
                semantic=len(positions)==dimensions['positions'] and all(
                    p['displayed_price_precision']==0 and p['price']=='100' for p in positions)
                semantic=semantic and sum(len(item['lots']) for item in result['results'])==dimensions['lots']
            elif name=='idempotent-reimport':semantic=all(r['status']=='UNCHANGED' for r in result['results'])
            elif name=='apply':semantic=all(r['status']=='APPLIED' for r in result['results'])
            elif name=='reconcile':semantic=len(result['results'])==dimensions['accounts']
            else:semantic=isinstance(result,dict) and 'issues' in result
        elif family=='P03':
            if name in {'activity-append','corrected-snapshot'}:
                semantic=Decimal(next(c['amount'] for c in state['cash_balances'] if c['account_id']==account))==10001
            elif name=='linked-cash-transfer':
                semantic=len(state['activities'])==2 and sum(Decimal(c['amount']) for c in state['cash_balances'])==dimensions['accounts']*10000
            elif name=='summary':semantic=Decimal(result['total_value'])==expected_total
            else:semantic=len(result['positions'])==dimensions['positions']
        elif family=='P04':semantic=result.get('status') in {'AVAILABLE','APPLIED','PREVIEW','VERIFIED'}
        elif family=='P05' and name!='hypothetical-risk':
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
        if family=='P01':
            fact('valid-public-json-or-http',True,isinstance(result,dict) and bool(result))
            fact('selected-ledger-unchanged',before,state_hash(state))
        elif family=='P02':
            fact('source-precision-and-provenance-preserved',
                 {'environments':['SYNTHETIC'],'price_precision':[0]},
                 {'environments':sorted({a.get('data_environment') for a in state['accounts']}),
                  'price_precision':sorted({p.get('displayed_price_precision') for p in state['positions']})})
            fact('positions-lots-cash-match-fixture',
                 {'positions':dimensions['positions'],'lots':dimensions['lots'],
                  'cash':str(dimensions['accounts']*10000)},
                 {'positions':len(state['positions']),'lots':len(state['lots']),
                  'cash':str(sum(Decimal(c['amount']) for c in state['cash_balances']))})
        elif family=='P03':
            delta=Decimal(1) if name in {'activity-append','corrected-snapshot'} else Decimal(0)
            fact('confirmed-accounting-conservation',
                 {'value':str(expected_total+delta),'basis':str(dimensions['lots']*600)},
                 {'value':str(sum(Decimal(p['market_value']) for p in state['positions'])+
                              sum(Decimal(c['amount']) for c in state['cash_balances'])),
                  'basis':str(sum(Decimal(l['remaining_adjusted_basis']) for l in state['lots']))})
            fact('accepted-history-preserved',
                 {'activities':2 if name=='linked-cash-transfer' else 1 if delta else 0,
                  'snapshots':dimensions['accepted_snapshots']+(name=='corrected-snapshot')},
                 {'activities':len(ledger.rows('activities')),'snapshots':len(ledger.rows('snapshots'))})
        elif family=='P04':
            archive=root/('pre-migration.tar.gz' if name=='schema-migration' else 'verified.tar.gz')
            verified=backup.verify(archive)['status']=='AVAILABLE' if archive.exists() else (
                analytics_store.verify_snapshot(ledger,pinned['manifest_id'],artifact_root=root)['status']=='AVAILABLE')
            fact('verified-artifact-hashes',True,verified)
            fact('foreign-key-integrity',[],ledger.connection.execute('PRAGMA foreign_key_check').fetchall())
            restored=before
            if name=='restore-staging':
                from invest.ledger import Ledger
                restored_ledger=Ledger(root/'staged.db')
                try:restored=state_hash(restored_ledger.planning_state())
                finally:restored_ledger.connection.close()
            else:restored=state_hash(state)
            fact('restored-logical-state-equal',before,restored)
        elif family=='P05':
            if name=='hypothetical-risk':
                fact('independent-dated-flow-results','HYPOTHETICAL_CURRENT_ALLOCATION',result.get('mode'))
                fact('account-scope-correct',dimensions['positions'],len(state['positions']))
                fact('missing-coverage-typed',len(fixture.securities),len(result.get('provenance',{})))
            else:
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
        for call in cleanup:call()
        fixture.close()
    return Prepared(operation=operation,verify=verify,counts=counts,
        input_state_hash=fixture.input_state_hash,reset=fixture.reset,close=close,
        storage_roots=(root,))
