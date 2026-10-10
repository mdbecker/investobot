import copy
import json
import sqlite3
from types import SimpleNamespace

import pytest
from pytest_bdd import given, scenarios, then, when

from invest import earnings_queries
from invest.models import DomainError

scenarios('features/earnings_queries.feature')


def test_exact_small_percentage_does_not_claim_division_rounding(ctx):
    store(ctx, package(2025, '1'), 'previous')
    store(ctx, package(2026, '1.00001'), 'current')
    result = earnings_queries.compare(ctx['ledger'], 'previous', 'current')
    assert result['comparisons'][0]['percentage_change'] == '0.00100'
    assert not any('rounded' in warning.lower() for warning in result['warnings'])

METRIC_COLUMNS = ('metric_id', 'metric_code', 'metric_label', 'metric_definition',
                  'value_text', 'unit', 'accounting_basis', 'period_type', 'period_length',
                  'period_start', 'period_end', 'fiscal_year', 'fiscal_period',
                  'measurement_type', 'scope', 'segment_name', 'source_id', 'source_locator',
                  'xbrl_taxonomy', 'xbrl_concept')


@pytest.fixture
def ctx():
    connection = sqlite3.connect(':memory:')
    connection.execute('''CREATE TABLE research_runs (
        id TEXT PRIMARY KEY, research_type TEXT, skill_name TEXT, skill_version TEXT,
        schema_version TEXT, company_name TEXT, ticker TEXT, security_id TEXT, cik TEXT,
        fiscal_year INTEGER, fiscal_period TEXT, period_end TEXT, researched_as_of TEXT,
        imported_at TEXT, coverage_status TEXT, summary_json TEXT, package_json TEXT)''')
    connection.execute('CREATE TABLE research_earnings_metrics (run_id TEXT, ' +
                       ', '.join(f'{column} TEXT' for column in METRIC_COLUMNS) + ')')
    connection.execute('CREATE TABLE research_earnings_guidance (run_id TEXT, guidance_id TEXT)')
    connection.execute('CREATE TABLE research_earnings_findings (run_id TEXT, finding_id TEXT)')
    connection.execute('''CREATE TABLE research_sources (
        run_id TEXT, source_id TEXT, source_type TEXT, publisher TEXT, url TEXT,
        accession_number TEXT, filed_at TEXT, accessed_at TEXT,
        is_amendment INTEGER, is_restatement INTEGER, original_accession_number TEXT)''')
    yield {'ledger': SimpleNamespace(connection=connection)}
    connection.close()


def package(year=2026, value='125.00'):
    return {
        'schema_version': '1.0', 'research_type': 'EARNINGS_FINANCIAL_STATEMENTS',
        'company': {'name': 'Fictional Corporation', 'ticker': 'FICTION',
                    'cik': '0000000001', 'security_id': None},
        'reporting_period': {'fiscal_year': year, 'fiscal_period': 'Q2',
                             'period_end': f'{year}-06-30'},
        'researched_as_of': '2026-10-10', 'coverage_status': 'PARTIAL',
        'sources': [{'id': 'source-1', 'source_type': 'SEC_10_Q',
                     'url': 'https://example.invalid/filing', 'publisher': 'Fictional Corporation',
                     'accession_number': 'SYNTHETIC-ACCESSION', 'filed_at': '2026-08-01',
                     'accessed_at': '2026-10-10'}],
        'metrics': [{'id': 'revenue', 'metric_code': 'REVENUE',
                     'metric_label': 'Revenue', 'metric_definition': 'Consolidated revenue',
                     'value': value, 'unit': 'USD', 'accounting_basis': 'GAAP',
                     'period_type': 'DURATION', 'period_length': 'QUARTER',
                     'period_start': f'{year}-04-01', 'period_end': f'{year}-06-30',
                     'fiscal_year': year, 'fiscal_period': 'Q2',
                     'measurement_type': 'REPORTED', 'scope': 'CONSOLIDATED',
                     'segment_name': None, 'source_id': 'source-1',
                     'source_locator': 'Statement of income',
                     'xbrl_taxonomy': None, 'xbrl_concept': None}],
        'guidance': [], 'findings': [], 'limitations': ['Synthetic partial coverage.'],
    }


