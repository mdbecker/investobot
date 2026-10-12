"""Independent output cardinality proofs must reject corrupted native results."""

import copy
import json
from pathlib import Path

import pytest

from benchmarks import analytics_workloads, paired, scaling

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / 'benchmarks/cases.json').read_text())
DIMENSIONS = MANIFEST['profiles']['test']
FIELDS = {
    'news': ('event_count', 'events'),
    'earnings': ('metric_count', 'metrics'),
    'political': ('verified_transactions', 'contributions'),
    'competitive': ('metric_count', 'metrics'),
    'insiders': ('transaction_count', 'transactions'),
    'fund-diligence': ('holding_count', 'holdings'),
}


@pytest.mark.parametrize('specialty', FIELDS)
@pytest.mark.parametrize('verb', ['validate', 'import', 'show'])
def test_specialty_coverage_uses_actual_native_output(tmp_path, specialty, verb):
    dimensions = dict(DIMENSIONS, research_evidence_scale=4)
    prepared = analytics_workloads.prepare(f'P13.{specialty}-{verb}', tmp_path, dimensions)
    try:
        native = prepared.operation()
        assert all(row['passed'] for row in prepared.verify(native).values())
        counter, rows = FIELDS[specialty]
        damaged = copy.deepcopy(native)
        if verb == 'show':
            assert len(native[rows]) >= 4
            damaged[rows].pop()
        else:
            assert native[counter] >= 4
            damaged[counter] += 1
        proof = prepared.verify(damaged)
        assert proof['complete-requested-research-coverage']['passed'] is False, (
            'Coverage must measure returned native evidence, not merely stored run totals')
    finally:
        prepared.close()


def test_fund_summary_scaling_is_explicitly_bounded_by_its_consumed_evidence():
    case_id = 'P13.fund-diligence-summary'
    assert scaling.dimensions(case_id, DIMENSIONS) == DIMENSIONS
    plan = paired.scaling_plan(MANIFEST)
    controls = [row for row in plan if row['case']['id'] == case_id]
    assert len(controls) == 1
    assert controls[0].get('bounded_control') is True
    assert isinstance(controls[0].get('reason'), str) and controls[0]['reason']
    assert controls[0]['small'] == controls[0]['large']
