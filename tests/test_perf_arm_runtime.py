"""Native Apple-Silicon performance evidence must never claim an x86 runtime."""
import importlib
from pathlib import Path

import pytest

from benchmarks.runner import validate_runtime

ROOT = Path(__file__).resolve().parents[1]


def facts(machine='aarch64', **changes):
    return {'docker': True, 'network': 'none', 'cpus': 2,
            'memory_bytes': 4 * 1024 ** 3, 'machine': machine, **changes}


@pytest.mark.parametrize('machine', ['aarch64', 'arm64'])
def test_native_arm_runtime_is_accepted_without_emulation(machine):
    result = validate_runtime(facts(machine))
    assert result['status'] == 'PASS'
    assert result['issues'] == []


@pytest.mark.parametrize('changes', [
    {'machine': 'x86_64'}, {'machine': 'amd64'}, {'emulated': True},
    {'engine_machine': 'x86_64'}, {'docker': False}, {'network': 'connected'},
    {'cpus': 4}, {'memory_bytes': 8 * 1024 ** 3},
])
def test_other_architectures_emulation_and_wrong_constraints_reject(changes):
    result = validate_runtime(facts(**changes))
    assert result['status'] == 'FAIL'
    assert result['issues']


@pytest.mark.parametrize('machine', ['aarch64', 'arm64'])
def test_paired_runtime_uses_actual_engine_architecture(machine):
    paired = importlib.import_module('benchmarks.paired')
    evidence = paired.runtime_for_engine({'Architecture': machine, 'Name': 'fictional-native-M4'})
    assert evidence['machine'] == machine
    assert evidence['hardware'] == 'fictional-native-M4'
    assert evidence['cpus'] == 2 and evidence['memory_bytes'] == 4 * 1024 ** 3
    assert evidence['network'] == 'none' and evidence['docker'] is True
    assert validate_runtime(evidence)['status'] == 'PASS'


@pytest.mark.parametrize('machine', ['x86_64', 'amd64', 'unknown'])
def test_paired_runtime_cannot_relabel_another_engine_as_arm(machine):
    paired = importlib.import_module('benchmarks.paired')
    with pytest.raises(ValueError):
        paired.runtime_for_engine({'Architecture': machine, 'Name': 'fictional-other-engine'})


def test_checked_in_performance_workflow_does_not_request_x86_emulation():
    workflow = (ROOT / '.github/workflows/performance.yml').read_text()
    assert '--platform linux/amd64' not in workflow
    assert 'linux/arm64' in workflow or 'ubuntu-24.04-arm' in workflow
