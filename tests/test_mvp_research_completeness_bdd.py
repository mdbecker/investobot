"""Real offline research acceptance: task scope, chronology and bounded reads."""

import json

import pytest
from pytest_bdd import given, scenarios, then, when

from invest.analytics_store import snapshot
from invest.ledger import Ledger
from invest.research_portfolio import plan, report
from invest.research_storage import import_run

scenarios('features/mvp/research_completeness.feature')

SKILLS = {'investobot-news', 'investobot-earnings', 'investobot-competitive',
          'investobot-management-insiders', 'investobot-political-contributions'}


@pytest.fixture
def context(tmp_path):
    ledger = Ledger(tmp_path / 'synthetic-research.db')
    yield {'ledger': ledger}
    ledger.connection.close()


def news_package(*, cik, name, researched_as_of, window_start, event_date):
    """Original fictional primary-source evidence accepted by the strict news model."""
    return {
        'schema_version': '1.0', 'research_type': 'NEWS_CATALYSTS_THESIS_CHANGES',
        'company': {'name': name, 'ticker': None, 'cik': cik, 'security_id': None},
        'scope': {'window_start': window_start, 'window_end': researched_as_of,
                  'researched_as_of': researched_as_of,
                  'coverage_status': 'COMPLETE_WITHIN_DECLARED_SCOPE',
                  'searched_source_types': ['ISSUER_RELEASE'],
                  'coverage_notes': 'Complete only within the declared fictional release scope.'},
        'sources': [{'id': 'fictional-release', 'source_type': 'ISSUER_RELEASE',
                     'publisher': name, 'url': f'https://example.invalid/{cik}/release',
                     'published_at': event_date, 'accessed_at': researched_as_of,
                     'source_locator': 'Opening paragraph'}],
        'events': [{'event_key': 'fictional-factory-opened-' + cik, 'title': 'Fictional factory opened',
                    'category': 'OPERATIONS', 'event_date': event_date,
                    'date_status': 'CONFIRMED', 'event_status': 'CONFIRMED',
                    'affected_segments': [], 'primary_source_id': 'fictional-release',
                    'source_ids': ['fictional-release'],
                    'facts': [{'fact_key': 'opened', 'statement': 'The fictional factory opened.',
                               'source_id': 'fictional-release', 'source_locator': 'Opening paragraph',
                               'verification_status': 'VERIFIED'}],
                    'implications': [], 'follow_up_questions': []}],
        'catalysts': [], 'theses': [], 'limitations': ['Entirely fictional offline evidence.']}


def accept_news(ctx, *, cik='0000123456', name='Fictional Selected Company',
                researched_as_of='2026-10-10', window_start='2026-10-01',
                event_date='2026-10-06'):
    package = news_package(cik=cik, name=name, researched_as_of=researched_as_of,
                           window_start=window_start, event_date=event_date)
    accepted = import_run(ctx['ledger'], {'kind': 'NEWS', 'issuer_id': 'CIK:' + cik,
        'as_of': researched_as_of, 'data_environment': 'SYNTHETIC',
        'skill_name': 'investobot-news', 'package': package}, confirmed=True)
    assert accepted['committed'] is True
    return accepted['run_id']


@given('a frozen synthetic issuer queue requiring five specialty skills')
def frozen(context):
    universe = {'manifest_id': 'selected-issuer-universe', 'as_of': '2026-10-10',
        'data_environment': 'SYNTHETIC', 'requested_top': 1,
        'issuers': [{'issuer_id': 'CIK:0000123456', 'exposure_weight': '1',
                    'identity': {'cik': '0000123456', 'name': 'Fictional Selected Company'}}],
        'coverage': {'household_total_value': '1000', 'unknown_exposure_value': '0',
                     'filtered_exposure_value': '0', 'unresolved_issuer_value': '0'}}
    accepted = snapshot(context['ledger'], {'id': universe['manifest_id'],
        'purpose': 'RESEARCH_UNIVERSE', 'data_environment': 'SYNTHETIC', 'artifacts': [],
        'metadata': {'universe': universe}}, confirm=True)
    assert accepted['committed'] is True
    context['plan'] = plan(context['ledger'], universe['manifest_id'],
                           window_start='2026-10-01', window_end='2026-10-10')
    assert set(context['plan']['skills']) == SKILLS
    context['financial_before'] = context['ledger'].planning_state()


