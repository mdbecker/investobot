import copy
import json
import sqlite3

import pytest
from pytest_bdd import given, scenarios, then, when

from invest.ledger import Ledger
from invest.models import DomainError

scenarios('features/news_storage.feature')


def news_package():
    return {
        'schema_version': '1.0', 'research_type': 'NEWS_CATALYSTS_THESIS_CHANGES',
        'company': {'name': 'Fictional Corporation', 'ticker': 'FAKE', 'cik': None,
                    'security_id': None},
        'scope': {'window_start': '2026-10-01', 'window_end': '2026-10-10',
                  'researched_as_of': '2026-10-10', 'coverage_status': 'PARTIAL',
                  'searched_source_types': ['ISSUER_RELEASE'],
                  'coverage_notes': 'Fictional selected releases only.'},
        'sources': [{'id': 'release', 'source_type': 'ISSUER_RELEASE',
                     'publisher': 'Fictional Corporation',
                     'url': 'https://example.invalid/announcement?record_id=public&token=secret',
                     'published_at': '2026-10-06', 'accessed_at': '2026-10-10',
                     'source_locator': 'Opening paragraph'}],
        'events': [{'event_key': 'product-release', 'title': 'Fictional launch',
                    'category': 'PRODUCT', 'event_date': '2026-10-06',
                    'date_status': 'CONFIRMED', 'event_status': 'ANNOUNCED',
                    'affected_segments': ['Enterprise'], 'primary_source_id': 'release',
                    'source_ids': ['release'],
                    'facts': [{'fact_key': 'announced', 'statement': 'Company announced a product.',
                               'source_id': 'release', 'source_locator': 'Opening paragraph',
                               'verification_status': 'VERIFIED'}],
                    'implications': [], 'follow_up_questions': []}],
        'catalysts': [], 'theses': [], 'limitations': ['Entirely fictional.'],
    }


@pytest.fixture
def ctx(tmp_path):
    path = tmp_path / 'news.db'
    db = Ledger(path)
    yield {'db': db, 'path': path, 'payload': news_package()}
    db.connection.close()


@given('a fictional news package and fresh ledger')
def initial(ctx):
    ctx['financial'] = ctx['db'].planning_state()


@when('the package is previewed then explicitly accepted twice')
def accept(ctx):
    from invest.news import import_research
    before = ctx['path'].read_bytes()
    ctx['preview'] = import_research(ctx['db'], ctx['payload'])
    assert before == ctx['path'].read_bytes()
    ctx['first'] = import_research(ctx['db'], ctx['payload'], yes=True)
    reordered = copy.deepcopy(ctx['payload'])
    reordered['events'][0]['source_ids'].reverse()
    ctx['second'] = import_research(ctx['db'], dict(reversed(list(reordered.items()))), yes=True)


@then('preview changes no bytes and one immutable run preserves financial state')
def isolated(ctx):
    assert ctx['preview']['status'] == 'PREVIEW' and not ctx['preview']['committed']
    assert ctx['first']['committed'] and ctx['second']['status'] == 'UNCHANGED'
    assert ctx['first']['research_run_id'] == ctx['second']['research_run_id']
    conn = ctx['db'].connection
    assert conn.execute('SELECT COUNT(*) FROM research_news_events').fetchone()[0] == 1
    assert conn.execute('SELECT COUNT(*) FROM research_news_facts').fetchone()[0] == 1
    assert conn.execute('SELECT skill_name,skill_version FROM research_runs').fetchone() == ('investobot-news', '1.0.1')
    assert conn.execute('PRAGMA foreign_key_check').fetchall() == []
    assert ctx['db'].planning_state() == ctx['financial']


def test_schema_six_rejects_five_without_deletion(tmp_path):
    db = Ledger(tmp_path / 'fresh.db')
    assert db.connection.execute('PRAGMA user_version').fetchone()[0] == 1
    db.connection.close()
    old = tmp_path / 'old.db'
    with sqlite3.connect(old) as conn:
        conn.execute('PRAGMA user_version=5')
        conn.execute('CREATE TABLE sentinel (id TEXT)')
    before = old.read_bytes()
    with pytest.raises(DomainError) as error:
        Ledger(old)
    assert error.value.code == 3 and before == old.read_bytes()


def test_rollback_and_run_scoped_references(ctx):
    from invest.news import import_research
    conn = ctx['db'].connection
    first = import_research(ctx['db'], ctx['payload'], yes=True)
    with conn:
        conn.execute("CREATE TRIGGER refuse_news BEFORE INSERT ON research_news_facts BEGIN SELECT RAISE(ABORT,'fictional failure'); END")
    second = copy.deepcopy(ctx['payload'])
    second['limitations'].append('Second observation')
    with pytest.raises(sqlite3.IntegrityError):
        import_research(ctx['db'], second, yes=True)
    assert conn.execute('SELECT COUNT(*) FROM research_runs').fetchone()[0] == 1
    assert conn.execute('SELECT COUNT(*) FROM research_sources').fetchone()[0] == 1
    with pytest.raises(sqlite3.IntegrityError), conn:
        conn.execute('UPDATE research_news_facts SET source_id=? WHERE run_id=?',
                     ('another-run-source', first['research_run_id']))


def test_cross_company_event_key_reuse_rejects_atomically(ctx):
    from invest.news import import_research
    import_research(ctx['db'], ctx['payload'], yes=True)
    other = copy.deepcopy(ctx['payload'])
    other['company'].update(name='Unrelated Fictional Corporation', ticker='OTHER')
    with pytest.raises(DomainError):
        import_research(ctx['db'], other, yes=True)
    assert ctx['db'].connection.execute('SELECT COUNT(*) FROM research_runs').fetchone()[0] == 1


