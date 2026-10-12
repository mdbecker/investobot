"""Paired calibration leaves measured headroom above the 200ms sample floor."""
from copy import deepcopy

import pytest

from benchmarks import paired, runner


def measurement_batch(warmups):
    assert hasattr(paired, 'measurement_batch'), 'Paired calibration lacks measured batch headroom'
    return paired.measurement_batch(warmups)


def test_paired_calibration_targets_400ms_using_fastest_revision():
    warmups = {'reference': {'P02.check': 24_000_000},
               'base': {'P02.check': 23_000_000},
               'candidate': {'P02.check': 22_500_000}}
    original = deepcopy(warmups)
    assert measurement_batch(warmups) == {'P02.check': 18}
    assert warmups == original


def test_paired_calibration_keeps_slow_operations_at_one_repetition():
    warmups = {'reference': {'import': 1_700_000_000},
               'base': {'import': 1_800_000_000},
               'candidate': {'import': 1_600_000_000}}
    assert measurement_batch(warmups) == {'import': 1}


def test_paired_calibration_handles_exact_headroom_boundary_per_case():
    warmups = {'reference': {'read': 100_000_000, 'bulk': 400_000_000},
               'base': {'read': 120_000_000, 'bulk': 450_000_000},
               'candidate': {'read': 110_000_000, 'bulk': 500_000_000}}
    assert measurement_batch(warmups) == {'bulk': 1, 'read': 4}


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
