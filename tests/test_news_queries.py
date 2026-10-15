"""Fictional relational snapshots exercise conservative news deltas."""
import json
import sqlite3
from types import SimpleNamespace

import pytest
from pytest_bdd import given, scenarios, then, when

from invest import news_queries as queries
from invest.models import DomainError


@pytest.fixture
def ledger():
    connection = sqlite3.connect(':memory:')
    connection.executescript('''
    CREATE TABLE research_runs(id TEXT, research_type TEXT, skill_name TEXT,
    skill_version TEXT, schema_version TEXT, company_name TEXT, ticker TEXT,
    security_id TEXT, cik TEXT, fiscal_year INTEGER, fiscal_period TEXT, period_end TEXT,
    researched_as_of TEXT, imported_at TEXT, coverage_status TEXT, summary_json TEXT,
    package_json TEXT);
    CREATE TABLE research_sources(run_id TEXT,source_id TEXT,source_type TEXT,
    publisher TEXT,url TEXT,accession_number TEXT,filed_at TEXT,accessed_at TEXT,
    cik TEXT,accepted_at TEXT,is_amendment INTEGER,is_restatement INTEGER,
    original_accession_number TEXT,published_at TEXT,source_locator TEXT);
    CREATE TABLE research_news_scopes(run_id TEXT,window_start TEXT,window_end TEXT,
    coverage_status TEXT,searched_source_types_json TEXT,coverage_notes TEXT);
    CREATE TABLE research_news_events(run_id TEXT,event_key TEXT,title TEXT,category TEXT,
    event_date TEXT,date_status TEXT,event_status TEXT,affected_segments_json TEXT,
    primary_source_id TEXT,source_ids_json TEXT,implications_json TEXT,
    follow_up_questions_json TEXT,material_fingerprint TEXT,
    status_source_id TEXT,status_source_locator TEXT);
    CREATE TABLE research_news_facts(run_id TEXT,event_key TEXT,fact_key TEXT,
    statement TEXT,verification_status TEXT,source_id TEXT,source_locator TEXT);
    CREATE TABLE research_news_catalysts(run_id TEXT,catalyst_id TEXT,title TEXT,
    related_event_key TEXT,scheduled_date TEXT,date_status TEXT,status TEXT,
    source_id TEXT,source_locator TEXT,qualifiers TEXT);
    CREATE TABLE research_news_theses(run_id TEXT,thesis_id TEXT,statement TEXT,
    assessment TEXT,rationale TEXT,uncertainty TEXT,related_event_keys_json TEXT);
    ''')
    yield SimpleNamespace(connection=connection)
    connection.close()


def save(ledger, run, day='2026-10-02', *, ticker='FAKE', cik='0000000001',
         facts=None, event=True, sources=('s1',), status='ANNOUNCED',
         catalyst='EXPECTED', assessment='INSUFFICIENT_EVIDENCE',
         statement='Demand is growing.', title='Product release', question='OPEN'):
    db = ledger.connection
    db.execute('INSERT INTO research_runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
               (run, 'NEWS_CATALYSTS_THESIS_CHANGES', 'investobot-news', '1.0.0', '1.0',
                'Fictional Company', ticker, None, cik, None, None, day, day,
                day + 'T12:00:00+00:00', 'PARTIAL', '{}', '{"company":{"name":"Fictional Company"}}'))
    db.execute('INSERT INTO research_news_scopes VALUES (?,?,?,?,?,?)',
               (run, day, day, 'PARTIAL', '["ISSUER_RELEASE"]', 'Selected sources only.'))
    for source in sources:
        db.execute('INSERT INTO research_sources VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                   (run, source, 'ISSUER_RELEASE', 'Fictional Company',
                    'https://example.invalid/' + source, None, None, day, None, None,
                    0, 0, None, day, 'Release paragraph'))
    if event:
        db.execute('INSERT INTO research_news_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                   (run, 'launch', title, 'PRODUCT', '2026-09-30', 'CONFIRMED', status,
                    '["Enterprise"]', sources[0], json.dumps(list(sources)), '[]',
                    json.dumps([{'id': 'uptake', 'question': 'Has adoption been disclosed?',
                                 'status': question}]), 'internally-generated', None, None))
        for key, text, verification in facts or [('announced', 'Launch announced.', 'VERIFIED')]:
            db.execute('INSERT INTO research_news_facts VALUES (?,?,?,?,?,?,?)',
                       (run, 'launch', key, text, verification, sources[0], 'Paragraph one'))
        db.execute('INSERT INTO research_news_catalysts VALUES (?,?,?,?,?,?,?,?,?,?)',
                   (run, 'availability', 'Availability', 'launch',
                    '2026-11-01' if catalyst == 'EXPECTED' else '2026-12-01',
                    'EXPECTED', catalyst, sources[0], 'Paragraph two', 'Timing uncertain.'))
        db.execute('INSERT INTO research_news_theses VALUES (?,?,?,?,?,?,?)',
                   (run, 'demand', statement, assessment, 'Evidence reviewed.',
                    'Uptake unknown.', '["launch"]'))
    db.commit()