def store(ctx, data, identity='current'):
    period = data['reporting_period']
    company = data['company']
    summary = {'metric_count': len(data['metrics']), 'guidance_count': len(data['guidance']),
               'finding_count': len(data['findings']), 'warnings': data['limitations']}
    connection = ctx['ledger'].connection
    connection.execute('INSERT INTO research_runs VALUES (' + ','.join('?' * 17) + ')',
        (identity, data['research_type'], 'investobot-earnings', '1.0', '1.0',
         company['name'], company['ticker'], company['security_id'], company['cik'],
         period['fiscal_year'], period['fiscal_period'], period['period_end'],
         data['researched_as_of'], '2026-10-10T12:00:00+00:00', data['coverage_status'],
         json.dumps(summary), json.dumps(data)))
    for metric in data['metrics']:
        row = {'metric_id': metric['id'], 'value_text': metric['value'], **metric}
        connection.execute('INSERT INTO research_earnings_metrics VALUES (' +
            ','.join('?' * (len(METRIC_COLUMNS) + 1)) + ')',
            (identity, *(row[column] for column in METRIC_COLUMNS)))
    for source in data['sources']:
        connection.execute('INSERT INTO research_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)',
            (identity, source['id'], source['source_type'], source['publisher'], source['url'],
             source['accession_number'], source['filed_at'], source['accessed_at'],
             source.get('is_amendment', False), source.get('is_restatement', False),
             source.get('original_accession_number')))
    for name, key in (('guidance', 'guidance_id'), ('findings', 'finding_id')):
        for item in data[name]:
            connection.execute(f'INSERT INTO research_earnings_{name} (run_id, {key}) VALUES (?,?)',
                               (identity, item['id']))


@given('saved fictional quarterly earnings with GAAP and adjusted metrics')
def saved(ctx):
    data = package()
    adjusted = copy.deepcopy(data['metrics'][0])
    adjusted.update(id='adjusted-revenue', accounting_basis='NON_GAAP', value='130.00')
    data['metrics'].append(adjusted)
    data['guidance'] = [{'id': 'outlook'}]
    data['findings'] = [{'id': 'finding'}]
    ctx['package'] = data
    store(ctx, data)


@when('the saved earnings summary is requested')
def summarize(ctx):
    ctx['result'] = earnings_queries.summary(ctx['ledger'], 'current')


@then('exact values bases and source references remain separate')
def summary_values(ctx):
    result = ctx['result']
    assert {(row['value'], row['accounting_basis'], row['source_id'])
            for row in result['metrics']} == {
                ('125.00', 'GAAP', 'source-1'), ('130.00', 'NON_GAAP', 'source-1')}
    assert result['guidance_count'] == result['findings_count'] == 1
    assert 'Synthetic partial coverage.' in result['warnings']


@then('unavailable growth is null with a warning')
def unavailable(ctx):
    assert ctx['result']['year_over_year_growth'] is None
    assert any('comparable' in warning.lower() for warning in ctx['result']['warnings'])


@given('two comparable fictional second-quarter earnings runs')
def compatible(ctx):
    store(ctx, package(2025, '100.00'), 'previous')
    store(ctx, package(), 'current')


@when('saved earnings runs are compared')
def compare(ctx):
    ctx['result'] = earnings_queries.compare(ctx['ledger'], 'previous', 'current')


@then('absolute and percentage changes use the saved exact values')
def comparison(ctx):
    row = ctx['result']['comparisons'][0]
    assert row['absolute_change'] == '25.00'
    assert row['percentage_change'] == '25.00'
    assert row['run_a_metric_id'] == row['run_b_metric_id'] == 'revenue'
    assert row['source_a_id'] == row['source_b_id'] == 'source-1'


@when('earnings runs matching the ticker are listed')
def listing(ctx):
    ctx['queries'] = []
    ctx['ledger'].connection.set_trace_callback(ctx['queries'].append)
    ctx['result'] = earnings_queries.list_runs(ctx['ledger'], ticker='fiction')


@then('only matching compact metadata is returned without package reads')
def compact(ctx):
    assert len(ctx['result']['runs']) == 1
    assert ctx['result']['runs'][0]['research_run_id'] == 'current'
    assert ctx['result']['runs'][0]['metric_count'] == 2
    assert 'package_json' not in ' '.join(ctx['queries']).lower()
    assert earnings_queries.list_runs(ctx['ledger'], ticker='OTHER') == {'runs': []}


@when('the historical earnings package is shown')
def shown(ctx):
    ctx['result'] = earnings_queries.show(ctx['ledger'], 'current')


@then('its original facts and recorded skill identity are reproduced')
def historical(ctx):
    expected = {**ctx['package'], 'research_run_id': 'current',
                'skill_name': 'investobot-earnings', 'skill_version': '1.0',
                'imported_at': '2026-10-10T12:00:00+00:00'}
    assert ctx['result'] == expected


@pytest.mark.parametrize('field,value', [
    ('accounting_basis', 'NON_GAAP'), ('unit', 'EUR'), ('scope', 'SEGMENT'),
    ('segment_name', 'Changed scope'), ('metric_definition', 'Adjusted revenue'),
    ('period_length', 'YTD'), ('fiscal_period', 'Q3'),
    ('period_start', '2026-01-01'), ('period_type', 'INSTANT'),
])
def test_incompatible_metric_returns_null_changes(ctx, field, value):
    store(ctx, package(2025, '100.00'), 'previous')
    data = package()
    data['metrics'][0][field] = value
    store(ctx, data)
    result = earnings_queries.compare(ctx['ledger'], 'previous', 'current')
    assert result['warnings']
    assert all(row['absolute_change'] is None and row['percentage_change'] is None
               for row in result['comparisons'])


