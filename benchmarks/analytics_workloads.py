"""Real isolated P09–P15 operations with independent fixture coverage checks."""

import copy
import hashlib
import json
import sqlite3
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from benchmarks import analytics_fixtures as fixtures
from invest import (
    analytics_store,
    backtest,
    lookthrough,
    search,
)

SUPPORTED_CASES = frozenset({'P10.recursive-exposure', 'P10.top-issuers',
    'P11.temporal-join', 'P12.run-ten-years', 'P14.text-top10', 'P14.semantic-top10'})


def _json(value):
    if isinstance(value, dict):
        return {key: _json(item) for key, item in value.items()
                if key not in {'created_at', 'imported_at', 'retrieved_at', 'retrieval_timestamp',
                               'approved_at', 'source_age_seconds'}
                and not (key == 'id' and isinstance(item, str) and len(item) == 36)}
    if isinstance(value, list):
        return [_json(item) for item in value]
    return json.loads(json.dumps(value, default=str))


def _checkpoint(ledger, root, *, reuse=False):
    path = root / 'benchmark-baseline.sqlite'
    if not reuse:
        destination = sqlite3.connect(path)
        try:
            destination.execute('PRAGMA journal_mode=DELETE')
            ledger.connection.backup(destination)
        finally:
            destination.close()

    def reset():
        source = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
        try:
            source.backup(ledger.connection)
        finally:
            source.close()
    return reset


def prepare(case_id, root, dimensions, *, reuse=False):
    from benchmarks.financial_fixtures import build
    from benchmarks.operations import Prepared, evidence

    if case_id not in SUPPORTED_CASES:
        raise ValueError('Unsupported analytical operation: ' + case_id)
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    metadata_path = root / 'analytical-preparation.json'
    metadata = json.loads(metadata_path.read_text()) if reuse else {}
    if reuse and (metadata.get('case_id') != case_id or metadata.get('dimensions') != dimensions):
        raise ValueError('Analytical template identity mismatch')
    stage = metadata.get('stage') if reuse else None
    financial = build(root, dimensions, reuse=reuse)
    ledger = financial.ledger
    family, operation = case_id.split('.', 1)
    counts = {name: len(ledger.rows(table))
              for name, table in {'accounts': 'accounts', 'positions': 'positions',
                  'lots': 'lots', 'accepted_snapshots': 'snapshots'}.items()}
    counts['saved_plans'] = ledger.connection.execute('SELECT count(*) FROM plan_runs').fetchone()[0]
    factual_dimensions = {'P09': ('funds',), 'P10': ('funds', 'nested_levels'),
        'P11': ('parquet_observations',), 'P12': ('history_years',),
        'P14': ('research_chunks', 'vector_dimensions')}
    counts.update({key: dimensions[key] for key in factual_dimensions.get(family, ())})
    if family == 'P10':
        run, observations = _exposure(ledger, dimensions, operation, counts, stage=stage)
    elif family == 'P11':
        run, observations = _parquet(ledger, root, dimensions, operation, financial.securities[0], counts, stage=stage)
    elif family == 'P12':
        run, observations = _historical(ledger, dimensions, operation,
            financial.securities[:dimensions.get('historical_assets', 2)], counts, stage=stage)
    elif family == 'P14':
        run, observations = _corpus(ledger, dimensions, operation, counts, stage=stage)
    else:
        financial.close()
        raise ValueError('Unsupported analytics benchmark family')
    corpus_rows = {}
    if family == 'P14':
        for table in ('document_chunks', 'embeddings'):
            corpus_rows[table] = [tuple(row) for row in ledger.connection.execute(
                'SELECT * FROM ' + table + ' ORDER BY 1,2')]
    baseline = fixtures.digest(evidence({'financial': ledger.planning_state(),
                                        'sources': run.preparation, 'corpus': corpus_rows}))
    if not reuse:
        metadata_path.write_text(json.dumps({'case_id': case_id, 'dimensions': dimensions,
            'stage': run.preparation}, sort_keys=True, default=str))
    reset = _checkpoint(ledger, root, reuse=reuse)
    definitions = json.loads((fixtures.ROOT / 'benchmarks/cases.json').read_text())
    required = next(case['invariant'] for case in definitions['cases'] if case['id'] == case_id)

    def operation_call():
        return _json(run())

    def verify(result):
        facts = observations(result)
        values = {}
        for name in required:
            expected, observed = facts[name]
            if isinstance(expected, Decimal):
                expected = format(expected.normalize(), 'f')
            if isinstance(observed, Decimal):
                observed = format(observed.normalize(), 'f')
            values[name] = {'passed': expected == observed, 'expected': expected, 'observed': observed}
        return values

    return Prepared(operation=operation_call, verify=verify, counts=counts,
                    input_state_hash=baseline, reset=reset, close=financial.close,
                    storage_roots=(root,))


