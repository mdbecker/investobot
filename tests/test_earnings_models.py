import copy

import pytest
from pytest_bdd import given, scenarios, then, when

from invest.earnings_models import EarningsResearchInput

scenarios('features/earnings_models.feature')


def package():
    return {
        'schema_version': '1.0', 'research_type': 'EARNINGS_FINANCIAL_STATEMENTS',
        'company': {'name': 'Fictional Technology Corporation', 'ticker': 'FAKE',
                    'cik': '0000000001', 'security_id': None},
        'reporting_period': {'fiscal_year': 2026, 'fiscal_period': 'Q2',
                             'period_end': '2026-06-30'},
        'researched_as_of': '2026-10-10', 'coverage_status': 'PARTIAL',
        'sources': [{'id': 'filing', 'source_type': 'SEC_10_Q',
                     'url': 'https://example.invalid/filing?record_id=public&api_key=secret',
                     'accession_number': 'SYNTHETIC-ACCESSION', 'filed_at': '2026-08-01',
                     'accessed_at': '2026-10-10', 'publisher': 'Fictional Corporation'}],
        'metrics': [{'id': 'revenue', 'metric_code': 'REVENUE',
                     'metric_label': 'Consolidated revenue', 'value': '1250000000.00',
                     'unit': 'USD', 'accounting_basis': 'GAAP', 'measurement_type': 'REPORTED',
                     'period_type': 'DURATION', 'period_start': '2026-04-01',
                     'period_end': '2026-06-30', 'fiscal_year': 2026, 'fiscal_period': 'Q2',
                     'scope': 'CONSOLIDATED', 'segment_name': None, 'source_id': 'filing',
                     'source_locator': 'Financial statements; consolidated revenue',
                     'xbrl_taxonomy': None, 'xbrl_concept': None}],
        'guidance': [], 'findings': [], 'limitations': ['Synthetic partial example'],
    }


@pytest.fixture
def ctx():
    return {}


@given('a synthetic source-backed earnings package')
def earnings(ctx):
    ctx['package'] = package()


@when('earnings research is validated')
def validated(ctx):
    ctx['model'] = EarningsResearchInput.model_validate(ctx['package'])


@then('its exact values and source periods are preserved')
def preserved(ctx):
    exported = ctx['model'].model_dump(mode='json')
    assert exported['metrics'][0]['value'] == '1250000000.00'
    assert exported['metrics'][0]['period_start'] == '2026-04-01'
    assert exported['sources'][0]['url'] == 'https://example.invalid/filing?record_id=public'


@when('a nine-month cash-flow fact is labeled as third-quarter only')
def confused(ctx):
    metric = ctx['package']['metrics'][0]
    metric.update(metric_code='OPERATING_CASH_FLOW', period_start='2026-01-01',
                  period_end='2026-09-30', fiscal_period='Q3')
    ctx['package']['reporting_period'].update(fiscal_period='Q3', period_end='2026-09-30')
    try:
        EarningsResearchInput.model_validate(ctx['package'])
    except ValueError as error:
        ctx['error'] = error


@then('the unsupported quarterly representation is rejected')
def rejected(ctx):
    assert isinstance(ctx.get('error'), ValueError)


@pytest.mark.parametrize('mutation', [
    lambda p: p.update(extra='unknown'),
    lambda p: p['company'].update(address='private'),
    lambda p: p['company'].update(cik='not-a-cik'),
    lambda p: p['metrics'][0].update(source_id='missing'),
    lambda p: p['metrics'][0].update(value=1.5),
    lambda p: p['metrics'][0].update(value='NaN'),
    lambda p: p['metrics'][0].update(value='1e9'),
    lambda p: p['metrics'][0].update(unit='BANANAS'),
    lambda p: p['metrics'][0].update(unit='shares'),
    lambda p: p['metrics'][0].update(period_start=None),
    lambda p: p['metrics'][0].update(period_type='INSTANT'),
    lambda p: p['metrics'][0].update(period_start='2026-07-01'),
    lambda p: p['metrics'][0].update(measurement_type='ESTIMATED'),
    lambda p: p['metrics'][0].update(scope='SEGMENT', segment_name=None),
    lambda p: p['metrics'][0].update(segment_name='Cloud'),
    lambda p: p['metrics'][0].update(source_locator=''),
    lambda p: p['metrics'][0].update(xbrl_taxonomy='us-gaap'),
    lambda p: p['metrics'].append(copy.deepcopy(p['metrics'][0])),
    lambda p: p['metrics'].append({**p['metrics'][0], 'id': 'conflict', 'value': '1'}),
    lambda p: p['sources'].append(copy.deepcopy(p['sources'][0])),
    lambda p: p['sources'][0].update(cik='0000000002'),
    lambda p: p['sources'][0].update(accession_number=None),
    lambda p: p['sources'][0].update(filed_at='2026-10-11'),
    lambda p: p['sources'][0].update(is_amendment=True),
    lambda p: p['sources'][0].update(is_restatement=True),
    lambda p: p['sources'][0].update(accepted_at='2026-10-11T12:00:00Z'),
    lambda p: p['reporting_period'].update(period_end='2026-12-31'),
    lambda p: p['findings'].append({'id': 'finding', 'category': 'VERIFIED_FACT',
                                  'statement': 'Unsupported fact', 'source_id': None,
                                  'source_locator': None, 'limitations': []}),
])
def test_invalid_earnings_inputs(mutation):
    incoming = package()
    mutation(incoming)
    with pytest.raises(ValueError):
        EarningsResearchInput.model_validate(incoming)


