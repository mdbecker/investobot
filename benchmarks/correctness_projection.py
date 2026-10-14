"""Bounded comparison of reviewed additions; native outputs remain independently checked."""
import hashlib
import json
from decimal import Decimal


def project(value):
    if isinstance(value, list):
        return [project(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {key: project(item) for key, item in value.items()}
    if 'snapshots' in result:
        result['snapshots'] = sorted(result['snapshots'], key=lambda row: json.dumps(
            row, sort_keys=True, default=str))
    if 'account' in value and 'source_hash' in value and 'positions_complete' in value:
        if value.get('issues') == []:
            result.pop('issues', None)
        if value.get('institution_status') is None:
            result.pop('institution_status', None)
    if 'eligible_accounts' in value:
        for key in ('short_term_gain_budget', 'long_term_gain_budget'):
            if key in value:
                if value[key] is not None:
                    raise ValueError('Nonempty retired gain budget cannot be projected')
                result.pop(key)
    if value.get('algorithm_version') == 'contribution-first-hifo-1':
        if 'saved' in value:
            if value['saved'] is not True:
                raise ValueError('Unsaved preview cannot stand for a saved-plan workflow')
            result.pop('saved')
        analysis = result.get('tax_analysis', {})
        for key in ('realized_gain_loss', 'short_term_gain_loss', 'long_term_gain_loss',
                    'positive_estimated_tax_cost'):
            if key in analysis:
                if Decimal(analysis[key]) != 0:
                    raise ValueError('Nonzero new sale estimate cannot be projected')
                analysis.pop(key)
        result['source_state_hash'] = hashlib.sha256(json.dumps(
            result['source_state'], sort_keys=True, default=str).encode()).hexdigest()
    if 'tax_summary' in value:
        for key in ('short_term_gain_loss', 'long_term_gain_loss'):
            if result['tax_summary'].get(key) == '0':
                result['tax_summary'][key] = None
    if 'exposures' in value and 'unknown_exposure_value' in value:
        total = value.get('total_value')
        if 'known_value_subtotal' in value:
            if total is None or Decimal(value['known_value_subtotal']) != Decimal(total):
                raise ValueError('Partial denominator cannot be projected')
            result.pop('known_value_subtotal')
        for key in ('numeric_complete', 'evidence_complete'):
            if key in value:
                if value[key] is not True:
                    raise ValueError('Incomplete new exposure evidence cannot be projected')
                result.pop(key)
        if 'unresolved_identity_value' in value:
            if value['unresolved_identity_value'] != value['unresolved_issuer_value']:
                raise ValueError('Unresolved amount differs from native issuer coverage')
            result.pop('unresolved_identity_value')
        if value.get('warnings') == []:
            result.pop('warnings', None)
        for key in ('by_sector', 'by_asset_type'):
            if key in value:
                if sum((Decimal(amount) for amount in value[key].values()), Decimal(0)) != Decimal(total):
                    raise ValueError('Exposure subtotals do not conserve the native denominator')
                result.pop(key)
        if 'fund_coverage' in value:
            for row in value['fund_coverage'].values():
                if (row['represented_weight'] != '1' or row['reported_weight'] != '1'
                        or row['numeric_complete'] is not True or row['evidence_complete'] is not True
                        or not row['source'] or not row['data_as_of']):
                    raise ValueError('New fund coverage does not support the complete fixed fixture')
            result.pop('fund_coverage')
    if 'contributions' in value and 'total_value' in value and 'security_id' in value:
        identity = value.get('identity')
        if identity:
            if identity.get('ticker') != value.get('ticker'):
                raise ValueError('Supplemental identity disagrees with the native ticker')
            result.pop('identity', None)
        evidence = value.get('issuer_identity_evidence')
        if evidence:
            if evidence.get('reviewed') is not True or not evidence.get('source_locator'):
                raise ValueError('Supplemental issuer evidence is not reviewed')
            result.pop('issuer_identity_evidence', None)
        elif value.get('issuer_identity_evidence') is None:
            result.pop('issuer_identity_evidence', None)
        result.pop('name', None)
        if value.get('observed_identifier') is None:
            result.pop('observed_identifier', None)
    if 'source_id' in value and 'security_id' in value and 'as_of' in value:
        for key in ('stale', 'provisional'):
            if key in value:
                if value[key] is not False:
                    raise ValueError('Uncertain exposure path cannot be projected')
                result.pop(key)
    return result
