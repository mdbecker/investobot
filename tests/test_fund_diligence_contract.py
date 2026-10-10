"""Fictional offline disclosures exercise conservative share-class validation."""

import copy
import importlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError


def package():
    return json.loads((Path(__file__).parent / 'fixtures/fund_diligence.json').read_text())


def model():
    try:
        module = importlib.import_module('invest.fund_diligence_models')
    except ModuleNotFoundError:
        pytest.fail('Fund diligence must expose its strict, validated JSON contract')
    assert hasattr(module, 'FundDiligenceInput'), 'Fund diligence input contract is required'
    return module.FundDiligenceInput


def validate(payload):
    return model().model_validate(payload)


def change(payload, path, value):
    target = payload
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value


@pytest.mark.parametrize(('path', 'value'), [
    (('fund', 'registrant_cik'), '123'),
    (('fund', 'series_id'), 'S123'),
    (('fund', 'class_id'), None),
    (('fund', 'fund_type'), 'ETN'),
    (('fund', 'fund_type'), 'LEVERAGED_ETF'),
    (('fund', 'strategy_type'), 'OTHER'),
    (('sources', 0, 'registrant_cik'), '0000000456'),
    (('sources', 1, 'series_id'), 'S000000456'),
    (('sources', 1, 'class_id'), 'C000000456'),
    (('sources', 0, 'accession_number'), '0000000123-26-000002'),
    (('sources', 0, 'url'), 'https://www.sec.gov/Archives/edgar/data/456/000000012326000001/a.htm'),
    (('sources', 1, 'url'), 'https://user:secret@example.invalid/prospectus'),
    (('sources', 1, 'published_at'), '2026-10-11'),
    (('sources', 1, 'accessed_at'), '2026-10-11'),
    (('scope', 'researched_as_of'), '2099-01-01'),
    (('holdings_snapshot', 'as_of_date'), '2026-10-11'),
    (('holdings_snapshot', 'source_id'), 'missing'),
    (('holdings', 0, 'source_id'), 'missing'),
    (('holdings', 0, 'source_id'), 'prospectus'),
    (('holdings', 0, 'weight_pct'), '-1'),
    (('holdings', 0, 'weight_pct'), '101'),
    (('holdings', 0, 'weight_pct'), 6.0),
    (('holdings', 0, 'weight_pct'), '6e0'),
    (('holdings', 0, 'weight_pct'), 'NaN'),
    (('holdings', 1, 'weight_pct'), '7'),
    (('methodology', 'index_name'), None),
    (('methodology', 'source_ids'), []),
    (('methodology', 'source_ids'), ['missing']),
    (('metrics', 0, 'source_id'), 'missing'),
    (('metrics', 0, 'scope'), 'SERIES'),
    (('metrics', 0, 'unit'), 'USD'),
    (('metrics', 0, 'value'), '-0.01'),
    (('metrics', 0, 'value'), 0.15),
    (('metrics', 0, 'value'), '1.5e-1'),
    (('metrics', 0, 'observed_as_of'), '2026-10-11'),
    (('findings', 0, 'source_ids'), []),
    (('findings', 0, 'source_ids'), ['missing']),
    (('limitations',), []),
])
def test_rejects_contradictory_or_unsupported_disclosures(path, value):
    payload = package()
    change(payload, path, value)
    contract = model()
    with pytest.raises(ValidationError):
        contract.model_validate(payload)


@pytest.mark.parametrize('path', [(), ('fund',), ('scope',), ('sources', 0),
                                 ('methodology',), ('holdings_snapshot',),
                                 ('holdings', 0), ('metrics', 0), ('findings', 0)])
def test_every_nested_object_rejects_extra_fields(path):
    payload = package()
    target = payload
    for key in path:
        target = target[key]
    target['invented_investment_score'] = 100
    contract = model()
    with pytest.raises(ValidationError):
        contract.model_validate(payload)


