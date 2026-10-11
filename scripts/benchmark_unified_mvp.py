"""Offline synthetic benchmark; Docker only, no private ledger or network access."""

import argparse
import hashlib
import json
import math
import os
import platform
import tempfile
from pathlib import Path
from time import perf_counter

import duckdb

from invest import analytics_store, backup, search
from invest.ledger import Ledger
from invest.lookthrough import research_universe
from invest.parsers.generic import parse_html
from invest.planning import propose
from invest.plans import compare, list_plans
from invest.targets import save

DATE = '2026-10-10'
DEFAULT_CHUNKS = 100000


def timed(call, count=1):
    started = perf_counter()
    value = call()
    return value, {'count': count, 'elapsed_ms': (perf_counter() - started) * 1000}


def percentile(values, fraction):
    values = sorted(values)
    index = (len(values) - 1) * fraction
    lower = math.floor(index)
    return values[lower] + (values[math.ceil(index)] - values[lower]) * (index - lower)


def measure(chunks, queries):
    fixture_hash = hashlib.sha256()
    workloads = {}
    with tempfile.TemporaryDirectory(prefix='investobot-unified-benchmark-') as temporary:
        root = Path(temporary)
        ledger, workloads['startup'] = timed(lambda: Ledger(root / 'synthetic.db'))
        try:
            html = ('<table><tr><th>Symbol</th><th>Quantity</th><th>Price</th><th>Market Value</th></tr>'
                    '<tr><td>BENCH</td><td>10</td><td>100</td><td>1000</td></tr>'
                    '<tr><td>CASH</td><td></td><td></td><td>2000</td></tr></table>')
            fixture_hash.update(html.encode())
            candidate, workloads['import'] = timed(lambda: parse_html(
                html, 'synthetic', tax_status='TAX_FREE', as_of=DATE,
                positions_complete=True, lots_complete=False, data_environment='SYNTHETIC'))
            _, workloads['reconcile'] = timed(lambda: ledger.reconcile(candidate))
            ledger.apply(candidate)
            identities = []
            for index in range(20):
                cik = f'{index + 1:010d}'
                record = {'ticker': f'ISS{index:02d}', 'name': f'Fictional issuer {index}',
                          'currency': 'USD', 'asset_type': 'STOCK', 'source': 'Reviewed fictional source',
                          'cik': cik, 'issuer_id': cik, 'data_environment': 'SYNTHETIC',
                          'issuer_identity_evidence': {'cik': cik, 'reviewed': True,
                            'source': 'Reviewed fictional original record',
                            'source_locator': f'https://issuer{index}.example/identity'}}
                fixture_hash.update(json.dumps(record, sort_keys=True).encode())
                identities.append(ledger.register_security(record)['id'])
            bench = ledger.resolve('BENCH')['id']
            target = save(ledger, {'name': 'Fictional target', 'target_allocations': {bench: '1'},
                'planning_constraints': {'eligible_accounts': ['synthetic'],
                                        'permitted_securities': {'synthetic': [bench]}}})
            policy = {'version': 'fictional-benchmark-1', 'data_environment': 'SYNTHETIC',
                      'fee_per_trade': '0', 'permissions': {'synthetic': {bench: {
                        'can_buy': True, 'can_sell': False, 'can_hold': True, 'share_increment': '1'}}}}
            plans = [propose(ledger, target['id'], policy=policy, mode='contributions-only',
                             as_of=DATE, prices={bench: '100'})['id'] for _ in range(20)]
            listed, workloads['plan_list'] = timed(lambda: list_plans(ledger), 20)
            compared, workloads['plan_compare'] = timed(lambda: compare(ledger, *plans), 20)
            assert len(listed['plans']) == len(compared['plans']) == 20
            assert ledger.connection.execute('SELECT count(*) FROM plan_runs').fetchone()[0] == 20
            assert all(json.loads(row[0])['storage_identity']['manifest_hash'] for row in
                       ledger.connection.execute('SELECT details_json FROM plan_runs'))
            parquet = root / 'history.parquet'
            writer = duckdb.connect(':memory:')
            try:
                writer.execute("CREATE TABLE history AS SELECT 'BENCH' AS ticker, DATE '2026-10-09' AS date, '100' AS adjusted_close")
                writer.execute('COPY history TO ? (FORMAT PARQUET)', [str(parquet)])
            finally:
                writer.close()
            parquet_hash = hashlib.sha256(parquet.read_bytes()).hexdigest()
            fixture_hash.update(parquet_hash.encode())
            manifest = {'data_environment': 'SYNTHETIC', 'artifacts': [{
                'kind': 'DIVIDEND_ADJUSTED_PRICES', 'relative_path': 'history.parquet',
                'sha256': parquet_hash, 'provider': 'FICTIONAL', 'observed_at': DATE,
                'as_of': DATE, 'data_environment': 'SYNTHETIC'}]}
            pinned = analytics_store.snapshot(ledger, manifest, confirm=True, artifact_root=root)
            assert pinned['status'] == 'AVAILABLE', pinned

            def historical():
                with analytics_store.analytical_connection(ledger, pinned['manifest_id'], artifact_root=root) as connection:
                    result = connection.execute('SELECT count(*) FROM artifact_0 h JOIN ledger.securities s ON h.ticker=s.ticker').fetchone()[0]
                    assert result == 1
                    return result
            _, workloads['historical_parquet'] = timed(historical)
            state = ledger.planning_state()
            lookup_state = dict(state, positions=[{
                'account_id': 'synthetic', 'security_id': identity, 'quantity': '1',
                'market_value': '100', 'currency': 'USD'} for identity in identities])
            universe, workloads['top_n_lookthrough'] = timed(lambda: research_universe(
                lookup_state, {}, as_of=DATE, top=20, min_exposure='0'), 20)
            assert len(universe['companies']) == 20
            archive, workloads['backup'] = timed(lambda: backup.create(
                ledger.path, root / 'verified.tar.gz', artifact_root=root))
            assert archive['status'] == 'AVAILABLE', archive
            before = ledger.planning_state()
            corpus = []
            for index in range(chunks):
                text = f'Fictional permitted issuer evidence passage {index:06d}.'
                row = {'chunk_id': f'chunk-{index:06d}', 'document_id': f'document-{index:06d}',
                       'text': text, 'source_url': f'https://fictional.example/evidence/{index}',
                       'source_date': DATE, 'permission': 'PERMITTED', 'license': 'Reviewed fictional permission',
                       'data_environment': 'SYNTHETIC', 'offset_start': 0, 'offset_end': len(text),
                       'content_hash': hashlib.sha256(text.encode()).hexdigest(),
                       'model_id': 'fictional-unit-vector-v1', 'vector': [1.0, 0.0]}
                fixture_hash.update(json.dumps(row, sort_keys=True).encode())
                corpus.append(row)
            _, workloads['corpus_build'] = timed(lambda rows=corpus: search.store_chunks(
                ledger.path, rows, confirmed=True), chunks)
            del corpus
            workloads['corpus_build']['size_bytes'] = sum(path.stat().st_size for path in root.glob('synthetic.db*') if path.is_file())
            for mode in ['text_search', 'vector_search']:
                durations = []
                for _ in range(queries):
                    result, measured = timed(lambda: search.search(ledger.path, query='fictional', top_k=10,
                        **({'vector': [1.0, 0.0], 'model_id': 'fictional-unit-vector-v1'} if mode == 'vector_search' else {})))
                    assert result['status'] == 'AVAILABLE', result
                    durations.append(measured['elapsed_ms'])
                workloads[mode] = {'count': queries, 'elapsed_ms': sum(durations),
                    'p50_ms': percentile(durations, 0.5), 'p95_ms': percentile(durations, 0.95),
                    'result_count': len(result['results'])}
            unchanged = ledger.planning_state() == before
            assert unchanged
            vector_connection = search.open_search_connection(ledger.path, readonly=True)
            try:
                vector_version = vector_connection.execute('SELECT vec_version()').fetchone()[0]
            finally:
                vector_connection.close()
        finally:
            ledger.connection.close()
    return {'schema_version': '1', 'data_environment': 'SYNTHETIC',
            'fixture_sha256': fixture_hash.hexdigest(),
            'parameters': {'chunks': chunks, 'queries': queries, 'top_k': 10, 'default_chunks': DEFAULT_CHUNKS},
            'hardware': {'machine': platform.machine(), 'processor': platform.processor(),
                'cpu_count': os.cpu_count(), 'memory_bytes': os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')},
            'container': {'docker': True, 'network': 'none', 'python': platform.python_version(),
                          'duckdb': duckdb.__version__, 'sqlite_vec': vector_version},
            'workloads': workloads, 'canonical_financial_state_unchanged': unchanged,
            'disposable_workspace_removed': not root.exists(),
            'assumptions': {'vector_dimension': 2, 'vector_model': 'fictional-unit-vector-v1',
                'cache': 'warm repeated calls; no OS cold-cache claim',
                'lookthrough': 'explicit hypothetical 20-issuer universe, not accepted holdings',
                'memory': 'kernel physical memory; container limit may differ',
                'timings': 'perf_counter wall time, no external APIs, no fixed throughput target'}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chunks', type=int, default=DEFAULT_CHUNKS)
    parser.add_argument('--queries', type=int, default=20)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.chunks < 10 or args.queries < 1:
        parser.error('chunks must be at least 10 and queries positive')
    if not Path('/.dockerenv').exists():
        parser.error('Run only in a disposable Docker container')
    routes = Path('/proc/net/route').read_text().splitlines()[1:]
    if any(line.split()[1] == '00000000' for line in routes if len(line.split()) > 1):
        parser.error('Run Docker with --network none')
    rendered = json.dumps(measure(args.chunks, args.queries), sort_keys=True, indent=2) + '\n'
    if args.output:
        args.output.write_text(rendered)
    print(rendered, end='')


if __name__ == '__main__':
    main()
