"""Matched fourfold fixture slices and derived scaling views of actual measurements."""
from copy import deepcopy


def _driver(case_id):
    family, operation = case_id.split('.', 1)
    if family == 'P04':
        return 'backup_fixture_bytes' if operation in {'backup', 'verify', 'restore-staging'} else 'positions'
    if family == 'P05':
        return 'positions' if operation == 'hypothetical-risk' else 'history_checkpoints'
    if family == 'P09':
        if operation.startswith(('holdings-', 'compare-', 'history-metrics-')):
            return 'constituents_per_fund'
        return 'funds'
    if family == 'P10':
        return 'constituent_observations'
    if family == 'P11':
        return 'parquet_observations'
    if family == 'P12':
        return 'history_rows'
    if family == 'P13':
        # Legal specialty packages are bounded controls; scale the real ledger
        # context, without claiming their fixed evidence cardinality increases.
        return 'positions'
    if family == 'P14':
        return 'research_chunks'
    if family == 'P06':
        return 'lots'
    if family == 'P08':
        return 'saved_plans'
    return 'positions'


def dimensions(case_id, base_dimensions):
    """Scale only the logical driver; retain financial rules and fixed time span."""
    result = deepcopy(base_dimensions)
    family = case_id.split('.', 1)[0]
    if family in {'P02', 'P03', 'P06', 'P07', 'P15', 'P01'}:
        fields = ('accounts', 'positions', 'lots', 'accepted_snapshots')
    elif family == 'P04':
        fields = ('backup_fixture_bytes',) if _driver(case_id) == 'backup_fixture_bytes' else (
            'accounts', 'positions', 'lots', 'accepted_snapshots')
    elif family == 'P05':
        if _driver(case_id) == 'positions':
            for field in ('accounts', 'positions', 'lots', 'accepted_snapshots'):
                result[field] *= 4
            return result
        result['history_density'] = base_dimensions.get('history_density', 1) * 4
        return result
    elif family == 'P08':
        fields = ('saved_plans',)
    elif family == 'P09':
        driver = _driver(case_id)
        fields = (driver,)
    elif family == 'P10':
        fields = ('constituents_per_fund',)
    elif family == 'P11':
        fields = ('parquet_observations',)
    elif family == 'P12':
        result['historical_assets'] = base_dimensions.get('historical_assets', 2) * 4
        return result
    elif family == 'P13':
        fields = ('accounts', 'positions', 'lots', 'accepted_snapshots')
    elif family == 'P14':
        fields = ('research_chunks',)
    else:
        raise ValueError(f'Unknown workload family: {family}')
    for field in fields:
        if field not in base_dimensions:
            raise ValueError(f'Missing matched scaling dimension: {field}')
        result[field] = base_dimensions[field] * 4
    return result


def project(report, case_id):
    """Return a derived logical-count view; never alter archived observation evidence."""
    result = deepcopy(report)
    driver = _driver(case_id)
    for row in result['cases'][case_id]['samples']:
        counts = row.get('counts', {})
        if driver not in counts:
            # Only dimensions actually attested by the observation are acceptable.
            if driver == 'constituent_observations' and all(
                    name in counts for name in ('funds', 'constituents_per_fund', 'fund_vintages')):
                value = counts['funds'] * counts['constituents_per_fund'] * counts['fund_vintages']
            else:
                raise ValueError(f'Missing measured logical driver: {driver}')
        else:
            value = counts[driver]
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError('Logical record counts must be positive measured integers')
        row['counts'] = {'logical_records': value}
    return result
