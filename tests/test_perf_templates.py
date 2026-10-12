"""Immutable once-built fixture copies, exercised through real worker entry points."""
import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from benchmarks import runner

ROOT = Path(__file__).resolve().parents[1]


def templates():
    try:
        return importlib.import_module('benchmarks.templates')
    except ModuleNotFoundError:
        pytest.fail('Missing reusable checksummed benchmark templates')


def case(identifier):
    return next(row for row in runner.manifest()['cases'] if row['id'] == identifier)


def test_template_clones_are_verified_independent_and_leave_original_unchanged(tmp_path):
    module = templates()
    selected = case('P03.activity-append')
    dimensions = runner.manifest()['profiles']['test']
    original = tmp_path / 'template'
    manifest = module.create(selected, dimensions, original)
    assert manifest['build_count'] == 1 and manifest['source_hash'] == runner.source_hash()
    assert manifest['files'] and manifest['template_hash']
    first, second = tmp_path / 'first', tmp_path / 'second'
    module.clone(original, first, selected, dimensions)
    module.clone(original, second, selected, dimensions)
    baseline = (original / 'financial.db').read_bytes()
    for root in (first, second):
        sample = runner.observe(selected, dimensions, root, repetitions=1, reuse=True)
        assert sample['exit_code'] == 0
        assert all(proof['passed'] for proof in sample['invariant_results'].values())
    assert (original / 'financial.db').read_bytes() == baseline
    assert first != second
    assert not list(original.rglob('*-wal')) and not list(original.rglob('*-shm'))


@pytest.mark.parametrize('mutation', ['checksum', 'dimensions', 'source', 'symlink'])
def test_invalid_template_is_rejected_before_destination_exists(tmp_path, mutation):
    module = templates()
    selected = case('P03.activity-append')
    dimensions = runner.manifest()['profiles']['test']
    original, destination = tmp_path / 'template', tmp_path / 'worker'
    module.create(selected, dimensions, original)
    requested = dict(dimensions)
    if mutation == 'checksum':
        (original / 'financial.db').write_bytes(b'corrupt')
    elif mutation == 'dimensions':
        requested['positions'] *= 4
    elif mutation == 'source':
        path = original / 'template-manifest.json'
        manifest = json.loads(path.read_text())
        manifest['source_hash'] = '0' * 64
        path.write_text(json.dumps(manifest))
    else:
        (original / 'unsafe').symlink_to(tmp_path / 'unrelated')
    with pytest.raises(ValueError):
        module.clone(original, destination, selected, requested)
    assert not destination.exists()


def test_public_runner_prepares_once_and_reuses_warmup_and_samples():
    process = subprocess.run([sys.executable, str(ROOT / 'scripts/perf.py'), 'run',
        '--profile', 'test', '--case', 'P03.activity-append', '--observations', '2',
        '--batch-repetitions', '1'], capture_output=True, text=True, timeout=90)
    assert process.returncode == 0, process.stderr
    report = json.loads(process.stdout)
    assert report['runner']['fixture_builds'] == 1
    assert report['runner']['workspace_removed'] is True
    measurements = report['cases']['P03.activity-append']
    assert measurements['template']['build_count'] == 1
    samples = measurements['samples']
    assert len(samples) == 2
    assert len({row['template_hash'] for row in samples}) == 1
    assert len({row['input_state_hash'] for row in samples}) == 1
    assert all(row['fixture_reused'] is True and row['fresh_process'] is True for row in samples)