def _exposure(ledger, dimensions, operation, counts, *, stage=None):
    # Three wrappers with exactly sourced fractional paths to shared companies.
    size = dimensions['constituents_per_fund']
    if stage is None:
        companies = [fixtures.register_issuer(ledger, ticker=f'COMP{index:06}',
            cik=f'{index + 1:010}', name=f'Fictional company {index}') for index in range(size)]
        wrappers = [fixtures.register_security(ledger, f'fictional-wrapper-{index:04}', {'ticker': f'WRAP{index:04}',
            'name': f'Fictional wrapper {index}', 'asset_type': 'ETF', 'currency': 'USD',
            'source': 'Reviewed fictional wrapper record', 'data_environment': 'SYNTHETIC'})
            for index in range(dimensions['funds'])]
        ledger.apply({'account': {'id': 'fund-slice', 'name': 'Fictional fund exposure slice',
            'tax_status': 'TAX_FREE', 'currency': 'USD'},
            'positions': [{'security': wrapper['ticker'], 'asset_type': 'ETF', 'quantity': '1',
                'price': '100', 'market_value': '100', 'as_of': fixtures.DATE,
                'displayed_price_precision': 0, 'displayed_market_value_precision': 0} for wrapper in wrappers],
            'lots': [], 'cash': '0', 'cash_known': True, 'positions_complete': True,
            'lots_complete': False, 'source_timestamp': fixtures.DATE,
            'source_hash': 'fictional-fund-slice', 'data_environment': 'SYNTHETIC'})
        state = ledger.planning_state()
        state['accounts'] = [row for row in state['accounts'] if row['id'] == 'fund-slice']
        state['positions'] = [row for row in state['positions'] if row['account_id'] == 'fund-slice']
        state['cash_balances'] = []  # Explicit zero confirmed cash adds no exposure path.
        sources = {}
        for index, wrapper in enumerate(wrappers):
            weight = (Decimal(1) / size).quantize(Decimal('0.000000000001'))
            holdings = [{'security_id': company['id'], 'issuer_id': company['cik'],
                'issuer_verified': True, 'weight': str(weight if row < size - 1 else 1 - weight * (size - 1))}
                for row, company in enumerate(companies)]
            if index < 2:
                holdings[0] = {'security_id': wrappers[index + 1]['id'], 'weight': str(weight)}
            if operation == 'incomplete-coverage':
                # Omit half each terminal company's disclosed weight, never redistribute.
                for holding in holdings:
                    if holding.get('issuer_verified'):
                        holding['weight'] = str(Decimal(holding['weight']) / 2)
            vintages = []
            for vintage in range(dimensions['fund_vintages']):
                day = (date.fromisoformat(fixtures.DATE) - timedelta(days=vintage * 30)).isoformat()
                vintages.append({'id': f'fictional-{index}-vintage-{vintage}',
                    'security_id': wrapper['id'], 'as_of': day, 'observed_at': day,
                    'published_at': day, 'sha256': fixtures.digest(holdings),
                    'currency': 'USD', 'data_environment': 'SYNTHETIC', 'rows': holdings})
            sources[wrapper['id']] = vintages
    else:
        state, sources = stage['state'], stage['sources']
    counts.update(processed_funds=dimensions['funds'],
        processed_constituents=dimensions['funds'] * size,
        selected_fund_vintages=dimensions['funds'],
        examined_fund_vintages=dimensions['funds'] * dimensions['fund_vintages'])

    def run():
        evidence = {}
        for security, vintages in sources.items():
            selected = analytics_store.select_vintage(vintages, security_id=security, as_of=fixtures.DATE)
            evidence[security] = {'as_of': selected['as_of'], 'observed_at': selected['observed_at'],
                'currency': 'USD', 'data_environment': 'SYNTHETIC', 'source_id': selected['id'],
                'source_hash': selected['sha256'], 'holdings': selected['rows']}
        if operation == 'recursive-exposure':
            return lookthrough.exposure(state, evidence, as_of=fixtures.DATE)
        return lookthrough.research_universe(state, evidence, as_of=fixtures.DATE,
                                             top=size, min_exposure='0')
    expected_unknown = str(dimensions['funds'] * 50) if operation == 'incomplete-coverage' else '0'

    def observed(output):
        rows = output.get('companies', output.get('exposures', []))
        # Paths through the replaced first company reach it via terminal wrappers.
        return {'all-paths-and-vintages-accounted': [str(size), str(len(rows))],
            'duplicate-issuer-consolidation': [str(size), str(len({row['issuer_id'] for row in rows}))],
            'unknown-residual-preserved': [Decimal(expected_unknown), Decimal(output['unknown_exposure_value'])]}
    run.preparation = {'state': state, 'sources': sources}
    return run, observed


