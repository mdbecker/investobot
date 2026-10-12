"""Bounded local replay minimization; findings need human review."""
import copy

from fuzz.scenario import digest as _hash


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
    if not signature or classification not in {'UNCONFIRMED', 'EXPECTED_REJECTION'} or any(
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