def test_accept_explicit_ytd_in_quarterly_filing():
    incoming = package()
    incoming['reporting_period'].update(fiscal_period='Q3', period_end='2026-09-30')
    incoming['sources'][0]['filed_at'] = '2026-10-01'
    incoming['metrics'][0].update(metric_code='OPERATING_CASH_FLOW', period_start='2026-01-01',
                                  period_end='2026-09-30', fiscal_period='Q3', period_length='YTD')
    model = EarningsResearchInput.model_validate(incoming)
    assert model.metrics[0].period_length == 'YTD'


def test_exact_scaling_beyond_decimal_context():
    incoming = package()
    value = '1.123456789012345678901234567890123456789'
    scaled = '1123456.789012345678901234567890123456789'
    incoming['metrics'][0].update(value=scaled, source_value=value,
                                  source_unit='USD_MILLIONS', source_scale='1000000')
    model = EarningsResearchInput.model_validate(incoming)
    assert model.model_dump(mode='json')['metrics'][0]['value'] == scaled
    incoming['metrics'][0]['value'] = scaled + '1'
    with pytest.raises(ValueError):
        EarningsResearchInput.model_validate(incoming)


def test_empty_research_requires_explicit_partial_coverage():
    incoming = package()
    incoming.update(sources=[], metrics=[])
    EarningsResearchInput.model_validate(incoming)
    incoming['coverage_status'] = 'COMPLETE_WITHIN_DECLARED_SCOPE'
    with pytest.raises(ValueError):
        EarningsResearchInput.model_validate(incoming)


def test_guidance_bounds_and_withdrawal_reference():
    incoming = package()
    guidance = {'id': 'outlook', 'metric_code': 'REVENUE', 'period_start': '2026-07-01',
                'period_end': '2026-09-30', 'lower_value': '1', 'upper_value': '2',
                'unit': 'USD', 'accounting_basis': 'NON_GAAP', 'guidance_status': 'ISSUED',
                'source_id': 'filing', 'source_locator': 'Outlook', 'qualifiers': 'Synthetic'}
    incoming['guidance'] = [guidance]
    EarningsResearchInput.model_validate(incoming)
    guidance.update(lower_value='3')
    with pytest.raises(ValueError):
        EarningsResearchInput.model_validate(incoming)
    guidance.update(lower_value=None, upper_value=None, guidance_status='WITHDRAWN')
    with pytest.raises(ValueError):
        EarningsResearchInput.model_validate(incoming)
    guidance['prior_guidance_id'] = 'historical-guidance-run:outlook'
    EarningsResearchInput.model_validate(incoming)


def test_unknown_cik_is_retained_as_unknown_and_segment_scopes_are_distinct():
    incoming = package()
    incoming['company']['cik'] = None
    incoming['metrics'].append({**incoming['metrics'][0], 'id': 'segment',
                               'scope': 'SEGMENT', 'segment_name': 'Cloud', 'value': '1',
                               'metric_code': 'SEGMENT_REVENUE'})
    model = EarningsResearchInput.model_validate(incoming)
    assert model.company.cik is None
    assert len(model.metrics) == 2


def test_instant_fact_has_no_duration():
    incoming = package()
    incoming['metrics'][0].update(metric_code='OTHER', metric_label='Cash balance',
                                 period_type='INSTANT', period_start=None)
    EarningsResearchInput.model_validate(incoming)


def test_amended_source_preserves_original_accession():
    incoming = package()
    incoming['sources'][0].update(is_amendment=True,
                                  original_accession_number='ORIGINAL-SYNTHETIC-ACCESSION')
    model = EarningsResearchInput.model_validate(incoming)
    assert model.sources[0].original_accession_number == 'ORIGINAL-SYNTHETIC-ACCESSION'


def test_nonstrings_units_are_input_errors():
    incoming = package()
    incoming['metrics'][0]['unit'] = 123
    with pytest.raises(ValueError):
        EarningsResearchInput.model_validate(incoming)


def test_earnings_schema_advertises_decimal_strings():
    schema = EarningsResearchInput.model_json_schema()
    assert schema['$defs']['EarningsMetric']['properties']['value']['type'] == 'string'


def test_unknown_guidance_issue_date_is_not_a_filing_date():
    incoming = package()
    incoming['guidance'] = [{'id': 'outlook', 'metric_code': 'REVENUE',
        'period_start': '2026-07-01', 'period_end': '2026-09-30',
        'lower_value': '1', 'upper_value': '2', 'unit': 'USD',
        'accounting_basis': 'GAAP', 'guidance_status': 'ISSUED',
        'source_id': 'filing', 'source_locator': 'Outlook', 'qualifiers': 'Synthetic'}]
    assert EarningsResearchInput.model_validate(incoming).guidance[0].issued_at is None