def test_warning_counts_are_part_of_delta_and_missing_baseline(ledger):
    save(ledger, 'old')
    save(ledger, 'new', '2026-10-03')
    result = queries.compare(ledger, 'old', 'new')
    assert result['counts']['warnings'] == len(result['warnings'])
    missing = queries.changes(ledger, 'ABSENT')
    assert missing['counts']['warnings'] == len(missing['warnings'])


def test_compact_reads_preserve_scope_citations_and_accepted_research(ledger):
    save(ledger, 'old')
    save(ledger, 'new', '2026-10-03')
    expected_context = queries.context(ledger, 'FAKE')
    expected_delta = queries.compare(ledger, 'old', 'new')
    raw_detail = 'Fictional detailed research notes. ' * 5000
    package = {'company': {'name': 'Fictional Company'}, 'limitations': [raw_detail]}
    for index in range(20):
        save(ledger, f'unrelated-{index:02}', '2026-10-04', ticker='OTHER', cik='0000000002')
    ledger.connection.execute('UPDATE research_runs SET package_json=?', (json.dumps(package),))
    ledger.connection.commit()
    before = tuple(ledger.connection.iterdump())
    # A true read-only boundary, independent of query spelling or access plan.
    ledger.connection.execute('PRAGMA query_only=ON')
    listed = queries.list_runs(ledger, 'FAKE')
    assert [run['research_run_id'] for run in listed['runs']] == ['new', 'old']
    result = queries.context(ledger, 'FAKE')
    assert result == expected_context
    assert result['baseline_available'] is True
    assert result['research_run_id'] == 'new'
    assert result['events'][0]['event_key'] == 'launch'
    assert result['catalysts'][0]['catalyst_id'] == 'availability'
    assert result['theses'][0]['thesis_id'] == 'demand'
    assert result['open_follow_up_questions'][0]['id'] == 'uptake'
    summary = queries.summary(ledger, 'new')
    assert summary['events'][0]['verified_facts'][0]['fact_key'] == 'announced'
    assert queries.compare(ledger, 'old', 'new') == expected_delta
    for compact in (listed, result, expected_delta):
        encoded = json.dumps(compact)
        assert raw_detail not in encoded
        assert len(encoded.encode()) < 128 * 1024
        assert 'unrelated-' not in encoded
    shown = queries.show(ledger, 'old')
    assert shown['skill_name'] == 'investobot-news'
    assert shown['limitations'] == [raw_detail]
    source = result['events'][0]['sources'][0]
    assert (source['run_id'], source['url'], source['published_at'], source['source_locator']) == (
        'new', 'https://example.invalid/s1', '2026-10-03', 'Release paragraph')
    assert tuple(ledger.connection.iterdump()) == before


def test_missing_baseline_and_unknown_runs(ledger):
    assert queries.context(ledger, 'FAKE')['baseline_available'] is False
    assert queries.changes(ledger, 'FAKE')['baseline_available'] is False
    save(ledger, 'only')
    assert queries.changes(ledger, 'FAKE')['baseline_available'] is False
    with pytest.raises(DomainError):
        queries.show(ledger, 'missing')


def test_added_corroboration_and_cosmetic_text_are_not_material(ledger):
    save(ledger, 'old')
    save(ledger, 'new', '2026-10-03', sources=('s1', 's2'),
         facts=[('announced', '  Launch   announced. ', 'VERIFIED')], title='Renamed headline')
    result = queries.compare(ledger, 'old', 'new')
    assert result['new_events'] == []
    assert result['updated_events'] == []
    assert result['new_evidence_only'][0]['event_key'] == 'launch'
    assert result['new_evidence_only'][0]['added_source_ids'] == ['s2']
    assert result['new_evidence_only'][0]['sources'][0]['url'].startswith('https://example.invalid/')


def test_material_updates_have_before_after_evidence_and_stable_ids(ledger):
    save(ledger, 'old')
    save(ledger, 'new', '2026-10-03', sources=('s2',),
         facts=[('announced', 'Launch announced.', 'VERIFIED'),
                ('available', 'Commercial availability confirmed.', 'VERIFIED')],
         catalyst='DELAYED', assessment='MIXED', question='ANSWERED')
    result = queries.compare(ledger, 'old', 'new')
    update = result['updated_events'][0]
    assert 'FACT_ADDED' in update['change_types']
    assert update['added_facts'][0]['fact_key'] == 'available'
    assert update['before']['event_key'] == update['after']['event_key'] == 'launch'
    assert update['sources'][0]['source_id'] == 's2'
    assert result['catalyst_changes'][0]['old_status'] == 'EXPECTED'
    assert result['catalyst_changes'][0]['new_date'] == '2026-12-01'
    assert result['thesis_changes'][0]['new_assessment'] == 'MIXED'
    assert result['follow_up_changes'][0]['old_status'] == 'OPEN'
    assert result['counts']['updated_events'] == 1