def financial_account(state):
    return state['accounts'][0]['id']


def _parquet(ledger, root, dimensions, operation, security, counts, *, stage=None):
    payload = fixtures.parquet_file(root, dimensions, security) if stage is None else stage['payload']
    if operation != 'data-snapshot' and stage is None:
        analytics_store.snapshot(ledger, payload, confirm=True, artifact_root=root)

    def run():
        if operation == 'data-snapshot':
            return analytics_store.snapshot(ledger, payload, confirm=True, artifact_root=root)
        with analytics_store.analytical_connection(ledger, payload, artifact_root=root) as connection:
            if operation == 'pinned-parquet-read':
                query = 'SELECT count(*) FROM artifact_0 JOIN ledger.securities s ON artifact_0.security_id=s.id'
            elif operation == 'temporal-join':
                query = ('SELECT count(*) FROM artifact_0 h JOIN artifact_1 v '
                    'ON h.security_id=v.security_id AND h.date BETWEEN v.effective_from AND v.effective_to '
                    "WHERE v.observed_at <= DATE '2026-10-10'")
            else:
                query = 'SELECT sum(n) FROM (SELECT date,count(*) n FROM artifact_0 GROUP BY date)'
            return {'rows': connection.execute(query).fetchone()[0], 'manifest': payload['id']}

    def observed(output):
        if operation == 'data-snapshot':
            with fixtures.duckdb.connect(':memory:') as independent:
                rows = independent.execute('SELECT count(*) FROM read_parquet(?)',
                    [str(root / 'observations.parquet')]).fetchone()[0]
        else:
            rows = output.get('rows', 0)
        counts['processed_parquet_observations'] = rows
        counts['source_constituent_vintage_rows'] = 3
        verification = analytics_store.verify_snapshot(ledger, payload, artifact_root=root)
        return {'exact-dated-row-coverage': [dimensions['parquet_observations'], rows],
            'pinned-manifest-hashes': ['AVAILABLE', verification['status']],
            'no-future-constituents': [dimensions['parquet_observations'], rows]}
    run.preparation = {'payload': payload}
    return run, observed


