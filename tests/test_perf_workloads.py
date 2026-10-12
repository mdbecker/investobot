"""Every declared critical operation is measured independently on real offline state."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / 'benchmarks/cases.json').read_text())
REQUIRED_OPERATIONS = {
    'P01': 'cli-startup tools-list tools-describe dashboard-overview',
    'P02': 'html-preview reconcile apply idempotent-reimport check',
    'P03': 'activity-append corrected-snapshot summary planning-read',
    'P04': 'backup verify restore-staging schema-migration manifest-verify',
    'P05': 'household-performance account-performance linked-flow-metrics incomplete-coverage',
    'P06': 'lots specific-disposal budget harvest-candidates harvest-plan household-wash-review',
    'P07': 'target-diff simulate monthly-proposal quarterly-proposal',
    'P08': 'persist-20-plans list compare-20 show markdown-export',
    'P10': 'recursive-exposure top-issuers research-universe incomplete-coverage',
    'P11': 'data-snapshot pinned-parquet-read temporal-join observation-aggregation',
    'P12': 'run-ten-years compare-three identical-repeat unavailable-history',
    'P14': 'text-top10 semantic-top10 hybrid-filtered-top10 rebuild-after-deletion incremental-ingest',
    'P15': 'monthly-report-sequence top-issuer-research-sequence',
}
REQUIRED_OPERATIONS['P09'] = ' '.join(
    f'{operation}-{cache}' for operation in
    ('holdings', 'compare', 'search', 'replacements', 'screen', 'history-read', 'history-metrics')
    for cache in ('hit', 'miss'))
REQUIRED_OPERATIONS['P13'] = ' '.join(
    [f'{specialty}-{operation}' for specialty in
     ('news', 'political', 'earnings', 'competitive', 'insiders', 'fund-diligence')
     for operation in ('validate', 'import')]
    + ['history-list', 'context', 'changes', 'compare', 'portfolio-report'])
for family, operations in {
    'P03': ['linked-cash-transfer'], 'P05': ['hypothetical-risk'],
    'P09': ['quote-hit', 'quote-miss'],
    'P13': [f'{specialty}-{operation}' for specialty in
            ('news', 'political', 'earnings', 'competitive', 'insiders', 'fund-diligence')
            for operation in ('list', 'show', 'summary')]
           + ['competitive-matrix', 'insiders-activity', 'insiders-ownership',
              'fund-diligence-holdings', 'research-plan'],
}.items():
    REQUIRED_OPERATIONS[family] += ' ' + ' '.join(operations)
REQUIRED = {f'{family}.{operation}' for family, operations in REQUIRED_OPERATIONS.items()
            for operation in operations.split()}
CASES = {case['id']: case for case in MANIFEST['cases']}
scenarios('features/performance/workloads.feature')


@pytest.fixture
def workload(tmp_path):
    return {'root': tmp_path}


def invoke(workload, *arguments):
    script = ROOT / 'scripts/perf.py'
    assert script.is_file(), 'Missing real P01–P15 performance runner'
    result = subprocess.run([sys.executable, str(script), *arguments], cwd=workload['root'],
        env=dict(os.environ, INVEST_DB=str(workload['root'] / 'never-selected.db')),
        capture_output=True, text=True, check=False, timeout=180)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert not (workload['root'] / 'never-selected.db').exists()
    return report


def assert_sha(value):
    assert re.fullmatch(r'[a-f0-9]{64}', value)


@given('the complete fixed critical-workflow inventory')
def inventory(workload):
    assert set(MANIFEST['required_cases']) == REQUIRED
    assert set(CASES) == REQUIRED
    assert len(CASES) == len(MANIFEST['cases']) == 114
    assert MANIFEST['seed'] == 271828
    assert MANIFEST['fixed_clock'] == '2026-10-10T12:00:00Z'
    assert MANIFEST['profiles']['medium'] == {
        'accounts': 10, 'positions': 1000, 'lots': 2000, 'accepted_snapshots': 200,
        'saved_plans': 20, 'history_years': 10, 'funds': 20, 'constituents_per_fund': 1000,
        'nested_levels': 3, 'fund_vintages': 1, 'parquet_observations': 500000,
        'research_chunks': 10000, 'vector_dimensions': 384, 'backup_fixture_bytes': 209715200}
    assert MANIFEST['profiles']['stress'] == {
        'accounts': 40, 'positions': 4000, 'lots': 8000, 'accepted_snapshots': 800,
        'saved_plans': 80, 'history_years': 10, 'funds': 80, 'constituents_per_fund': 4000,
        'nested_levels': 3, 'fund_vintages': 12, 'parquet_observations': 2000000,
        'research_chunks': 100000, 'vector_dimensions': 384, 'backup_fixture_bytes': 209715200}
    for case in CASES.values():
        assert case['profile'] == {'pr': 'medium', 'extended': 'stress', 'integration': 'test'}
        assert case['boundary'] and case['workflow'] and case['invariant']
        assert isinstance(case['mutates'], bool)
        assert case['repetitions']['pr'] == 7
        assert case['repetitions']['extended'] in (3, 21)
        assert case['warmups'] == 1 and case['min_batch_elapsed_ms'] == 200
        assert case['budget_ns'] > 0 and case['budget_stat'] in ('max', 'p95')
        assert case['scalability_partner']['case_id'] == case['id']
        assert case['scalability_partner']['scales'] == [1, 4]
        assert case['scalability_partner']['max_elapsed_ratio'] == 6.0


@when('runnable inventory coverage is checked')
def coverage(workload):
    workload['coverage'] = invoke(workload, 'coverage')


@then('every named subcase is runnable with no unclassified expensive public path')
def covered(workload):
    report = workload['coverage']
    assert report['status'] == 'PASS'
    assert set(report['runnable_cases']) == REQUIRED
    assert report['missing_cases'] == []
    assert report['unclassified_paths'] == []
    assert report['classified_paths']
    for exemption in report.get('exemptions', []):
        assert exemption['path'] and exemption['reason'] and exemption['reviewed'] is True


@given(parsers.parse('the isolated real workload {case_id}'))
def selected(workload, case_id):
    inventory(workload)
    workload['case_id'] = case_id
    assert case_id in REQUIRED


@when('one explicitly reduced test-profile observation is measured offline')
def measured(workload):
    workload['report'] = invoke(workload, 'run', '--suite', 'pr', '--profile', 'test',
                                '--case', workload['case_id'], '--observations', '1')


@then('the separately timed operation proves correct output and complete test-profile counts')
def correct(workload):
    report = workload['report']
    assert report['fixture']['recipe_version'] == MANIFEST['recipe_version']
    assert_sha(report['fixture']['hash'])
    assert report['fixture']['dimensions'] == MANIFEST['profiles']['test']
    assert report['runner']['profile'] == 'test'
    assert report['runner']['network'] == 'none'
    assert report['runner']['disposable'] is True
    assert report['runner']['warmups'] == 1
    assert report['runner']['fixture_preparation_in_timing'] is False
    assert report['runner']['docker_startup_in_timing'] is False
    assert report['commit']
    assert_sha(report['runner']['source_hash'])
    assert set(report['cases']) == {workload['case_id']}
    case = report['cases'][workload['case_id']]
    assert case['status'] == 'PASS'
    assert len(case['samples']) == 1
    sample = case['samples'][0]
    for metric in ('elapsed_ns', 'peak_rss_bytes', 'persisted_bytes', 'temp_bytes'):
        assert isinstance(sample[metric], int) and sample[metric] >= 0
    assert sample['elapsed_ns'] > 0 and sample['peak_rss_bytes'] > 0
    assert sample['exit_code'] == 0
    assert_sha(sample['output_hash'])
    assert sample['counts']
    required_counts = {
        'P02': ('positions', 'lots'), 'P03': ('positions', 'lots'),
        'P05': ('history_years',), 'P06': ('lots',), 'P07': ('positions', 'lots'),
        'P08': ('saved_plans',), 'P09': ('funds',), 'P10': ('funds', 'nested_levels'),
        'P11': ('parquet_observations',), 'P12': ('history_years',),
        'P14': ('research_chunks', 'vector_dimensions'),
    }
    family = CASES[workload['case_id']]['family']
    for key in required_counts.get(family, ()):
        assert sample['counts'][key] == MANIFEST['profiles']['test'][key]
    if CASES[workload['case_id']]['mutates']:
        assert sample['fresh_process'] is True
        assert_sha(sample['input_state_hash'])
    assert set(sample['invariant_results']) == set(CASES[workload['case_id']]['invariant'])
    for result in sample['invariant_results'].values():
        assert result['passed'] is True
        assert result['expected'] == result['observed']
    assert report['runner']['workspace_removed'] is True


def test_new_public_expensive_command_requires_explicit_inventory_classification():
    assert (ROOT / 'benchmarks/gates.py').is_file(), 'Missing public inventory validator'
    from benchmarks.gates import validate_inventory

    descriptors = [*MANIFEST['public_paths'], {'command': 'portfolio.fictional-expensive-scan',
                                             'performance': 'expensive', 'required_cases': []}]
    result = validate_inventory(MANIFEST, descriptors)
    assert result['status'] == 'FAIL'
    assert 'portfolio.fictional-expensive-scan' in json.dumps(result)


def test_extended_bulk_rebuild_uses_three_samples_and_no_fabricated_p95(workload):
    report = invoke(workload, 'run', '--suite', 'extended', '--profile', 'test',
                    '--case', 'P14.rebuild-after-deletion', '--observations', '3')
    case = report['cases']['P14.rebuild-after-deletion']
    assert len(case['samples']) == 3
    assert case['p95_ns'] is None
    assert all(sample['counts']['vector_dimensions'] == 384 for sample in case['samples'])
    assert all(sample['counts']['corpus_chunks'] == 24 for sample in case['samples'])
    assert all(sample['counts']['canonical_documents_changed'] == 0 for sample in case['samples'])


def test_mutation_observations_start_from_identical_frozen_input_and_repeat_exact_outcomes(workload):
    report = invoke(workload, 'run', '--suite', 'pr', '--profile', 'test',
                    '--case', 'P03.activity-append', '--observations', '2')
    samples = report['cases']['P03.activity-append']['samples']
    assert len(samples) == 2
    assert_sha(samples[0]['input_state_hash'])
    assert samples[0]['input_state_hash'] == samples[1]['input_state_hash']
    assert samples[0]['counts'] == samples[1]['counts']
    assert samples[0]['output_hash'] == samples[1]['output_hash']
    assert samples[0]['counts']['new_activities'] == 1
    assert all(sample['fresh_process'] is True for sample in samples)


def test_twenty_plan_fixture_repeat_has_distinct_plans_and_reproducible_hash(workload):
    first = invoke(workload, 'run', '--suite', 'pr', '--profile', 'test',
                   '--case', 'P08.persist-20-plans', '--observations', '1')
    second = invoke(workload, 'run', '--suite', 'pr', '--profile', 'test',
                    '--case', 'P08.persist-20-plans', '--observations', '1')
    assert first['fixture']['hash'] == second['fixture']['hash']
    a = first['cases']['P08.persist-20-plans']['samples'][0]
    b = second['cases']['P08.persist-20-plans']['samples'][0]
    assert a['counts']['distinct_new_plans'] == b['counts']['distinct_new_plans'] == 20
    assert a['output_hash'] == b['output_hash']
