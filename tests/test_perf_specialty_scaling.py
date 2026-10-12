"""Matched research scaling grows native evidence, not unrelated ledger rows."""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from benchmarks.analytics_workloads import prepare

ROOT = Path(__file__).resolve().parents[1]
DIMENSIONS = json.loads((ROOT / 'benchmarks/cases.json').read_text())['profiles']['test']
PRIMARY_EVIDENCE = {
    'news': 'events', 'earnings': 'metrics', 'political': 'contributions',
    'competitive': 'metrics', 'insiders': 'transactions', 'fund-diligence': 'holdings',
}


@pytest.mark.parametrize('specialty', PRIMARY_EVIDENCE)
@pytest.mark.parametrize('operation', ['validate', 'import', 'show', 'summary'])
def test_native_specialty_evidence_scales_fourfold_with_valid_real_operations(
        tmp_path, specialty, operation):
    measured = []
    for scale in (1, 4):
        root = tmp_path / str(scale)
        prepared = prepare(f'P13.{specialty}-{operation}', root,
                           dict(DIMENSIONS, research_evidence_scale=scale))
        try:
            stage = json.loads((root / 'analytical-preparation.json').read_text())['stage']
            payload = stage['payload']
            evidence_count = len(payload[PRIMARY_EVIDENCE[specialty]])
            assert prepared.counts.get('research_evidence_items') == evidence_count
            assert evidence_count > 0
            if specialty == 'fund-diligence':
                assert payload['holdings_snapshot']['holdings_count_reported'] == evidence_count
                assert evidence_count <= 100
                weights = [Decimal(row['weight_pct']) for row in payload['holdings']]
                assert weights == sorted(weights, reverse=True)
                assert sum(weights) <= 100
            if specialty == 'competitive':
                assert 1 <= len(payload['peers']) <= 8
            result = prepared.operation()
            proofs = prepared.verify(result)
            assert all(proof['passed'] and proof['expected'] == proof['observed']
                       for proof in proofs.values()), proofs
            measured.append(evidence_count)
        finally:
            prepared.close()
    assert measured[1] == 4 * measured[0], 'Timed native package evidence must grow fourfold'


@pytest.mark.parametrize(('case_id', 'specialty'), [
    ('P13.competitive-matrix', 'competitive'),
    ('P13.insiders-activity', 'insiders'),
    ('P13.fund-diligence-holdings', 'fund-diligence'),
])
def test_specialty_detail_queries_use_scaled_native_evidence(tmp_path, case_id, specialty):
    observed = []
    for scale in (1, 4):
        root = tmp_path / str(scale)
        prepared = prepare(case_id, root, dict(DIMENSIONS, research_evidence_scale=scale))
        try:
            stage = json.loads((root / 'analytical-preparation.json').read_text())['stage']
            count = len(stage['payload'][PRIMARY_EVIDENCE[specialty]])
            assert prepared.counts.get('research_evidence_items') == count
            result = prepared.operation()
            assert all(proof['passed'] for proof in prepared.verify(result).values())
            observed.append(count)
        finally:
            prepared.close()
    assert observed[1] == observed[0] * 4
