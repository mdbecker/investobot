"""Measurement mechanics supplement all inventory and comparator contracts."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

scenarios('features/performance/execution.feature')


@pytest.fixture
def ctx():
    return {}


@given('a fixed synthetic measurement request')
def request(ctx):
    ctx['case'] = 'P03.activity-append'


@when('two fresh observations execute the same mutation')
def observations(ctx):
    from benchmarks.runner import run

    ctx['result'] = run(suite='pr', profile='test', case=ctx['case'], observations=2)


@then('their input and substantive output proofs match')
def equivalent(ctx):
    rows = ctx['result']['cases'][ctx['case']]['samples']
    assert len(rows) == 2
    assert rows[0]['input_hash'] == rows[1]['input_hash']
    assert rows[0]['output_hash'] == rows[1]['output_hash']
    assert rows[0]['counts'] == rows[1]['counts']
    assert all(row['fresh_process'] and row['exit_code'] == 0 for row in rows)
    assert all(row['elapsed_ns'] >= 200_000_000 for row in rows)
    assert all(row['batch_repetitions'] >= 1 for row in rows)


@given('the release resource contract')
def resource_contract(ctx):
    ctx['limits'] = {'cpus': 2, 'memory_bytes': 4 * 1024 ** 3, 'network': 'none',
                     'machine': 'x86_64'}


@when('a measurement is requested outside the safe runtime')
def unsafe(ctx):
    from benchmarks.runner import validate_runtime

    ctx['result'] = validate_runtime({'docker': False, **ctx['limits']})


@then('it rejects the request before opening a selected ledger')
def rejected(ctx):
    assert ctx['result']['status'] == 'FAIL'
    assert 'UNSAFE_RUNTIME' in {row['code'] for row in ctx['result']['issues']}


@given('reference, base and candidate revisions')
def revisions(ctx):
    ctx['revisions'] = ['reference', 'base', 'candidate']


@when('the statistical observation schedule is generated')
def schedule(ctx):
    from benchmarks.runner import schedule

    ctx['schedule'] = schedule(ctx['revisions'], observations=7)


@then('each revision receives seven observations in rotated order')
def rotated(ctx):
    rows = ctx['schedule']
    assert len(rows) == 7
    assert rows[:3] == [['reference', 'base', 'candidate'],
                        ['base', 'candidate', 'reference'],
                        ['candidate', 'reference', 'base']]
    assert all(sorted(row) == sorted(ctx['revisions']) for row in rows)


@given('a child that times out or is killed')
def killed(ctx):
    ctx['failures'] = [(-9, 'OOM'), (124, 'TIMEOUT')]


@when('the parent captures the measurement')
def capture(ctx):
    from benchmarks.runner import failed_observation

    ctx['results'] = [failed_observation(code, reason) for code, reason in ctx['failures']]


@then('the report retains the failure and cannot certify it')
def retained(ctx):
    for row, (code, reason) in zip(ctx['results'], ctx['failures'], strict=True):
        assert row['exit_code'] == code
        assert row['status'] == 'FAIL'
        assert row['error'] == reason


def test_reference_metadata_is_real_pinned_recipe_and_never_legacy_timing():
    path = Path('benchmarks/reference.json')
    assert path.exists(), 'Reviewed post-MVP reference metadata is absent'
    value = json.loads(path.read_text())
    assert value['reference_commit'] == '7cbf2bed13a0447865403e986662119571217bc6'
    assert value['seed'] == 271828
    assert len(value['recipe_sha256']) == 64
    assert value['legacy_timings_are_gate'] is False
    assert value['approval']['procedure'] == 'explicit-reviewed-rebaseline'


def test_performance_workflow_is_fixed_offline_paired_and_has_no_fuzz_campaign():
    path = Path('.github/workflows/performance.yml')
    assert path.exists(), 'Required fixed performance workflow is absent'
    text = path.read_text()
    for required in ('pull_request:', 'schedule:', 'workflow_dispatch:',
                     '--network none', '--cpus=2', '--memory=4g', 'reference', 'base',
                     'candidate', 'OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
        assert required in text
    assert 'scripts/fuzz.py run' not in text
    assert 'FMP_API_KEY' not in text


def test_small_runner_output_has_real_metric_and_provenance_fields(tmp_path):
    result = subprocess.run([sys.executable, 'scripts/perf.py', 'run', '--suite', 'pr',
                             '--profile', 'test', '--case', 'P01.tools-list',
                             '--observations', '1'], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report['fixture']['recipe_version'] and report['fixture']['hash']
    assert report['runner']['docker'] is True
    assert report['runner']['network'] == 'none'
    assert report['runner']['profile'] == 'test'
    assert report['commit']
    sample = report['cases']['P01.tools-list']['samples'][0]
    for key in ('elapsed_ns', 'peak_rss_bytes', 'persisted_bytes', 'temp_bytes', 'input_hash',
                'output_hash', 'counts', 'exit_code', 'fresh_process', 'batch_repetitions'):
        assert key in sample
    assert sample['exit_code'] == 0 and sample['counts']['commands'] > 0
    assert not list(tmp_path.rglob('*.db'))


def test_common_batch_calibration_preserves_identical_work_across_revisions():
    from benchmarks.runner import common_batch_counts

    counts = common_batch_counts({'reference': {'read': 20_000_000},
                                  'base': {'read': 10_000_000},
                                  'candidate': {'read': 5_000_000}})
    assert counts == {'read': 40}