@given('complete accepted news evidence for the selected issuer')
def current_news(context):
    context['selected_run_id'] = accept_news(context)


@given('complete accepted news evidence predating the requested window')
def historical_news(context):
    context['selected_run_id'] = accept_news(context, researched_as_of='2026-09-01',
                                            window_start='2026-08-01', event_date='2026-08-31')


@given('corrupted accepted research for an unrelated issuer')
def unrelated(context):
    run_id = accept_news(context, cik='0000654321', name='Fictional Unrelated Company')
    connection = context['ledger'].connection
    metadata = json.loads(connection.execute("SELECT metadata_json FROM research_artifacts "
        "WHERE run_id=? AND id='envelope'", (run_id,)).fetchone()[0])
    metadata['envelope']['package']['events'][0]['title'] = 'Corrupted unrelated evidence'
    with connection:
        connection.execute("UPDATE research_artifacts SET metadata_json=? "
                           "WHERE run_id=? AND id='envelope'", (json.dumps(metadata), run_id))
    context['unrelated_run_id'] = run_id


@when('the selected portfolio research plan is reported')
def reported(context):
    context['result'] = report(context['ledger'], context['plan']['id'])
    assert context['ledger'].planning_state() == context['financial_before']


@then('news coverage is complete while four specialties remain not researched')
def specialty_coverage(context):
    result = context['result']
    company = result['companies'][0]
    assert company['status'] == 'PARTIAL'
    assert set(company['specialty_statuses']) == SKILLS
    assert company['specialty_statuses']['investobot-news'] == 'AVAILABLE'
    assert all(company['specialty_statuses'][name] == 'NOT_RESEARCHED'
               for name in SKILLS - {'investobot-news'})
    assert set(result['coverage']['specialties']) == SKILLS
    for name, coverage in result['coverage']['specialties'].items():
        assert coverage['requested_issuers'] == 1
        assert coverage['researched_issuers'] == (1 if name == 'investobot-news' else 0)
        assert coverage['researched_weight'] == ('1' if name == 'investobot-news' else '0')
        assert coverage['complete'] is (name == 'investobot-news')


@then('selected and whole portfolio research remain incomplete')
def incomplete(context):
    result = context['result']
    assert result['status'] == 'PARTIAL'
    assert result['coverage']['researched_issuers'] == 1
    assert result['coverage']['selected_research_complete'] is False
    assert result['coverage']['whole_portfolio_research_complete'] is False


@then('current news coverage is unavailable with explicit historical context')
def old_scope(context):
    result = context['result']
    assert result['coverage']['researched_issuers'] == 0
    assert result['coverage']['researched_weight'] == '0'
    company = result['companies'][0]
    assert company['status'] == 'REVIEW_REQUIRED'
    assert company['specialty_statuses']['investobot-news'] == 'REVIEW_REQUIRED'
    assert any(issue['code'] == 'RESEARCH_WINDOW_NOT_COVERED' and
               context['selected_run_id'] in issue['affected_ids'] for issue in result['issues'])
    assert company['events'][0]['observation_status'] == 'NOT_REOBSERVED'
    assert company['events'][0]['event_date'] == '2026-08-31'
    assert company['events'][0]['source_ids'] == ['fictional-release']
    assert result['coverage']['selected_research_complete'] is False


@then('selected issuer source evidence is returned independently')
def isolated(context):
    result = context['result']
    assert result['coverage']['requested_issuers'] == 1
    assert result['coverage']['researched_issuers'] == 1
    assert result['companies'][0]['run_hashes'] == [context['selected_run_id']]
    assert result['companies'][0]['events'][0]['source_ids'] == ['fictional-release']
    assert context['unrelated_run_id'] not in json.dumps(result)
