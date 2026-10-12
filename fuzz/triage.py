"""Local evidence triage; no generated code, production edits or publication."""

import copy
import hashlib
import json
from fractions import Fraction

from benchmarks import gates


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _report(sample, retry=None):
    def case(value):
        observations = value.get('observations', [])
        rows = []
        for observation in observations:
            if isinstance(observation, dict):
                row = dict(observation)
            else:
                row = {'elapsed_ns': observation * 1_000_000, 'batch_repetitions': 1}
            for metric in ('peak_rss_bytes', 'persisted_bytes', 'temp_bytes'):
                row.setdefault(metric, value[metric])
            row.update(output_hash=value['output_hash'], counts={'input_hash': value['input_hash']},
                       exit_code=0, invariant_results={'valid_output': {'passed': value['valid_output']}})
            rows.append(row)
        return {'status': 'PASS', 'samples': rows}
    measured = case(sample)
    if retry is not None:
        measured['retry'] = case(retry)
    return {'commit': sample['source_commit'], 'fixture': {'input_hash': sample['input_hash']},
            'runner': sample['limits'], 'cases': {'fixed-fuzz-input': measured}}


def compare(reference, candidate, *, retry_reference=None, retry_candidate=None):
    """Reuse paired benchmark gates only for exact inputs and equivalent limits."""
    samples = [reference, candidate] + [value for value in (retry_reference, retry_candidate) if value is not None]
    for field, reason in [('input_hash', 'INCOMPARABLE_INPUTS'), ('limits', 'INCOMPARABLE_LIMITS')]:
        if any(value.get(field) != reference.get(field) for value in samples):
            return {'classification': 'UNCONFIRMED', 'reason': reason, 'status': 'FAILED',
                    'clean_reproductions': 0}
    if any(value.get('valid_output') is not True or value.get('output_hash') != reference.get('output_hash')
           for value in samples):
        return {'classification': 'UNCONFIRMED', 'reason': 'INVALID_OUTPUT', 'status': 'FAILED',
                'clean_reproductions': 0}
    try:
        base = _report(reference, retry_reference)
        proposed = _report(candidate, retry_candidate)
        manifest = {'required_cases': ['fixed-fuzz-input'], 'mode': 'pr',
            'reference_hash': 'fixed-fuzz-input', 'expected_reference_hash': 'fixed-fuzz-input',
            'reference_commit': reference['source_commit'], 'fixture': base['fixture'], 'runner': base['runner']}
        measured = gates.compare(proposed, base, base, manifest)
        ratio = next((row['ratio'] for row in measured['comparisons'] if row['metric'] == 'elapsed_ns'), None)
        regression = any(row['code'] == 'PERFORMANCE_REGRESSION' for row in measured['issues'])
        confirmed = regression and bool(measured['retries']) and not measured['retry_required']
        classification = ('CONFIRMED_SLOW_PATH' if confirmed else 'NOISY_FIRST_MEASUREMENT'
                          if measured['status'] == 'NOISY_FIRST_MEASUREMENT' else
                          'UNCONFIRMED' if measured['issues'] else 'PASS')
        return {'classification': classification, 'status': measured['status'], 'elapsed_ratio': ratio,
                'clean_reproductions': 2 if confirmed else 0, 'gate_evidence': measured}
    except (KeyError, ValueError, TypeError, ZeroDivisionError, OverflowError) as error:
        return {'classification': 'UNCONFIRMED', 'status': 'FAILED', 'reason': 'INVALID_MEASUREMENTS',
                'issues': [{'code': 'INVALID_MEASUREMENTS', 'detail': str(error)}], 'clean_reproductions': 0}


def deduplicate(findings):
    """A signature/shape identifies a defect; different seeds are supporting cases."""
    grouped = {}
    for original in findings:
        finding = copy.deepcopy(original)
        if finding.get('classification', '').startswith('CONFIRMED_') and finding.get('clean_reproductions', 0) < 2:
            finding['classification'] = 'UNCONFIRMED'
        key = (finding.get('failure_signature') or finding.get('input_hash'), finding.get('shape_hash'))
        if key not in grouped:
            grouped[key] = {**finding, 'case_ids': [], 'input_hashes': []}
        target = grouped[key]
        for field, output in [('case_id', 'case_ids'), ('input_hash', 'input_hashes')]:
            value = finding.get(field)
            if value is not None and value not in target[output]:
                target[output].append(value)
        target['clean_reproductions'] = max(target.get('clean_reproductions', 0), finding.get('clean_reproductions', 0))
        if finding.get('classification', '').startswith('CONFIRMED_'):
            target['classification'] = finding['classification']
    return list(grouped.values())


def _dependencies(operations):
    available = set()
    for operation in operations:
        name = operation['name']
        if name in {'apply', 'reconcile'} and 'import' not in available:
            return False
        available.add(name)
    return True