def test_accepts_fictional_fund_without_inventing_unknowns():
    result = validate(package()).model_dump(mode='json')
    assert result['methodology']['reconstitution_policy'] is None
    assert result['fund']['security_id'] is None
    assert result['holdings_snapshot']['coverage'] == 'TOP_N'


@pytest.mark.parametrize('collection', ['sources', 'holdings', 'metrics', 'findings'])
def test_duplicate_record_ids_rejected(collection):
    payload = package()
    payload[collection].append(copy.deepcopy(payload[collection][0]))
    contract = model()
    with pytest.raises(ValidationError):
        contract.model_validate(payload)


def test_duplicate_metric_observation_rejected_even_with_different_id():
    payload = package()
    metric = copy.deepcopy(payload['metrics'][0])
    metric['id'] = 'another-id'
    payload['metrics'].append(metric)
    contract = model()
    with pytest.raises(ValidationError):
        contract.model_validate(payload)


def test_identity_requires_original_sec_evidence():
    payload = package()
    payload['sources'] = payload['sources'][1:]
    contract = model()
    with pytest.raises(ValidationError):
        contract.model_validate(payload)


def test_reported_long_only_weights_cannot_exceed_rounding_allowance():
    payload = package()
    payload['holdings'][0]['weight_pct'] = '60'
    payload['holdings'][1]['weight_pct'] = '40.500000000000000000001'
    contract = model()
    with pytest.raises(ValidationError):
        contract.model_validate(payload)


def test_tiny_literal_decimal_remains_exact():
    payload = package()
    payload['holdings'][1]['weight_pct'] = '0.000000000000000000000000000000000001'
    payload['metrics'][0]['value'] = '0.150000000000000000000000000000000001'
    result = validate(payload).model_dump(mode='json')
    assert result['holdings'][1]['weight_pct'] == payload['holdings'][1]['weight_pct']
    assert result['metrics'][0]['value'] == payload['metrics'][0]['value']


def test_unavailable_holdings_require_empty_undated_snapshot():
    payload = package()
    payload['holdings_snapshot']['coverage'] = 'UNAVAILABLE'
    contract = model()
    with pytest.raises(ValidationError):
        contract.model_validate(payload)
    payload['holdings'] = []
    payload['holdings_snapshot'].update(as_of_date=None, source_id=None,
                                        holdings_count_reported=None)
    assert validate(payload).holdings == []


def test_full_coverage_needs_affirmative_complete_disclosure():
    payload = package()
    payload['holdings_snapshot']['coverage'] = 'FULL'
    contract = model()
    with pytest.raises(ValidationError):
        contract.model_validate(payload)


def test_hundred_row_limit_is_not_a_bulk_holdings_import():
    payload = package()
    payload['holdings'] = [{**payload['holdings'][0], 'id': f'h-{i}', 'weight_pct': '0'}
                           for i in range(101)]
    payload['holdings_snapshot']['holdings_count_reported'] = 101
    contract = model()
    with pytest.raises(ValidationError):
        contract.model_validate(payload)


def test_active_fund_requires_approach_and_cannot_claim_index():
    payload = package()
    payload['fund']['strategy_type'] = 'ACTIVE'
    contract = model()
    with pytest.raises(ValidationError):
        contract.model_validate(payload)
    payload['methodology'].update(index_name=None, active_approach='Select reported quality equities.')
    assert validate(payload).fund.strategy_type == 'ACTIVE'


@pytest.mark.parametrize(('code', 'value', 'accepted'), [
    ('AVG_PREMIUM_DISCOUNT', '-0.08', True),
    ('MEDIAN_BID_ASK_SPREAD', '-0.08', False),
    ('MEDIAN_BID_ASK_SPREAD', '0.08', True),
])
def test_signed_premium_is_distinct_from_spread(code, value, accepted):
    payload = package()
    payload['metrics'][0].update(code=code, value=value, period_start='2026-09-01',
                                period_end='2026-09-20')
    contract = model()
    if accepted:
        assert contract.model_validate(payload)
    else:
        with pytest.raises(ValidationError):
            contract.model_validate(payload)


