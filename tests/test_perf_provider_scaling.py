"""Provider growth measurements count timed observations, not unrelated fixtures."""

import json
from pathlib import Path

import pytest

from benchmarks import analytics_workloads, paired, scaling

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / 'benchmarks/cases.json').read_text())
BASE = MANIFEST['profiles']['test']


@pytest.mark.parametrize('operation', ['history-read-hit', 'history-read-miss',
                                       'history-metrics-hit', 'history-metrics-miss'])
def test_history_scaling_processes_fourfold_actual_history_observations(tmp_path, operation):
    case = 'P09.' + operation
    large_dimensions = scaling.dimensions(case, BASE)
    assert large_dimensions.get('provider_history_observations') == 20
    assert large_dimensions['funds'] == BASE['funds']
    assert large_dimensions['constituents_per_fund'] == BASE['constituents_per_fund']
    fixtures = [analytics_workloads.prepare(case, tmp_path / name, dimensions)
                for name, dimensions in [('small', BASE), ('large', large_dimensions)]]
    try:
        results = [fixture.operation() for fixture in fixtures]
        for fixture, result in zip(fixtures, results):
            assert all(row['passed'] for row in fixture.verify(result).values())
        histories = [result.get('history', result)['prices'] for result in results]
        assert [len(history) for history in histories] == [5, 20]
        assert fixtures[0].counts['processed_history_observations'] == 5
        assert fixtures[1].counts['processed_history_observations'] == 20
        for fixture, result in zip(fixtures, results):
            report = {'cases': {case: {'samples': [{'counts': fixture.counts}]}}}
            assert scaling.project(report, case)['cases'][case]['samples'][0]['counts'] == {
                'logical_records': len(result.get('history', result)['prices'])}
    finally:
        for fixture in fixtures:
            fixture.close()


@pytest.mark.parametrize('temperature', ['hit', 'miss'])
def test_single_quote_is_a_truthfully_bounded_control(tmp_path, temperature):
    case = 'P09.quote-' + temperature
    assert scaling.dimensions(case, BASE) == BASE
    fixture = analytics_workloads.prepare(case, tmp_path / temperature, BASE)
    try:
        result = fixture.operation()
        assert result['price'] == '100'
        assert all(row['passed'] for row in fixture.verify(result).values())
        assert fixture.counts['processed_quote_observations'] == 1
    finally:
        fixture.close()


def test_quote_bounded_controls_remain_in_complete_scaling_plan():
    quote_ids = {'P09.quote-hit', 'P09.quote-miss'}
    assert quote_ids <= {case['id'] for case in MANIFEST['cases']}
    plan = paired.scaling_plan(MANIFEST)
    controls = [row for row in plan if row['case']['id'] in quote_ids]
    assert len(controls) == 2
    assert all(row.get('bounded_control') is True for row in controls)
    assert all(isinstance(row.get('reason'), str) and 'quote' in row['reason'].lower() for row in controls)
    assert all(row['small'] == row['large'] for row in controls)
    assert {row['case']['id'] for row in plan} == {case['id'] for case in MANIFEST['cases']}
