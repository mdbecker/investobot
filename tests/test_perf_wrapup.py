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
