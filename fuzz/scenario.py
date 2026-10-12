"""Strict non-executable synthetic scenario contracts and stable replay identities."""
import hashlib
import json
import re
from datetime import date

INVARIANTS = frozenset({'financial_conservation', 'position_lot_consistency', 'basis_conservation',
    'immutable_provenance', 'idempotent_replay', 'same_state_recomputation', 'row_order_equivalence',
    'supported_error_codes', 'atomic_rejection', 'no_look_ahead', 'no_invalid_trading',
    'vector_permission_filter', 'research_continuity', 'missing_data_propagation',
    'recovery_equivalence', 'immutable_reads'})
MUTATIONS = frozenset({'reverse_independent_rows', 'missing_flow_boundary', 'inconsistent_position_value',
    'missing_cash_coverage', 'denied_source', 'invalid_activity'})
PARAMS = {'import': {'template': {'coherent', 'inconsistent_value'}}, 'reconcile': {}, 'apply': {},
    'query': {'kind': {'summary', 'performance', 'exposure'}},
    'activity': {'type': {'DEPOSIT'}, 'amount': 'decimal', 'date': 'date'},
    'tax': {'kind': {'lots'}}, 'plan': {'mode': {'contributions-only'}},
    'vector': {'kind': {'search'}, 'query': 'text'}, 'backup': {'kind': {'roundtrip'}}}
CASE_FIELDS = {'id', 'family', 'seed', 'fixture_profile', 'records', 'operations', 'mutations',
               'invariants', 'expected_result', 'performance_dimension', 'rationale'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def limits(large=False):
    return {'max_operations': 12, 'max_records': 100000 if large else 25000,
            'max_input_bytes': 20 * 1024 * 1024, 'case_cpu_seconds': 20 if large else 30,
            'case_memory_bytes': 512 * 1024 * 1024, 'case_disk_bytes': 128 * 1024 * 1024,
            'case_wall_seconds': 30 if large else 60, 'large_opt_in': bool(large), 'bounded': True}


def _identifier(value):
    return isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}', value)


def _integer(value, lower, upper):
    return isinstance(value, int) and not isinstance(value, bool) and lower <= value <= upper


def _case(case, large=False):
    if not isinstance(case, dict) or set(case) != CASE_FIELDS:
        raise ValueError('Unknown or missing scenario fields')
    if not _identifier(case['id']) or case['family'] not in {f'P{i:02}' for i in range(1, 16)}:
        raise ValueError('Invalid case identity/family')
    if not _integer(case['seed'], 0, 2**63 - 1) or not _integer(case['records'], 1, limits(large)['max_records']):
        raise ValueError('Unbounded seed/record count')
    if case['fixture_profile'] != 'tiny':
        raise ValueError('Unsupported synthetic prerequisites')
    if case['expected_result'] not in {'SUCCESS', 'BLOCKED', 'INPUT_ERROR'}:
        raise ValueError('Expected result must be an allowlisted result class')
    if case['performance_dimension'] not in {None, 'latency', 'scaling'}:
        raise ValueError('Unsupported performance dimension')
    if not isinstance(case['rationale'], str) or len(case['rationale']) > 4096:
        raise ValueError('Invalid non-executable rationale')
    for field, registry in [('mutations', MUTATIONS), ('invariants', INVARIANTS)]:
        values = case[field]
        if not isinstance(values, list) or len(values) > 20 or any(not isinstance(v, str) or v not in registry for v in values):
            raise ValueError('Unknown perturbation or independent invariant')
    if not case['invariants']:
        raise ValueError('Independent invariant required')
    operations = case['operations']
    if not isinstance(operations, list) or not 1 <= len(operations) <= 12:
        raise ValueError('Operation bound exceeded')
    for operation in operations:
        if not isinstance(operation, dict) or set(operation) != {'name', 'params'}:
            raise ValueError('Unknown operation fields')
        name = operation['name']
        if not isinstance(name, str) or name not in PARAMS:
            raise ValueError('Unsupported operation')
        values = operation['params']
        if not isinstance(values, dict) or set(values) != set(PARAMS[name]):
            raise ValueError('Unknown or missing typed parameters')
        for key, kind in PARAMS[name].items():
            value = values[key]
            if isinstance(kind, set):
                if not isinstance(value, str) or value not in kind:
                    raise ValueError('Unsupported parameter value')
            elif kind == 'decimal':
                if not isinstance(value, str) or len(value) > 256 or not re.fullmatch(r'-?\d+(\.\d+)?', value):
                    raise ValueError('Invalid exact decimal')
            elif kind == 'date':
                if not isinstance(value, str) or len(value) != 10:
                    raise ValueError('Invalid fixed date')
                date.fromisoformat(value)
            elif kind == 'text':
                if not isinstance(value, str) or len(value) > 256 or not re.fullmatch(r'[A-Za-z0-9 _-]+', value):
                    raise ValueError('Unsafe query text')
    executable = {key: value for key, value in case.items() if key not in {'id', 'rationale'}}
    shape = {'family': case['family'], 'operations': [row['name'] for row in operations],
             'transitions': [{key: value for key, value in row['params'].items()
                              if key in {'kind', 'type', 'mode', 'template'}} for row in operations],
             'mutations': case['mutations']}
    return {'id': case['id'], 'family': case['family'], 'input_hash': digest(executable),
            'shape_hash': digest(shape)}


def validate_case(case, large=False):
    try:
        if len(json.dumps(case, allow_nan=False).encode()) > limits(large)['max_input_bytes']:
            raise ValueError('Input size exceeded')
        identity = _case(case, large)
        return {'status': 'VALID', 'case_hashes': [identity], 'limits': limits(large)}
    except (ValueError, TypeError, KeyError, OverflowError) as error:
        return {'status': 'INVALID', 'issues': [{'code': 'INVALID_SCENARIO', 'message': str(error)}],
                'limits': limits(large)}


def validate(payload, large=False):
    try:
        if len(json.dumps(payload, allow_nan=False).encode()) > limits(large)['max_input_bytes']:
            raise ValueError('Input size exceeded')
        if not isinstance(payload, dict) or set(payload) != {'schema_version', 'campaign_id', 'cases'}:
            raise ValueError('Unknown campaign fields')
        if type(payload['schema_version']) is not int or payload['schema_version'] != 1 or not _identifier(payload['campaign_id']):
            raise ValueError('Invalid campaign version/identity')
        cases = payload['cases']
        if not isinstance(cases, list) or not 1 <= len(cases) <= 100:
            raise ValueError('Explicit run requires 1 to 100 bounded cases')
        identities = [_case(case, large) for case in cases]
        if len({row['id'] for row in identities}) != len(cases) or len({row['input_hash'] for row in identities}) != len(cases):
            raise ValueError('Duplicate case or executable input')
        return {'status': 'VALID', 'case_hashes': identities, 'limits': limits(large)}
    except (ValueError, TypeError, KeyError, OverflowError) as error:
        return {'status': 'INVALID', 'issues': [{'code': 'INVALID_CAMPAIGN', 'message': str(error)}],
                'limits': limits(large)}