def minimize(case, replay=None):
    """Bounded deletion shrink with two fresh reproductions of each accepted shrink."""
    if replay is None:
        from fuzz.runner import execute_case
        replay = execute_case
    current = copy.deepcopy(case)
    attempts = 0

    def reproduce(candidate):
        nonlocal attempts
        attempts += 2
        results = [replay(copy.deepcopy(candidate)), replay(copy.deepcopy(candidate))]
        return results

    results = reproduce(current)
    classification = results[0].get('classification')
    signature = results[0].get('failure_signature')
    if not signature or classification not in {'CONFIRMED_BUG', 'CONFIRMED_SLOW_PATH', 'EXPECTED_REJECTION'} or any(
            result.get('classification') != classification or result.get('failure_signature') != signature for result in results):
        return {'case': current, 'classification': 'UNCONFIRMED', 'failure_signature': signature,
                'clean_reproductions': 0, 'attempts': attempts, 'reproductions': results, 'input_hash': _hash(current)}
    index = 0
    while index < len(current['operations']) and len(current['operations']) > 1 and attempts < 50:
        candidate = copy.deepcopy(current)
        del candidate['operations'][index]
        if not _dependencies(candidate['operations']):
            index += 1
            continue
        trial = reproduce(candidate)
        if all(result.get('classification') == classification and result.get('failure_signature') == signature for result in trial):
            current, results, index = candidate, trial, 0
        else:
            index += 1
    return {'case': current, 'classification': classification, 'failure_signature': signature,
            'clean_reproductions': 2, 'attempts': attempts, 'input_hash': results[0].get('input_hash', _hash(current)),
            'reproductions': results, 'minimization': 'bounded dependency-aware operation deletion'}


def promotion(finding, inventory, *, red_evidence=None, green_evidence=None):
    """Draft a deterministic case for human review; never change the inventory."""
    issues = []
    for evidence, code, observed in [(red_evidence, 'OBSERVED_RED_REQUIRED', 'FAILED'),
                                     (green_evidence, 'OBSERVED_GREEN_REQUIRED', 'PASSED')]:
        if not evidence or evidence.get('observed') != observed or not evidence.get('commit') or not evidence.get('test'):
            issues.append({'code': code})
    if finding.get('classification') not in {'CONFIRMED_BUG', 'CONFIRMED_SLOW_PATH'} or finding.get('clean_reproductions', 0) < 2:
        issues.append({'code': 'TWO_CLEAN_REPRODUCTIONS_REQUIRED'})
    if not finding.get('case') or not finding.get('input_hash'):
        issues.append({'code': 'FIXED_INPUT_REQUIRED'})
    if red_evidence and green_evidence and red_evidence.get('test') != green_evidence.get('test'):
        issues.append({'code': 'REGRESSION_TEST_MISMATCH'})
    duplicate = any(row.get('input_hash') == finding.get('input_hash') for row in inventory.get('cases', []))
    return {'status': 'BLOCKED' if issues else 'READY_FOR_REVIEW', 'issues': issues,
        'production_modified': False, 'ci_campaign': False, 'existing_case': duplicate,
        'benchmark_case': {'input_hash': finding.get('input_hash'), 'fixed_input': copy.deepcopy(finding.get('case')),
                           'invariants': (finding.get('case') or {}).get('invariants', [])},
        'red_evidence': red_evidence, 'green_evidence': green_evidence}


def assess_growth(small, large, *, linear=True):
    """A matched fourfold scaling observation is a suspect, never a confirmed bug."""
    try:
        if large['records'] != 4 * small['records'] or small['records'] < 1:
            raise ValueError('Requires matched 1x/4x logical records')
        for field in ('input_shape_hash', 'source_commit', 'limits'):
            if small.get(field) != large.get(field):
                raise ValueError('Scaling provenance differs')
        elapsed = Fraction(str(small['elapsed_ns']))
        larger = Fraction(str(large['elapsed_ns']))
        if elapsed <= 0 or larger < 0:
            raise ValueError('Invalid elapsed time')
        ratio = larger / elapsed
        if not linear:
            return {'status': 'UNCONFIRMED', 'reason': 'NONLINEAR_BOUND_REQUIRED', 'confirmed': False}
        def report(value):
            return {'commit': value.get('source_commit'), 'runner': value.get('limits', {}),
                'cases': {'scaling': {'status': 'PASS', 'samples': [{'elapsed_ns': value['elapsed_ns'],
                    'exit_code': 0, 'counts': {'records': value['records']}}]}}}
        evidence = gates.compare_scaling([{'case_id': 'scaling', 'small': report(small),
            'large': report(large), 'expected_complexity': 'linear'}])
        return {'status': 'SUSPECTED_SLOW_PATH' if evidence['issues'] else 'PASS',
                'ratio': float(ratio), 'clean_reproductions': 0, 'confirmed': False, 'gate_evidence': evidence}
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return {'status': 'UNCONFIRMED', 'reason': 'INVALID_SCALING_MEASUREMENTS', 'confirmed': False}
