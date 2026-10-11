"""Small offline acceptance of the real reproducible unified benchmark workflow."""

import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path


def run_benchmark(tmp_path):
    script = Path(__file__).resolve().parents[1] / 'scripts' / 'benchmark_unified_mvp.py'
    result = subprocess.run([sys.executable, str(script), '--chunks', '12', '--queries', '3'],
                            cwd=tmp_path, env=dict(os.environ, INVEST_DB=str(tmp_path / 'unused.db')),
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_disposable_benchmark_measures_real_workloads_and_reproduces_fixture_hash(tmp_path):
    first = run_benchmark(tmp_path)
    second = run_benchmark(tmp_path)
    assert first['schema_version'] == '1'
    assert first['data_environment'] == 'SYNTHETIC'
    assert re.fullmatch(r'[a-f0-9]{64}', first['fixture_sha256'])
    assert first['fixture_sha256'] == second['fixture_sha256']
    assert first['parameters'] == {'chunks': 12, 'queries': 3, 'top_k': 10,
                                   'default_chunks': 100000}
    assert first['hardware']['machine']
    assert 'processor' in first['hardware']
    assert first['hardware']['cpu_count'] > 0
    assert first['hardware']['memory_bytes'] > 0
    assert first['container']['docker'] is True
    assert first['container']['network'] == 'none'
    for field in ('python', 'duckdb', 'sqlite_vec'):
        assert first['container'][field]
    expected = {'startup', 'import', 'reconcile', 'backup', 'plan_list', 'plan_compare',
                'historical_parquet', 'top_n_lookthrough', 'text_search', 'vector_search',
                'corpus_build'}
    assert set(first['workloads']) == expected
    for name, measured in first['workloads'].items():
        assert measured['count'] > 0, name
        assert math.isfinite(measured['elapsed_ms']) and measured['elapsed_ms'] >= 0, name
    for name in ('plan_list', 'plan_compare'):
        assert first['workloads'][name]['count'] == 20
    for name in ('text_search', 'vector_search'):
        measured = first['workloads'][name]
        assert measured['count'] == 3
        assert 0 <= measured['p50_ms'] <= measured['p95_ms']
        assert measured['result_count'] == 10
    assert first['workloads']['corpus_build']['count'] == 12
    assert first['workloads']['corpus_build']['size_bytes'] > 0
    assert first['canonical_financial_state_unchanged'] is True
    assert first['disposable_workspace_removed'] is True
    assert not (tmp_path / 'unused.db').exists()
    assert not list(tmp_path.rglob('*.db'))