def test_package_contains_no_agent_selected_provenance_or_fingerprint(ctx):
    from invest.news import import_research
    result = import_research(ctx['db'], ctx['payload'], yes=True)
    package = json.loads(ctx['db'].connection.execute(
        'SELECT package_json FROM research_runs WHERE id=?', (result['research_run_id'],)).fetchone()[0])
    assert 'skill_version' not in package and 'material_fingerprint' not in package['events'][0]


def test_resolution_locator_survives_summary_and_comparison(ctx):
    from invest.news import import_research
    from invest.news_queries import compare, summary
    first = import_research(ctx['db'], ctx['payload'], yes=True)['research_run_id']
    updated = copy.deepcopy(ctx['payload'])
    updated['events'][0].update(event_status='RESOLVED', status_source_id='release',
                                status_source_locator='Explicit outcome paragraph')
    second = import_research(ctx['db'], updated, yes=True)['research_run_id']
    assert summary(ctx['db'], second)['events'][0]['status_source_locator'] == 'Explicit outcome paragraph'
    delta = compare(ctx['db'], first, second)
    assert delta['updated_events'][0]['after']['status_source_locator'] == 'Explicit outcome paragraph'


def test_news_skill_version_is_pinned_independently(ctx, monkeypatch):
    from invest.news import import_research
    from invest.research_skills import SUPPORTED_SKILLS, show_skill
    monkeypatch.setitem(SUPPORTED_SKILLS['investobot-news'], 'skill_version', '1.0.1')
    assert show_skill('investobot-news')['skill_version'] == '1.0.1'
    run = import_research(ctx['db'], ctx['payload'], yes=True)['research_run_id']
    assert ctx['db'].connection.execute('SELECT skill_version FROM research_runs WHERE id=?',
                                       (run,)).fetchone()[0] == '1.0.1'
    assert show_skill('investobot-earnings')['skill_version'] == '1.0.0'
    assert show_skill('investobot-political-contributions')['skill_version'] == '1.0.0'


def test_nested_collection_reordering_is_content_idempotent(ctx):
    from invest.news import import_research
    data = ctx['payload']
    data['sources'].append(dict(data['sources'][0], id='independent',
                                url='https://example.invalid/independent'))
    event = data['events'][0]
    event['source_ids'].append('independent')
    event['affected_segments'].append('Other verified segment')
    event['facts'].append(dict(event['facts'][0], fact_key='second-fact',
                               statement='A separately attributed fictional fact.',
                               source_id='independent'))
    first = import_research(ctx['db'], data, yes=True)
    reordered = copy.deepcopy(data)
    for key in ('sources', 'events', 'catalysts', 'theses', 'limitations'):
        reordered[key].reverse()
    for key in ('facts', 'source_ids', 'affected_segments', 'implications', 'follow_up_questions'):
        reordered['events'][0][key].reverse()
    second = import_research(ctx['db'], reordered, yes=True)
    assert first['research_run_id'] == second['research_run_id']
    assert second['status'] == 'UNCHANGED'


def test_identical_unregistered_company_without_ticker_is_still_idempotent(ctx):
    from invest.news import import_research
    ctx['payload']['company']['ticker'] = None
    first = import_research(ctx['db'], ctx['payload'], yes=True)
    second = import_research(ctx['db'], ctx['payload'], yes=True)
    assert first['research_run_id'] == second['research_run_id']
    assert second['status'] == 'UNCHANGED'


def test_skill_instruction_update_preserves_accepted_hash_and_noop(ctx, monkeypatch):
    from invest.news import import_research
    from invest.research_skills import SUPPORTED_SKILLS
    ctx['payload']['company']['ticker'] = None
    monkeypatch.setitem(SUPPORTED_SKILLS['investobot-news'], 'skill_version', '1.0.0')
    first = import_research(ctx['db'], ctx['payload'], yes=True)
    monkeypatch.setitem(SUPPORTED_SKILLS['investobot-news'], 'skill_version', '1.0.1')
    second = import_research(ctx['db'], ctx['payload'], yes=True)
    assert second['status'] == 'UNCHANGED'
    assert second['research_run_id'] == first['research_run_id']
    assert ctx['db'].connection.execute('SELECT skill_version FROM research_runs').fetchall() == [('1.0.0',)]


def test_old_skill_package_validates_after_reordering_without_ticker(ctx, monkeypatch):
    from typer.testing import CliRunner

    from invest.cli import app
    from invest.news import import_research
    from invest.research_skills import SUPPORTED_SKILLS
    data = ctx['payload']
    data['company']['ticker'] = None
    data['sources'].append(dict(data['sources'][0], id='a-second',
                               url='https://example.invalid/second'))
    monkeypatch.setitem(SUPPORTED_SKILLS['investobot-news'], 'skill_version', '1.0.0')
    import_research(ctx['db'], data, yes=True)
    monkeypatch.setitem(SUPPORTED_SKILLS['investobot-news'], 'skill_version', '1.0.1')
    monkeypatch.setenv('INVEST_DB', str(ctx['path']))
    file = ctx['path'].parent / 'reordered.json'
    file.write_text(json.dumps(data))
    before = ctx['path'].read_bytes()
    result = CliRunner().invoke(app, ['research', 'news', 'validate', str(file)])
    assert result.exit_code == 0, result.stderr
    assert before == ctx['path'].read_bytes()
