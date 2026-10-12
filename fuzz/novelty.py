"""Local retained-history validation, exact input deduplication and structural novelty."""
import re
from copy import deepcopy

from fuzz.scenario import validate


def validate_history(history):
    if not isinstance(history, dict) or set(history) != {'schema_version', 'campaigns', 'bootstrap'}:
        raise ValueError('Unknown history fields')
    if type(history['schema_version']) is not int or history['schema_version'] != 1 or type(history['bootstrap']) is not bool:
        raise ValueError('Invalid history version/bootstrap')
    campaigns = history['campaigns']
    if not isinstance(campaigns, list) or len(campaigns) > 10000:
        raise ValueError('Unbounded campaign history')
    for campaign in campaigns:
        if not isinstance(campaign, dict) or set(campaign) != {'campaign_id', 'case_hashes'}:
            raise ValueError('Unknown saved campaign fields')
        if not isinstance(campaign['campaign_id'], str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}', campaign['campaign_id']):
            raise ValueError('Unsafe campaign identity')
        rows = campaign['case_hashes']
        if not isinstance(rows, list) or len(rows) > 100:
            raise ValueError('Unbounded hash inventory')
        for row in rows:
            if not isinstance(row, dict) or set(row) != {'id', 'family', 'input_hash', 'shape_hash'}:
                raise ValueError('Unknown saved identity fields')
            if not isinstance(row['id'], str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}', row['id']):
                raise ValueError('Unsafe case identity')
            if not isinstance(row['family'], str) or row['family'] not in {f'P{i:02}' for i in range(1, 16)}:
                raise ValueError('Invalid family')
            for key in ('input_hash', 'shape_hash'):
                if not isinstance(row[key], str) or not re.fullmatch(r'[0-9a-f]{64}', row[key]):
                    raise ValueError('Invalid canonical SHA-256')
    return deepcopy(history)


def assess(payload, history, acknowledge_missing=False, large=False):
    validation = validate(payload, large=large)
    if validation['status'] != 'VALID':
        return {'status': 'REJECTED', 'issues': validation['issues']}
    if history is None and not acknowledge_missing:
        return {'status': 'ACKNOWLEDGMENT_REQUIRED', 'issues': [{'code': 'MISSING_HISTORY'}]}
    reset = history is None
    if history is None:
        history = {'schema_version': 1, 'bootstrap': True, 'campaigns': []}
    try:
        history = validate_history(history)
    except ValueError as error:
        return {'status': 'REJECTED', 'issues': [{'code': 'INVALID_HISTORY', 'message': str(error)}]}
    identities = validation['case_hashes']
    retained = {row['input_hash'] for campaign in history['campaigns'] for row in campaign['case_hashes']}
    prior_shapes = {row['shape_hash'] for campaign in history['campaigns'][-10:] for row in campaign['case_hashes']}
    duplicates = [row['input_hash'] for row in identities if row['input_hash'] in retained]
    novel = sum(row['shape_hash'] not in prior_shapes for row in identities)
    issues = []
    if duplicates:
        issues.append({'code': 'DUPLICATE_EXECUTABLE_INPUT'})
    if novel * 4 < len(identities):
        issues.append({'code': 'INSUFFICIENT_STRUCTURAL_NOVELTY'})
    return {'status': 'REJECTED' if issues else 'ACCEPTED', 'issues': issues,
            'case_hashes': identities, 'duplicate_inputs': duplicates,
            'novel_shape_fraction': novel / len(identities), 'history_reset_acknowledged': reset}


def coverage(history):
    checked = validate_history(history)
    families = {row['family'] for campaign in checked['campaigns'][-5:] for row in campaign['case_hashes']}
    missing = {f'P{i:02}' for i in range(1, 16)} - families
    return {'covered_families': sorted(families), 'missing_families': sorted(missing),
            'complete': not missing, 'campaigns_considered': min(5, len(checked['campaigns']))}