@pytest.mark.parametrize('base', ['0.00', '-100.00'])
def test_nonpositive_base_prevents_misleading_percentage(ctx, base):
    store(ctx, package(2025, base), 'previous')
    store(ctx, package())
    result = earnings_queries.compare(ctx['ledger'], 'previous', 'current')
    assert result['comparisons'][0]['absolute_change'] is not None
    assert result['comparisons'][0]['percentage_change'] is None
    assert result['warnings']


@pytest.mark.parametrize('field,value', [('cik', '0000000002'), ('security_id', 'other')])
def test_conflicting_company_identity_disables_comparison(ctx, field, value):
    previous = package(2025, '100.00')
    if field == 'security_id':
        previous['company'][field] = 'original'
    store(ctx, previous, 'previous')
    current = package()
    current['company'][field] = value
    store(ctx, current)
    result = earnings_queries.compare(ctx['ledger'], 'previous', 'current')
    assert result['warnings']
    assert all(row['absolute_change'] is None for row in result['comparisons'])


def test_decimal_difference_preserves_precision_beyond_context(ctx):
    store(ctx, package(2025, '123456789012345678901234567890.01'), 'previous')
    store(ctx, package(2026, '123456789012345678901234567890.02'))
    result = earnings_queries.compare(ctx['ledger'], 'previous', 'current')
    assert result['comparisons'][0]['absolute_change'] == '0.01'


def test_summary_and_comparison_do_not_read_packages(ctx):
    compatible(ctx)
    queries = []
    ctx['ledger'].connection.set_trace_callback(queries.append)
    earnings_queries.summary(ctx['ledger'], 'current')
    earnings_queries.compare(ctx['ledger'], 'previous', 'current')
    assert 'package_json' not in ' '.join(queries).lower()


@pytest.mark.parametrize('query', [earnings_queries.show, earnings_queries.summary])
def test_missing_run_input_error(ctx, query):
    with pytest.raises(DomainError) as error:
        query(ctx['ledger'], 'missing')
    assert error.value.code == 1


def test_amendment_relationship_is_disclosed(ctx):
    store(ctx, package(2025, '100.00'), 'previous')
    data = package()
    data['sources'][0].update(is_amendment=True,
                             original_accession_number='SYNTHETIC-ACCESSION')
    store(ctx, data)
    result = earnings_queries.compare(ctx['ledger'], 'previous', 'current')
    assert any('amend' in warning.lower() for warning in result['warnings'])


def test_unregistered_company_requires_same_name_and_ticker(ctx):
    previous = package(2025, '100.00')
    previous['company']['cik'] = None
    store(ctx, previous, 'previous')
    current = package()
    current['company'].update(cik=None, name='Different Fictional Corporation')
    store(ctx, current)
    result = earnings_queries.compare(ctx['ledger'], 'previous', 'current')
    assert result['warnings']
    assert all(row['absolute_change'] is None for row in result['comparisons'])


def test_matching_cik_allows_documented_historical_name_change(ctx):
    store(ctx, package(2025, '100.00'), 'previous')
    current = package()
    current['company']['name'] = 'Renamed Fictional Corporation'
    store(ctx, current)
    result = earnings_queries.compare(ctx['ledger'], 'previous', 'current')
    assert result['comparisons'][0]['absolute_change'] == '25.00'


def test_empty_partial_research_remains_unknown(ctx):
    data = package()
    data['metrics'] = []
    store(ctx, data)
    result = earnings_queries.summary(ctx['ledger'], 'current')
    assert result['metrics'] == []
    assert result['year_over_year_growth'] is None
    assert result['warnings']


def test_distinct_quarters_are_not_compared_as_growth(ctx):
    store(ctx, package(2025, '100.00'), 'previous')
    current = package()
    current['reporting_period'].update(fiscal_period='Q3', period_end='2026-09-30')
    current['metrics'][0].update(fiscal_period='Q3', period_start='2026-07-01',
                                  period_end='2026-09-30')
    store(ctx, current)
    result = earnings_queries.compare(ctx['ledger'], 'previous', 'current')
    assert result['warnings']
    assert all(row['percentage_change'] is None for row in result['comparisons'])


def test_summary_retains_persisted_disclosure_warnings(ctx):
    data = package()
    store(ctx, data)
    warnings = ['Missing CIK: issuer identity requires human review.',
                'Non-GAAP reconciliation unavailable.', 'Amended filing retained.']
    ctx['ledger'].connection.execute(
        'UPDATE research_runs SET summary_json=? WHERE id=?',
        (json.dumps({'metric_count': 1, 'guidance_count': 0, 'finding_count': 0,
                     'warnings': warnings + data['limitations']}), 'current'))
    result = earnings_queries.summary(ctx['ledger'], 'current')
    assert all(warning in result['warnings'] for warning in warnings)
