"""The release gate uses eight comparable workflows and confirms noise once."""
from copy import deepcopy

import pytest

from benchmarks import gates, runner


def report(multiplier=1):
    return {'recipe_hash': 'fixed', 'runner': {'machine': 'same'}, 'cases': {
        str(index): {'input_hash': 'input', 'output_hash': 'output', 'counts': {'rows': 12},
                     'batch': 2, 'samples_ns': [400_000_000 * multiplier] * 5}
        for index in range(8)}}


def test_wrapup_has_exactly_eight_representative_boundaries():
    definitions = runner.recipes()
    assert len(definitions) == 8
    assert len({case['id'] for case in definitions}) == 8
    assert all(case['boundary'] and case['operations'] for case in definitions)


def test_fixed_workflows_use_representative_single_user_inputs():
    definitions = runner.manifest()
    dimensions = definitions['profiles'][definitions.get('profile', 'test')]
    assert dimensions['positions'] == 200
    assert dimensions['lots'] == 400
    assert dimensions['parquet_observations'] == 4000
    assert dimensions['research_chunks'] == 1000
    assert dimensions['history_years'] == 10


def test_one_slow_measurement_requires_complete_confirmation():
    assert gates.compare_pair(report(), report(1.26))['status'] == 'CONFIRM'
    assert gates.compare_pair(report(), report(1.26), confirmation=(report(), report()))['status'] == 'PASS'
    assert gates.compare_pair(report(), report(1.26), confirmation=(report(), report(1.26)))['status'] == 'FAIL'


def test_exact_25_percent_is_accepted():
    assert gates.compare_pair(report(), report(1.25))['status'] == 'PASS'


@pytest.mark.parametrize('alteration', ['short', 'missing', 'output', 'recipe', 'runner', 'count'])
def test_invalid_evidence_cannot_establish_a_regression(alteration):
    candidate = deepcopy(report(2))
    if alteration == 'short': candidate['cases']['0']['samples_ns'][0] = 199_999_999
    if alteration == 'missing': candidate['cases']['0']['samples_ns'].pop()
    if alteration == 'output': candidate['cases']['0']['output_hash'] = 'different'
    if alteration == 'recipe': candidate['recipe_hash'] = 'different'
    if alteration == 'runner': candidate['runner']['machine'] = 'different'
    if alteration == 'count': candidate['cases']['0']['counts']['rows'] = 13
    assert gates.compare_pair(report(), candidate)['status'] == 'INVALID'


def test_confirmation_must_cover_the_complete_suite():
    incomplete = report(1.26)
    incomplete['cases'].pop('7')
    assert gates.compare_pair(report(), report(1.26), confirmation=(report(), incomplete))['status'] == 'INVALID'


@pytest.mark.parametrize('operation', ['P06.budget', 'P10.recursive-exposure'])
def test_identical_synthetic_inputs_have_repeatable_financial_hashes(tmp_path, operation):
    from benchmarks.analytics_workloads import prepare as analytical
    from benchmarks.financial_workloads import prepare as financial
    prepare = financial if operation.startswith('P06') else analytical
    hashes = []
    for attempt in range(2):
        fixture = prepare(operation, tmp_path / str(attempt), runner.manifest()['profiles']['test'])
        try:
            result = fixture.operation()
            assert all(proof['passed'] for proof in fixture.verify(result).values())
            hashes.append(fixture.input_state_hash)
        finally:
            fixture.close()
    assert hashes[0] == hashes[1]


@pytest.mark.parametrize('operation,field,value', [
    ('P12.run-ten-years', 'history_years', 9),
    ('P14.semantic-top10', 'research_chunks', 25),
    ('P11.temporal-join', 'parquet_observations', 121),
])
def test_changed_historical_or_corpus_evidence_changes_input_fingerprint(tmp_path, operation, field, value):
    from benchmarks.analytics_workloads import prepare
    dimensions = runner.manifest()['profiles']['test']
    hashes = []
    for attempt, supplied in enumerate((dimensions, dict(dimensions, **{field: value}))):
        fixture = prepare(operation, tmp_path / str(attempt), supplied)
        try:
            result = fixture.operation()
            assert all(proof['passed'] for proof in fixture.verify(result).values())
            hashes.append(fixture.input_state_hash)
        finally:
            fixture.close()
    assert hashes[0] != hashes[1]


def test_retired_calendar_output_projection_preserves_every_financial_and_policy_field():
    from benchmarks.financial_workloads import foundation_projection

    native = {'algorithm_version': 'contribution-first-hifo-1', 'cadence': {'eligible': True},
              'proposed_actions': [{'type': 'BUY', 'quantity': '4', 'notional': '400'}],
              'estimated_tax_budget_consumption': '0', 'policy': {'source': 'Human reviewed'},
              'issues': [], 'source_state_hash': 'exact-source'}
    candidate = deepcopy(native)
    candidate.pop('cadence')
    assert foundation_projection(native) == candidate
    assert foundation_projection(candidate) == candidate
    native['cadence']['eligible'] = False
    with pytest.raises(ValueError, match='calendar'):
        foundation_projection(native)