def test_mutual_fund_cannot_report_etf_spread():
    payload = package()
    payload['fund']['fund_type'] = 'MUTUAL_FUND'
    payload['metrics'][0].update(code='MEDIAN_BID_ASK_SPREAD', value='0.08',
                                period_start='2026-09-01', period_end='2026-09-20')
    contract = model()
    with pytest.raises(ValidationError):
        contract.model_validate(payload)


def test_distribution_date_and_explicit_pay_or_ex_note_required():
    payload = package()
    payload['metrics'][0].update(code='LONG_TERM_CAPITAL_GAIN_DISTRIBUTION',
                                unit='USD_PER_SHARE', value='0.40')
    contract = model()
    with pytest.raises(ValidationError):
        contract.model_validate(payload)
    payload['metrics'][0].update(period_end='2026-09-20', notes='Payable date 2026-09-20.')
    assert validate(payload)


def test_turnover_requires_an_actual_reporting_period():
    payload = package()
    payload['metrics'][0].update(code='PORTFOLIO_TURNOVER', value='18', scope='SERIES')
    contract = model()
    with pytest.raises(ValidationError):
        contract.model_validate(payload)
    payload['metrics'][0].update(period_start='2025-09-21', period_end='2026-09-20')
    assert validate(payload)


def test_reported_period_cannot_run_backwards():
    payload = package()
    payload['metrics'][0].update(period_start='2026-09-21', period_end='2026-09-20')
    contract = model()
    with pytest.raises(ValidationError):
        contract.model_validate(payload)


def test_disclosed_expired_waiver_remains_historical_evidence():
    payload = package()
    payload['metrics'][0].update(waiver_end_date='2026-09-30',
                                notes='Reported fee waiver expired on 2026-09-30.')
    result = validate(payload).model_dump(mode='json')
    assert result['metrics'][0]['waiver_end_date'] == '2026-09-30'


def test_unknown_waiver_expiration_requires_explicit_limitation():
    payload = package()
    payload['metrics'][0]['notes'] = 'Net expense ratio includes a contractual fee waiver.'
    contract = model()
    with pytest.raises(ValidationError):
        contract.model_validate(payload)
    payload['metrics'][0]['notes'] += ' Waiver expiration could not be verified.'
    assert validate(payload)


@pytest.mark.parametrize(('path', 'key'), [
    (('fund',), 'ticker'), (('fund',), 'security_id'),
    (('sources', 0), 'filed_at'), (('methodology',), 'selection_rules'),
    (('holdings', 0), 'security_identifier'), (('metrics', 0), 'waiver_end_date'),
])
def test_nullable_fields_are_explicit_unknowns_not_omitted(path, key):
    payload = package()
    target = payload
    for part in path:
        target = target[part]
    del target[key]
    contract = model()
    with pytest.raises(ValidationError):
        contract.model_validate(payload)


def test_class_fees_need_class_attribution_not_only_series_evidence():
    payload = package()
    payload['sources'][1]['class_id'] = None
    contract = model()
    with pytest.raises(ValidationError):
        contract.model_validate(payload)


def test_record_ids_cannot_collide_between_collections():
    payload = package()
    payload['holdings'][0]['id'] = payload['metrics'][0]['id']
    contract = model()
    with pytest.raises(ValidationError):
        contract.model_validate(payload)


def test_duplicated_limitations_are_not_distinct_statements():
    payload = package()
    payload['limitations'].append(payload['limitations'][0])
    contract = model()
    with pytest.raises(ValidationError):
        contract.model_validate(payload)


def test_verified_zero_is_an_explicit_reported_fee_not_missing_data():
    payload = package()
    payload['metrics'][0].update(value='0', notes='Prospectus explicitly reports zero net expenses.')
    assert validate(payload).model_dump(mode='json')['metrics'][0]['value'] == '0'
