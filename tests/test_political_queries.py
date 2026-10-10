import copy
import json
import sqlite3
from types import SimpleNamespace

import pytest
from pytest_bdd import given, scenarios, then, when

from invest import political_queries
from invest.models import DomainError

scenarios('features/political_queries.feature')


@pytest.fixture
def ctx():
    connection = sqlite3.connect(':memory:')
    connection.execute('''CREATE TABLE research_political_runs (
        id TEXT PRIMARY KEY, company_name TEXT, ticker TEXT, security_id TEXT,
        jurisdiction TEXT, period_start TEXT, period_end TEXT, researched_as_of TEXT,
        imported_at TEXT, coverage_status TEXT, rights_status TEXT, package_json TEXT)''')
    yield {'ledger': SimpleNamespace(connection=connection)}
    connection.close()


def store(ctx, package, identity='run-1'):
    ctx['ledger'].connection.execute(
        'INSERT INTO research_political_runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
        (identity, package['company']['name'], package['company']['ticker'], None,
         'US_FEDERAL', '2024-01-01', '2026-10-09', '2026-10-09',
         '2026-10-10T12:00:00+00:00', 'PARTIAL', 'APPROVED', json.dumps(package)))


@given('fictional immutable political research with a donation refund and memo')
def research(ctx):
    package = {
        'schema_version': '1.0', 'research_type': 'EXECUTIVE_POLITICAL_CONTRIBUTIONS',
        'company': {'name': 'Fictional Corporation', 'ticker': 'FICTION', 'security_id': None},
        'scope': {'period_start': '2024-01-01', 'period_end': '2026-10-09',
                  'coverage_status': 'PARTIAL', 'rights_status': 'APPROVED'},
        'sources': [{'id': 'source-1', 'url': 'https://example.invalid/evidence'}],
        'executives': [{'id': 'officer-1', 'full_name': 'Fictional Officer', 'role': 'CEO'}],
        'recipients': [{'id': 'pac-1', 'name': 'Fictional PAC', 'recipient_type': 'PAC',
                        'recipient_party': 'UNKNOWN', 'candidate_id': None}],
        'contributions': [], 'unresolved_matches': [{'executive_id': 'officer-1'}],
        'limitations': ['Synthetic incomplete reporting period.'],
    }
    for identity, amount, kind, countable in (
        ('donation', '1000.00', 'CONTRIBUTION', True),
        ('refund', '-125.00', 'REFUND', True), ('memo', '1000.00', 'MEMO', False),
        ('conduit', '1000.00', 'CONTRIBUTION', False),
    ):
        transaction = {'id': identity, 'executive_id': 'officer-1', 'recipient_id': 'pac-1',
                       'amount_usd': amount, 'transaction_kind': kind, 'countable': countable,
                       'source_ids': ['source-1']}
        if kind == 'REFUND':
            transaction['original_contribution_id'] = 'donation'
        package['contributions'].append(transaction)
    ctx['package'] = package
    store(ctx, package)


@when('the research summary is requested')
def summarize(ctx):
    ctx['result'] = political_queries.summary(ctx['ledger'], 'run-1')


@then('the PAC totals net the linked refund and preserve transaction evidence')
def totals(ctx):
    result = ctx['result']
    assert result['totals_by_recipient_party']['UNKNOWN'] == '875.00'
    assert result['totals_by_recipient_type']['PAC'] == '875.00'
    assert result['totals_by_recipient_party']['DEMOCRATIC'] == '0'
    assert result['verified_transactions'] == 4
    assert result['executives_reviewed'] == 1
    assert result['unresolved_match_count'] == 1
    assert 'Synthetic incomplete reporting period.' in result['warnings']
    group = result['contributions_by_executive'][0]
    assert group['executive_id'] == 'officer-1'
    assert group['transactions'] == ctx['package']['contributions']
    assert result['contributions_by_recipient'][0]['recipient_id'] == 'pac-1'


@then('no donor political affiliation is inferred')
def affiliations(ctx):
    executive = ctx['result']['contributions_by_executive'][0]
    assert 'party' not in executive
    assert 'political_affiliation' not in executive
    assert ctx['result']['contributions_by_recipient'][0]['recipient_type'] == 'PAC'


@when('the full research package is requested')
def show(ctx):
    ctx['result'] = political_queries.show(ctx['ledger'], 'run-1')


@then('the accepted package is reproduced with its import provenance')
def reproduction(ctx):
    expected = copy.deepcopy(ctx['package'])
    expected.update(research_run_id='run-1', imported_at='2026-10-10T12:00:00+00:00')
    assert ctx['result'] == expected


@when('matching research runs are listed')
def listing(ctx):
    ctx['queries'] = []
    ctx['ledger'].connection.set_trace_callback(ctx['queries'].append)
    ctx['result'] = political_queries.list_runs(ctx['ledger'], ticker='fiction')


@then('only compact matching run metadata is read')
def compact(ctx):
    assert len(ctx['result']['runs']) == 1
    assert ctx['result']['runs'][0]['research_run_id'] == 'run-1'
    assert 'package_json' not in ' '.join(ctx['queries']).lower()
    assert 'sources' not in ctx['result']['runs'][0]
    assert political_queries.list_runs(ctx['ledger'], ticker='OTHER') == {'runs': []}


@pytest.mark.parametrize('query', [political_queries.show, political_queries.summary])
def test_missing_run_is_input_error(ctx, query):
    with pytest.raises(DomainError) as error:
        query(ctx['ledger'], 'missing')
    assert error.value.code == 1


def test_decimal_summation_is_lossless_beyond_default_precision(ctx):
    research(ctx)
    package = ctx['package']
    package['contributions'][0]['amount_usd'] = '123456789012345678901234567890.01'
    package['contributions'][1]['amount_usd'] = '-0.01'
    store(ctx, package, 'precise')
    result = political_queries.summary(ctx['ledger'], 'precise')
    assert result['totals_by_recipient_type']['PAC'] == '123456789012345678901234567890.00'


def test_empty_research_has_zero_categories_and_no_claim_of_no_donations(ctx):
    research(ctx)
    package = ctx['package']
    package['contributions'] = []
    store(ctx, package, 'empty')
    result = political_queries.summary(ctx['ledger'], 'empty')
    assert set(result['totals_by_recipient_party'].values()) == {'0'}
    assert result['verified_transactions'] == 0
    assert result['warnings']
