"""Prepared analytical workers reconstruct closures from independent local copies."""

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from benchmarks import analytics_workloads

ROOT = Path(__file__).resolve().parents[1]
DIMENSIONS = json.loads((ROOT / 'benchmarks/cases.json').read_text())['profiles']['test']


def tree_hash(root):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob('*') if path.is_file()}


@pytest.mark.parametrize('case_id', ['P09.holdings-hit', 'P09.holdings-miss',
    'P10.recursive-exposure', 'P11.temporal-join', 'P12.compare-three',
    'P13.news-list', 'P14.semantic-top10', 'P15.monthly-report-sequence'])
def test_prepared_files_hydrate_fresh_workers_without_reacceptance(tmp_path, case_id):
    template = tmp_path / 'template'
    prepared = analytics_workloads.prepare(case_id, template, DIMENSIONS, reuse=False)
    prepared.close()
    assert list(template.rglob('*.json')), 'Reuse needs JSON metadata, never pickled closures'
    baseline = tree_hash(template)
    shutil.copytree(template, tmp_path / 'first')
    shutil.copytree(template, tmp_path / 'second')
    first = analytics_workloads.prepare(case_id, tmp_path / 'first', DIMENSIONS, reuse=True)
    second = analytics_workloads.prepare(case_id, tmp_path / 'second', DIMENSIONS, reuse=True)
    try:
        initial = first.operation()
        assert all(row['passed'] for row in first.verify(initial).values())
        other = second.operation()
        assert all(row['passed'] for row in second.verify(other).values())
        assert initial == other
        assert first.input_state_hash == second.input_state_hash
        assert tree_hash(template) == baseline
        first.close()
        second.reset()
        assert second.operation() == other
        assert all(row['passed'] for row in second.verify(other).values())
        assert tree_hash(template) == baseline
        assert not any(path.name.endswith(('-wal', '-shm')) for path in template.rglob('*'))
    finally:
        first.close()
        second.close()


def test_reused_mutating_corpus_keeps_original_canonical_template(tmp_path):
    template = tmp_path / 'template'
    prepared = analytics_workloads.prepare('P14.incremental-ingest', template, DIMENSIONS, reuse=False)
    prepared.close()
    baseline = tree_hash(template)
    shutil.copytree(template, tmp_path / 'worker')
    worker = analytics_workloads.prepare('P14.incremental-ingest', tmp_path / 'worker', DIMENSIONS, reuse=True)
    try:
        first = worker.operation()
        assert all(row['passed'] for row in worker.verify(first).values())
        worker.reset()
        assert worker.operation() == first
        assert all(row['passed'] for row in worker.verify(first).values())
        assert tree_hash(template) == baseline
    finally:
        worker.close()


def test_hydration_does_not_rewrite_immutable_parquet_inputs(tmp_path):
    template = tmp_path / 'template'
    prepared = analytics_workloads.prepare('P11.temporal-join', template, DIMENSIONS, reuse=False)
    prepared.close()
    shutil.copytree(template, tmp_path / 'worker')
    files = list((tmp_path / 'worker').rglob('*.parquet'))
    assert files
    evidence = {str(path): (path.stat().st_mtime_ns, hashlib.sha256(path.read_bytes()).hexdigest()) for path in files}
    worker = analytics_workloads.prepare('P11.temporal-join', tmp_path / 'worker', DIMENSIONS, reuse=True)
    try:
        result = worker.operation()
        assert result['rows'] == DIMENSIONS['parquet_observations']
        assert all(row['passed'] for row in worker.verify(result).values())
        assert evidence == {str(path): (path.stat().st_mtime_ns, hashlib.sha256(path.read_bytes()).hexdigest()) for path in files}
    finally:
        worker.close()
