"""Offline diagnostics reject emulation and unsafe Docker constraints."""
import pytest

from benchmarks.runner import validate_runtime


def facts(machine='aarch64', **changes):
    return {'docker': True, 'network': 'none', 'cpus': 2,
            'memory_bytes': 4 * 1024 ** 3, 'machine': machine, **changes}


@pytest.mark.parametrize('machine', ['aarch64', 'arm64'])
def test_native_arm_runtime_is_accepted(machine):
    assert validate_runtime(facts(machine))['status'] == 'PASS'


@pytest.mark.parametrize('changes', [
    {'machine': 'x86_64'}, {'emulated': True}, {'engine_machine': 'x86_64'},
    {'docker': False}, {'network': 'connected'}, {'cpus': 4}, {'memory_bytes': 8 * 1024 ** 3},
])
def test_unsafe_runtime_is_rejected(changes):
    assert validate_runtime(facts(**changes))['status'] == 'FAIL'
