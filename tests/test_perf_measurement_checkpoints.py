"""Retained measurement evidence survives later orchestration or publication failures."""
import json

import pytest

from benchmarks import paired


def evidence():
    return {'status': 'IN_PROGRESS', 'reports': {'candidate': {
        'commit': 'fictional-source', 'cases': {'P01.cli-startup': {
            'status': 'PASS', 'samples': [{'elapsed_ns': 234567890, 'exit_code': 0}]}}}},
        'comparisons': [{'status': 'PASS', 'case_id': 'P01.cli-startup'}],
        'timed_operation_seconds': 0.23456789,
        'fixture_preparation_and_reset_seconds': 1.25,
        'reference_review_status': 'PENDING_HUMAN_REVIEW'}


def test_checkpoint_publishes_actual_partial_evidence_without_inventing_approval(tmp_path):
    output = tmp_path / 'measurements.json'
    original = evidence()
    paired.checkpoint(output, original)
    saved = json.loads(output.read_text())
    assert saved == original
    assert saved['reference_review_status'] == 'PENDING_HUMAN_REVIEW'
    assert not list(tmp_path.glob('*.tmp'))


def test_checkpoint_serialization_failure_preserves_previous_report_bytes(tmp_path):
    output = tmp_path / 'measurements.json'
    original = evidence()
    paired.checkpoint(output, original)
    previous = output.read_bytes()
    invalid = {**original, 'unserializable': object()}
    with pytest.raises((TypeError, ValueError)):
        paired.checkpoint(output, invalid)
    assert output.read_bytes() == previous
    assert sorted(path.name for path in tmp_path.iterdir()) == ['measurements.json']


def test_failure_checkpoint_retains_original_completed_measurements_and_error(tmp_path):
    output = tmp_path / 'measurements.json'
    original = evidence()
    paired.checkpoint(output, original)
    failed = {**original, 'status': 'FAIL', 'failure': {
        'kind': 'OPERATION_FAILED', 'message': 'Original observation rejected output',
        'cleanup_error': 'Owned volume cleanup also failed'}}
    paired.checkpoint(output, failed)
    retained = json.loads(output.read_text())
    assert retained['reports'] == original['reports']
    assert retained['comparisons'] == original['comparisons']
    assert retained['timed_operation_seconds'] == original['timed_operation_seconds']
    assert retained['failure'] == failed['failure']
    assert retained['status'] == 'FAIL'
