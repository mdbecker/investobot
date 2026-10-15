"""Eight paired medians; invalid evidence fails separately from a slowdown."""
from fractions import Fraction
from statistics import median

FLOOR_NS = 200_000_000
MAX_SLOWDOWN_RATIO = Fraction(3, 2)


def _validate(reference, candidate):
    if reference.get('recipe_hash') != candidate.get('recipe_hash'):
        raise ValueError('Recipe identity differs')
    if reference.get('runner') != candidate.get('runner'):
        raise ValueError('Runner identity differs')
    left, right = reference.get('cases', {}), candidate.get('cases', {})
    if len(left) != 8 or set(left) != set(right):
        raise ValueError('Exactly eight matching workflows are required')
    medians = {}
    for name in left:
        a, b = left[name], right[name]
        for key in ('input_hash', 'output_hash', 'counts'):
            if not a.get(key) or a[key] != b.get(key):
                raise ValueError(f'{name}: mismatched {key}')
        values = []
        for case in (a, b):
            batch = case.get('batch')
            samples = case.get('samples_ns', [])
            if isinstance(batch, bool) or not isinstance(batch, int) or batch <= 0 or len(samples) != 5:
                raise ValueError(f'{name}: five samples and positive batch required')
            if any(isinstance(x, bool) or not isinstance(x, (int, float)) or x < FLOOR_NS for x in samples):
                raise ValueError(f'{name}: invalid sample below 200 ms')
            values.append(median(Fraction(str(x)) / batch for x in samples))
        medians[name] = {'reference_median_ns': float(values[0]),
                         'candidate_median_ns': float(values[1]),
                         'ratio': float(values[1] / values[0]),
                         'slow': values[1] > values[0] * MAX_SLOWDOWN_RATIO}
    return medians


def compare_pair(reference, candidate, *, confirmation=None):
    """One complete confirmation is required before rejecting a >50% slowdown."""
    try:
        measurements = _validate(reference, candidate)
        slow = {name for name, row in measurements.items() if row['slow']}
        if not slow:
            return {'status': 'PASS', 'measurements': measurements, 'regressions': []}
        if confirmation is None:
            return {'status': 'CONFIRM', 'measurements': measurements, 'regressions': sorted(slow)}
        if len(confirmation) != 2:
            raise ValueError('Complete reference and candidate confirmation required')
        for first, repeated in zip((reference, candidate), confirmation, strict=True):
            if first.get('recipe_hash') != repeated.get('recipe_hash') or first.get('runner') != repeated.get('runner'):
                raise ValueError('Confirmation identity differs')
            for name, case in first['cases'].items():
                repeated_case = repeated.get('cases', {}).get(name, {})
                if any(case.get(key) != repeated_case.get(key) for key in ('input_hash', 'output_hash', 'counts')):
                    raise ValueError('Confirmation workflow evidence differs')
        verified = _validate(*confirmation)
        confirmed = sorted(name for name in slow if verified[name]['slow'])
        return {'status': 'FAIL' if confirmed else 'PASS', 'measurements': measurements,
                'confirmation': verified, 'regressions': confirmed}
    except (ValueError, KeyError, TypeError, ZeroDivisionError, OverflowError) as error:
        return {'status': 'INVALID', 'error': str(error), 'regressions': []}
