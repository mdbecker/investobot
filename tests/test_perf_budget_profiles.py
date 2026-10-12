"""Absolute acceptance measures the PRD's named sizes, independently of stress."""
from copy import deepcopy

import pytest

from benchmarks import gates, paired, runner


def test_absolute_plan_preserves_named_sizes_and_import_p95():
    definitions = runner.manifest()
    original = deepcopy(definitions)
    assert hasattr(paired, 'certification_plan'), 'Absolute sizes have no independent contract'
    plan = paired.certification_plan(definitions)
    assert {row['id'] for row in plan} == {row['id'] for row in definitions['cases']}
    for row in plan:
        expected = definitions['profiles']['stress' if row['id'].startswith('P14.') else 'medium']
        assert row['dimensions'] == expected
        assert row['observations'] == (21 if row['budget_stat'] == 'p95' else 3)
    apply = next(row for row in plan if row['id'] == 'P02.apply')
    assert apply['budget_stat'] == 'p95' and apply['observations'] == 21
    assert apply['budget_ns'] == 5_000_000_000
    assert definitions == original


def test_scaling_small_supplies_valid_absolute_observation_counts():
    definitions = runner.manifest()
    assert hasattr(paired, 'certification_plan'), 'Missing release budget sampling contract'
    budgets = {row['id']: row for row in paired.certification_plan(definitions)}
    for row in paired.scaling_plan(definitions):
        if not row['case']['id'].startswith('P14.'):
            assert row['observations'] >= budgets[row['case']['id']]['observations']


def test_certification_rejects_wrong_size_even_with_fast_correct_samples():
    medium = runner.manifest()['profiles']['medium']
    samples = [{'elapsed_ns': 1_000_000_000, 'peak_rss_bytes': 1000,
                'persisted_bytes': 1000, 'temp_bytes': 0, 'exit_code': 0,
                'output_hash': 'a' * 64, 'counts': {'positions': 1000}} for _ in range(21)]
    report = {'runner': paired.runtime_for_engine({'Architecture': 'aarch64'}),
              'fixture': {'dimensions': medium},
              'cases': {'P02.apply': {'status': 'PASS', 'samples': samples}}}
    contract = [{'id': 'P02.apply', 'mode': 'extended_retrieval', 'budget_stat': 'p95',
                 'budget_ns': 5_000_000_000, 'dimensions': medium}]
    assert gates.certify(report, contract)['status'] == 'PASS'
    report['fixture']['dimensions'] = runner.manifest()['profiles']['stress']
    result = gates.certify(report, contract)
    assert result['status'] == 'FAIL'
    assert any(row['code'] == 'ABSOLUTE_WORKLOAD_MISMATCH' for row in result['issues'])


def test_certification_assembles_medium_and_100k_vector_native_evidence():
    definitions = runner.manifest()
    assert hasattr(paired, 'certification_report'), 'Stress reports incorrectly certify medium budgets'
    stress = {'commit': 'candidate', 'runner': {'id': 'same-runner'},
              'fixture': {'dimensions': definitions['profiles']['stress']}, 'cases': {}}
    pairs = []
    for case in definitions['cases']:
        result = {'status': 'PASS', 'samples': [{'output_hash': case['id']}]}
        stress['cases'][case['id']] = deepcopy(result)
        native = {**stress, 'fixture': {'dimensions': definitions['profiles']['medium']},
                  'cases': {case['id']: result}}
        pairs.append({'case_id': case['id'], 'small_native': native})
    original = deepcopy((stress, pairs))
    report = paired.certification_report(stress, pairs, definitions)
    for identity, case in report['cases'].items():
        expected = definitions['profiles']['stress' if identity.startswith('P14.') else 'medium']
        assert case['fixture_dimensions'] == expected
        assert case['samples'] == stress['cases'][identity]['samples']
    assert (stress, pairs) == original


@pytest.mark.parametrize('field', ['commit', 'runner', 'dimensions', 'missing'])
def test_absolute_report_rejects_unrelated_or_missing_native_evidence(field):
    definitions = deepcopy(runner.manifest())
    definitions['cases'] = [next(case for case in definitions['cases'] if case['id'] == 'P02.apply')]
    assert hasattr(paired, 'certification_report'), 'No verified budget evidence projection'
    native = {'commit': 'candidate', 'runner': {'id': 'same-runner'},
              'fixture': {'dimensions': definitions['profiles']['medium']},
              'cases': {'P02.apply': {'status': 'PASS', 'samples': []}}}
    stress = {**native, 'fixture': {'dimensions': definitions['profiles']['stress']}}
    pairs = [{'case_id': 'P02.apply', 'small_native': deepcopy(native)}]
    selected = pairs[0]['small_native']
    if field == 'dimensions':
        selected['fixture']['dimensions'] = definitions['profiles']['stress']
    elif field == 'missing':
        pairs.clear()
    else:
        selected[field] = 'unrelated'
    with pytest.raises(ValueError):
        paired.certification_report(stress, pairs, definitions)