def test_absence_never_means_resolution(ledger):
    save(ledger, 'old', status='DEVELOPING')
    save(ledger, 'new', '2026-10-03', event=False)
    result = queries.compare(ledger, 'old', 'new')
    assert len(result['not_reobserved']) == 3
    assert {item['status'] for item in result['not_reobserved']} == {'NOT_REOBSERVED'}
    assert result['updated_events'] == result['catalyst_changes'] == []
    assert result['coverage_comparable'] is False
    assert result['warnings']


def test_disputed_claims_remain_separate_and_not_fact_added(ledger):
    save(ledger, 'old')
    save(ledger, 'new', '2026-10-03', facts=[('announced', 'Launch announced.', 'VERIFIED'),
                                         ('allegation', 'A third party alleges failure.', 'DISPUTED')])
    summary = queries.summary(ledger, 'new')
    assert len(summary['events'][0]['verified_facts']) == 1
    assert summary['events'][0]['disputed_facts'][0]['fact_key'] == 'allegation'
    delta = queries.compare(ledger, 'old', 'new')
    assert delta['updated_events'] == []
    assert any('disputed' in warning.lower() for warning in delta['warnings'])


def test_thesis_statement_change_is_incompatible(ledger):
    save(ledger, 'old')
    save(ledger, 'new', '2026-10-03', statement='Costs are falling.', assessment='SUPPORTED')
    result = queries.compare(ledger, 'old', 'new')
    assert result['thesis_changes'][0]['status'] == 'INCOMPATIBLE'
    assert result['thesis_changes'][0]['before']['statement'] == 'Demand is growing.'


def test_identity_conflicts_refused_and_changes_select_latest_compatible(ledger):
    save(ledger, 'old')
    save(ledger, 'new', '2026-10-03')
    save(ledger, 'unrelated', '2026-10-04', cik='0000000002')
    with pytest.raises(DomainError):
        queries.compare(ledger, 'old', 'unrelated')
    result = queries.changes(ledger, 'FAKE')
    assert result['baseline_available'] is False
    assert result['warnings']


def test_tie_ordering_and_newly_observed_older_event(ledger):
    save(ledger, 'a', event=False)
    save(ledger, 'b')
    result = queries.changes(ledger, 'FAKE')
    assert result['from_run_id'] == 'a'
    assert result['to_run_id'] == 'b'
    assert result['new_events'][0]['observation_status'] == 'PREVIOUSLY_OCCURRING_NEWLY_OBSERVED'



scenarios('features/news_queries.feature')


@given('immutable fictional runs sharing a stable event key and verified facts')
def corroboration_runs(ledger):
    save(ledger, 'old')


@when('another source is added and a headline is renamed', target_fixture='delta')
def corroboration_delta(ledger):
    save(ledger, 'new', '2026-10-03', sources=('s1', 's2'), title='Renamed headline')
    return queries.compare(ledger, 'old', 'new')


@then('the change is new evidence only and retains exact source links')
def corroboration_assertion(delta):
    assert delta['new_events'] == delta['updated_events'] == []
    assert delta['new_evidence_only'][0]['sources'][0]['url'].startswith('https://example.invalid/')


def test_partial_strong_identity_cannot_fall_back_to_ticker(ledger):
    save(ledger, 'old', cik=None)
    save(ledger, 'new', '2026-10-03')
    with pytest.raises(DomainError):
        queries.compare(ledger, 'old', 'new')


def test_context_excludes_full_facts_and_implications_but_summary_retains_them(ledger):
    save(ledger, 'old')
    detail = 'Fictional full-detail evidence, not context.'
    implications = [{'id': 'possible-demand', 'area': 'DEMAND', 'statement': detail,
                     'assumptions': 'Fictional uptake.', 'uncertainty': 'Uptake unknown.'}]
    ledger.connection.execute('UPDATE research_news_facts SET statement=?', (detail,))
    ledger.connection.execute('UPDATE research_news_events SET implications_json=?',
                              (json.dumps(implications),))
    ledger.connection.commit()
    before = tuple(ledger.connection.iterdump())
    result = queries.context(ledger, 'FAKE')
    assert result['baseline_available']
    event, = result['events']
    assert not {'verified_facts', 'disputed_facts', 'implications'} & event.keys()
    assert detail not in json.dumps(result)
    assert 'sources' not in result
    full = queries.summary(ledger, 'old')['events'][0]
    assert full['verified_facts'][0]['statement'] == detail
    assert full['implications'] == implications
    assert tuple(ledger.connection.iterdump()) == before


def test_missing_records_keep_prior_source_links(ledger):
    save(ledger, 'old')
    save(ledger, 'new', '2026-10-03', event=False)
    result = queries.compare(ledger, 'old', 'new')
    for item in result['not_reobserved']:
        assert item['sources'][0]['url'] == 'https://example.invalid/s1'
        assert item['before'] is not None and item['after'] is None


def test_relabeling_same_source_is_not_new_corroboration(ledger):
    save(ledger, 'old', sources=('s1',))
    save(ledger, 'new', '2026-10-03', sources=('renamed',))
    ledger.connection.execute('UPDATE research_sources SET url=? WHERE run_id=?',
                              ('https://example.invalid/s1', 'new'))
    result = queries.compare(ledger, 'old', 'new')
    assert result['updated_events'] == result['new_evidence_only'] == []
