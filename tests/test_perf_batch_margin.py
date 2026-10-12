"""Paired calibration leaves measured headroom above the 200ms sample floor."""
from copy import deepcopy
from fractions import Fraction

import pytest

from benchmarks import paired, runner


def measurement_batch(warmups):
    assert hasattr(paired, 'measurement_batch'), 'Paired calibration lacks measured batch headroom'
    return paired.measurement_batch(warmups)


def test_paired_calibration_targets_300ms_using_fastest_revision():
    warmups = {'reference': {'P02.check': 24_000_000},
               'base': {'P02.check': 23_000_000},
               'candidate': {'P02.check': 22_500_000}}
    original = deepcopy(warmups)
    assert measurement_batch(warmups) == {'P02.check': 14}
    assert warmups == original


def test_paired_calibration_keeps_slow_operations_at_one_repetition():
    warmups = {'reference': {'import': 1_700_000_000},
               'base': {'import': 1_800_000_000},
               'candidate': {'import': 1_600_000_000}}
    assert measurement_batch(warmups) == {'import': 1}


def test_paired_calibration_handles_exact_headroom_boundary_per_case():
    warmups = {'reference': {'read': 100_000_000, 'bulk': 300_000_000},
               'base': {'read': 120_000_000, 'bulk': 450_000_000},
               'candidate': {'read': 110_000_000, 'bulk': 500_000_000}}
    assert measurement_batch(warmups) == {'bulk': 1, 'read': 3}


def test_extended_interactive_calibration_preserves_six_hundred_second_reserve():
    """Complete interactive coverage leaves room for bulk operations and warmups."""
    definitions = runner.manifest()
    interactive = sum(case['repetitions']['extended'] == 21 for case in definitions['cases'])
    assert interactive == 94
    warmup_ns = 10_000_000
    warmups = {revision: {'read': warmup_ns}
               for revision in ('reference', 'base', 'candidate')}
    target_ns = warmup_ns * measurement_batch(warmups)['read']
    # Three paired revisions plus both matched candidate scaling sizes.
    interactive_ns = interactive * 21 * 5 * target_ns
    assert interactive_ns <= (3600 - 600) * 1_000_000_000


def test_recorded_short_sample_gains_headroom_without_changing_normalized_time():
    """Retain the failed nine-call evidence; extrapolation is not a new measurement."""
    recorded_ns = 174_663_833
    recorded_count = 9
    warmups = {'reference': {'P02.check': 24_000_000},
               'base': {'P02.check': 23_000_000},
               'candidate': {'P02.check': 22_500_000}}
    count = measurement_batch(warmups)['P02.check']
    per_operation = Fraction(recorded_ns, recorded_count)
    projected_ns = per_operation * count
    assert count == 14
    assert recorded_ns < 200_000_000
    assert projected_ns > 200_000_000
    assert projected_ns / count == per_operation


def test_paired_calibration_rejects_mismatched_workload_inventories():
    warmups = {'reference': {'read': 100_000_000},
               'base': {'other': 100_000_000},
               'candidate': {'read': 100_000_000}}
    assert hasattr(paired, 'measurement_batch'), 'Paired calibration lacks measured batch headroom'
    with pytest.raises(ValueError, match='inventories differ'):
        paired.measurement_batch(warmups)


def test_public_runner_calibration_retains_200ms_default():
    warmups = {'reference': {'read': 24_000_000},
               'base': {'read': 23_000_000},
               'candidate': {'read': 22_500_000}}
    assert runner.common_batch_counts(warmups) == {'read': 9}