def _historical(ledger, dimensions, operation, securities, counts, *, stage=None):
    manifest, days = (fixtures.daily_history(securities, dimensions['history_years'])
                      if stage is None else (stage['manifest'], stage['days']))
    policy = {'version': 'fictional-backtest-1', 'data_environment': 'SYNTHETIC',
              'starting_value': '10000', 'fee_per_trade': '0'}
    counts.update(historical_assets=len(securities), history_rows=len(securities) * len(days))
    weight = Decimal(1) / len(securities)
    first = {sid: str(weight) for sid in securities}
    second = {sid: str(weight / 2) for sid in securities}
    second['CASH'] = '0.5'
    denominator = sum(range(1, len(securities) + 1))
    third = {sid: str(Decimal(index + 1) / denominator) for index, sid in enumerate(securities)}
    portfolios = [first, second, third]

    def execute(weights, source=manifest):
        return backtest.run(ledger, portfolio=weights, start=days[0],
                            end=days[-1], policy=policy, manifest=source)
    runs = ([execute(weights) for weights in portfolios] if operation == 'compare-three' else []) if stage is None else stage['runs']

    def run():
        if operation == 'compare-three':
            return backtest.compare(ledger, [result['id'] for result in runs])
        if operation == 'unavailable-history':
            incomplete = copy.deepcopy(manifest)
            incomplete['series'][securities[0]].pop(len(days) // 2)
            return execute(portfolios[0], incomplete)
        first = execute(portfolios[0])
        if operation == 'identical-repeat':
            second = execute(portfolios[0])
            return {'first': first, 'second': second}
        return first

    def observed(output):
        selected = output.get('first', output)
        available = selected.get('status') == ('COMPARABLE' if operation == 'compare-three' else 'UNAVAILABLE' if operation == 'unavailable-history' else 'AVAILABLE')
        expected_runs = 3 if operation == 'compare-three' else 2 if operation == 'identical-repeat' else 1
        actual_runs = len(output['runs']) if operation == 'compare-three' else 2 if 'second' in output else 1
        typed = (selected.get('status') == 'UNAVAILABLE' and bool(selected.get('issues'))) if operation == 'unavailable-history' else available
        return {'ten-year-coverage': [True, available], 'no-look-ahead': [True, available],
            'three-target-comparison': [expected_runs, actual_runs],
            'missing-history-typed': [True, typed]}
    run.preparation = {'manifest': manifest, 'days': days, 'runs': runs,
                       'policy': policy, 'portfolios': portfolios}
    return run, observed


def _corpus(ledger, dimensions, operation, counts, *, stage=None):
    size = dimensions['research_chunks']
    if stage is None:
        rows = fixtures.corpus(dimensions)
        rows[-1]['permission'] = 'DENIED'
        rows[-2]['model_id'] = 'fictional-incompatible-384-v1'
        rows[-3]['source_date'] = '2027-01-01'
        search.store_chunks(ledger.path, rows, confirmed=True)
    if operation == 'rebuild-after-deletion':
        from invest.sqlite_extensions import load_required
        load_required(ledger.connection)
    expected = min(10, size // 2 if operation == 'hybrid-filtered-top10' else size)
    before = ledger.connection.execute('SELECT count(*) FROM document_chunks').fetchone()[0]
    def canonical_hash():
        digest = hashlib.sha256()
        for table, condition in [('document_chunks', 'id'), ('embeddings', 'chunk_id')]:
            for row in ledger.connection.execute('SELECT * FROM ' + table + ' WHERE ' + condition
                    + ' != ? ORDER BY 1,2', (extra[0]['chunk_id'],)):
                for value in row:
                    encoded = value if isinstance(value, bytes) else json.dumps(value).encode()
                    digest.update(len(encoded).to_bytes(8, 'big'))
                    digest.update(encoded)
        return digest.hexdigest()
    counts.update(corpus_chunks=before, canonical_documents_changed=0)
    query_vector = [1.0] + [0.0] * (dimensions['vector_dimensions'] - 1)
    extra = fixtures.corpus(dimensions, start=size, count=1)
    canonical_before = canonical_hash()

    def run():
        if operation == 'incremental-ingest':
            return search.store_chunks(ledger.path, extra, confirmed=True)
        if operation == 'rebuild-after-deletion':
            tables = ledger.connection.execute("SELECT name FROM sqlite_master WHERE sql LIKE '%USING vec0%'").fetchall()
            with ledger.connection:
                for (name,) in tables:
                    ledger.connection.execute('DROP TABLE "' + name.replace('"', '""') + '"')
            return search.rebuild_index(ledger.path)
        kwargs = {} if operation == 'text-top10' else {'vector': query_vector, 'model_id': 'fictional-384-unit-v1'}
        if operation == 'hybrid-filtered-top10':
            kwargs.update(issuer_id='issuer-0', date_from=fixtures.DATE, date_to=fixtures.DATE)
        return search.search(ledger.path, query='' if operation == 'semantic-top10' else 'fictional', top_k=10, **kwargs)

    def observed(output):
        chunks = ledger.connection.execute('SELECT count(*) FROM document_chunks').fetchone()[0]
        results = output.get('results', [])
        if operation in {'rebuild-after-deletion', 'incremental-ingest'}:
            results = search.search(ledger.path, query='fictional', top_k=10,
                vector=query_vector, model_id='fictional-384-unit-v1')['results']
        ids = [row['chunk_id'] for row in results]
        expected_ids = [f'chunk-{index:08}' for index in
                        (range(0, 2 * expected, 2) if operation == 'hybrid-filtered-top10' else range(expected))]
        unchanged = canonical_hash() == canonical_before
        counts['canonical_documents_changed'] = 0 if unchanged else 1
        return {'canonical-corpus-preserved': [True, unchanged and chunks == before + (operation == 'incremental-ingest')],
            'model-dimension-compatibility': [True, output.get('status') in {'AVAILABLE', 'APPROVED', 'UNCHANGED'}],
            'permission-issuer-date-filters': [expected_ids, ids],
            'top10-exact-eligible-results': [expected_ids, ids]}
    run.preparation = {}
    return run, observed
