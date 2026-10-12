"""Matched logical scaling must change the measured workload, not its semantics."""
import importlib
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

from benchmarks.gates import compare_scaling

ROOT = Path(__file__).resolve().parents[1]


def test_scaled_inventory_preserves_temporal_and_vector_semantics():
    scaling = importlib.import_module('benchmarks.scaling')
    base = json.loads((ROOT / 'benchmarks/cases.json').read_text())['profiles']['test']
    original = deepcopy(base)
    scaled = scaling.dimensions('P02.apply', base)
    for key in ('accounts', 'positions', 'lots', 'accepted_snapshots'):
        assert scaled[key] == base[key] * 4
    for key in ('history_years', 'vector_dimensions', 'nested_levels', 'fund_vintages'):
        assert scaled[key] == base[key]
    assert base == original


def test_history_density_and_fund_workloads_have_distinct_scaling_drivers():
    scaling = importlib.import_module('benchmarks.scaling')
    base = json.loads((ROOT / 'benchmarks/cases.json').read_text())['profiles']['test']
    performance = scaling.dimensions('P05.household-performance', base)
    assert performance['history_years'] == 10
    assert performance['history_density'] == base.get('history_density', 1) * 4
    holdings = scaling.dimensions('P09.holdings-hit', base)
    assert holdings['constituents_per_fund'] == base['constituents_per_fund'] * 4
    assert holdings['funds'] == base['funds']
    search = scaling.dimensions('P09.search-hit', base)
    assert search['funds'] == base['funds'] * 4
    assert search['constituents_per_fund'] == base['constituents_per_fund']


def test_scaling_projection_preserves_raw_evidence_and_gates_actual_chunk_count():
    scaling = importlib.import_module('benchmarks.scaling')
    def report(chunks, elapsed):
        return {'commit': 'same-revision', 'runner': {'id': 'same-runner'},
                'fixture': {'hash': str(chunks), 'dimensions': {'research_chunks': chunks,
                                                              'vector_dimensions': 384}},
                'cases': {'P14.text-top10': {'status': 'PASS', 'samples': [{
                    'elapsed_ns': elapsed, 'batch_repetitions': 1, 'peak_rss_bytes': 1000,
                    'persisted_bytes': 1000, 'temp_bytes': 0, 'exit_code': 0,
                    'output_hash': 'a' * 64, 'counts': {'research_chunks': chunks,
                                                       'vector_dimensions': 384}}]}}}
    small, large = report(100, 1_000_000_000), report(400, 8_000_000_000)
    original = deepcopy(small)
    projected = scaling.project(small, 'P14.text-top10')
    row = projected['cases']['P14.text-top10']['samples'][0]
    assert row['counts'] == {'logical_records': 100}
    for key in ('elapsed_ns', 'batch_repetitions', 'peak_rss_bytes', 'persisted_bytes',
                'temp_bytes', 'exit_code', 'output_hash'):
        assert row[key] == small['cases']['P14.text-top10']['samples'][0][key]
    assert projected['fixture'] == small['fixture']
    assert projected['commit'] == small['commit'] and projected['runner'] == small['runner']
    assert small == original
    result = compare_scaling([{'case_id': 'P14.text-top10', 'expected_complexity': 'linear',
                              'small': projected, 'large': scaling.project(large, 'P14.text-top10')}])
    assert result['status'] == 'FAIL'
    assert any(issue['code'] == 'SUPERLINEAR_GROWTH' and issue['ratio'] == 8
               for issue in result['issues'])


def test_public_scaled_run_measures_ninety_six_chunks_and_ten_correct_results():
    process = subprocess.run([sys.executable, str(ROOT / 'scripts/perf.py'), 'run',
        '--profile', 'test', '--case', 'P14.text-top10', '--observations', '1', '--scale', '4'],
        cwd=ROOT, text=True, capture_output=True, timeout=90)
    assert process.returncode == 0, process.stderr
    result = json.loads(process.stdout)
    assert result['fixture']['dimensions']['research_chunks'] == 96
    row = result['cases']['P14.text-top10']['samples'][0]
    assert row['counts']['research_chunks'] == 96
    proof = row['invariant_results']['top10-exact-eligible-results']
    assert proof['passed'] is True and proof['expected'] == proof['observed']
    assert len(proof['observed']) == 10
