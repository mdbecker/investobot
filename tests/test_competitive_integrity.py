"""Offline integrity, read isolation and precision checks for peer research."""

import copy
import json
import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest

from invest.ledger import Ledger
from invest.models import DomainError


def package():
    return json.loads((Path(__file__).parent / 'fixtures/competitive.json').read_text())


@pytest.fixture
def ctx(tmp_path):
    path = tmp_path / 'competitive.db'
    db = Ledger(path)
    yield {'db': db, 'path': path, 'payload': package()}
    db.connection.close()


def accept(ctx, payload=None):
    from invest.competitive import import_research
    result = import_research(ctx['db'], payload or ctx['payload'], yes=True)
    return result.get('run_id', result.get('research_run_id'))


def test_transaction_rolls_back_all_four_child_tables(ctx):
    from invest.competitive import import_research
    accept(ctx)
    conn = ctx['db'].connection
    tables = ['research_runs', 'research_sources', 'research_competitive_entities',
              'research_competitive_overlaps', 'research_competitive_findings',
              'research_competitive_metrics']
    before = {table: conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
              for table in tables}
    with conn:
        conn.execute("CREATE TRIGGER refuse_metric BEFORE INSERT ON research_competitive_metrics "
                     "BEGIN SELECT RAISE(ABORT,'synthetic metric failure'); END")
    revised = copy.deepcopy(ctx['payload'])
    revised['limitations'].append('A separate immutable observation.')
    with pytest.raises(sqlite3.IntegrityError):
        import_research(ctx['db'], revised, yes=True)
    assert before == {table: conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
                      for table in tables}
    assert conn.execute('PRAGMA foreign_key_check').fetchall() == []


def test_source_foreign_keys_do_not_cross_runs(ctx):
    first = accept(ctx)
    revised = copy.deepcopy(ctx['payload'])
    for source in revised['sources']:
        source['id'] = 'new-' + source['id']
    for peer in revised['peers']:
        peer['selection_source_id'] = 'new-' + peer['selection_source_id']
    for overlap in revised['overlaps']:
        for key in ['subject_source_id', 'peer_source_id']:
            overlap[key] = 'new-' + overlap[key]
    for finding in revised['findings']:
        finding['source_id'] = 'new-' + finding['source_id']
        finding['corroborating_source_ids'] = ['new-' + s for s in finding['corroborating_source_ids']]
    for metric in revised['metrics']:
        metric['source_id'] = 'new-' + metric['source_id']
    second = accept(ctx, revised)
    assert first != second
    conn = ctx['db'].connection
    with pytest.raises(sqlite3.IntegrityError), conn:
        conn.execute('UPDATE research_competitive_metrics SET source_id=? WHERE run_id=?',
                     ('new-a-financials', first))
    assert conn.execute('PRAGMA foreign_key_check').fetchall() == []


def test_compact_queries_never_select_saved_package(ctx):
    from invest.competitive_queries import list_runs, matrix, summary
    run = accept(ctx)
    queries = []
    ctx['db'].connection.set_trace_callback(queries.append)
    assert list_runs(ctx['db'])['runs']
    assert summary(ctx['db'], run)
    assert matrix(ctx['db'], run)['rows']
    ctx['db'].connection.set_trace_callback(None)
    selections = [query.lower() for query in queries if query.lstrip().lower().startswith('select')]
    assert selections
    assert not any('package_json' in query or 'select *' in query for query in selections)


def test_preview_and_every_query_leave_database_bytes_unchanged(ctx):
    from invest.competitive import import_research
    from invest.competitive_queries import list_runs, matrix, show, summary
    run = accept(ctx)
    before = ctx['path'].read_bytes()
    assert import_research(ctx['db'], ctx['payload'])['committed'] is False
    for query in [show, summary, matrix]:
        assert query(ctx['db'], run)
    assert list_runs(ctx['db'])['runs']
    assert ctx['path'].read_bytes() == before


def test_schema_seven_rejects_six_without_touching_files(tmp_path):
    path = tmp_path / 'old.db'
    with sqlite3.connect(path) as conn:
        conn.execute('PRAGMA user_version=6')
        conn.execute('CREATE TABLE sentinel(value TEXT)')
        conn.execute("INSERT INTO sentinel VALUES ('keep')")
    before = path.read_bytes()
    with pytest.raises(DomainError) as error:
        Ledger(path)
    assert error.value.code == 3
    assert path.read_bytes() == before


def test_existing_saved_plan_and_financial_fingerprint_remain_current(ctx):
    from test_account_planning import setup

    from invest.market import MarketClient
    from invest.plan_storage import load_plan
    from invest.plans import generate
    from invest.targets import save
    portfolio = {'ledger': ctx['db']}
    setup(portfolio, 'TAX_FREE')
    target = save(ctx['db'], portfolio['payload'])
    client = MarketClient(ctx['db'], fixture_path=Path('tests/fixtures/fmp-synthetic.json'))
    plan = generate(ctx['db'], client, target['id'], as_of='2026-10-08')
    before_plan = load_plan(ctx['db'], plan['id'])
    before = ctx['db'].planning_state()
    accept(ctx)
    assert ctx['db'].planning_state() == before
    assert load_plan(ctx['db'], plan['id']) == before_plan


@pytest.mark.parametrize('contradiction', ['sec_url', 'issuer'])
def test_financial_source_identity_contradictions_reject(contradiction):
    from pydantic import ValidationError

    from invest.competitive_models import CompetitiveResearchInput
    payload = package()
    payload['subject']['cik'] = '0000000001'
    source = payload['sources'][2]
    source['cik'] = '0000000001' if contradiction == 'sec_url' else '0000000002'
    if contradiction == 'sec_url':
        source['url'] = 'https://www.sec.gov/Archives/edgar/data/2/000000000226000001/report.htm'
    with pytest.raises(ValidationError):
        CompetitiveResearchInput.model_validate(payload)


def test_duplicate_strong_company_identity_under_different_peer_ids_rejects():
    from pydantic import ValidationError

    from invest.competitive_models import CompetitiveResearchInput
    payload = package()
    payload['peers'][0]['cik'] = '0000000002'
    payload['peers'].append(dict(payload['peers'][0], entity_id='peer-copy'))
    payload['overlaps'].append(dict(payload['overlaps'][0], id='copy', peer_id='peer-copy'))
    with pytest.raises(ValidationError):
        CompetitiveResearchInput.model_validate(payload)


def test_two_peer_package_preserves_private_disclosure_gap_and_relationship(ctx):
    from invest.competitive_queries import matrix, summary
    payload = ctx['payload']
    payload['sources'].append(dict(payload['sources'][1], id='private-products',
                                   publisher='Fictional Private C', url='https://example.invalid/c'))
    payload['peers'].append(dict(payload['peers'][0], entity_id='peer-c',
                                 name='Fictional Private C', ticker=None,
                                 relationship='ADJACENT_COMPETITOR',
                                 selection_source_id='private-products'))
    payload['overlaps'].append(dict(payload['overlaps'][0], id='private-overlap',
                                    peer_id='peer-c', peer_source_id='private-products',
                                    peer_segment='Private Workflow', overlap_type='PARTIAL'))
    payload['limitations'].append('Private C publishes no revenue.')
    run = accept(ctx)
    result = summary(ctx['db'], run)
    assert 'ADJACENT_COMPETITOR' in json.dumps(result)
    private_rows = matrix(ctx['db'], run, peer='peer-c')['rows']
    assert private_rows and all(row['peer_value'] is None for row in private_rows)
    assert all(row['comparison_status'] == 'NOT_COMPARABLE' for row in private_rows)


def test_trusted_skill_version_and_canonical_content_are_independent(ctx, monkeypatch):
    from invest.research_skills import SUPPORTED_SKILLS, show_skill
    monkeypatch.setitem(SUPPORTED_SKILLS['investobot-competitive'], 'skill_version', '1.0.9')
    run = accept(ctx)
    saved = ctx['db'].connection.execute(
        'SELECT skill_name,skill_version,package_json FROM research_runs WHERE id=?', (run,)).fetchone()
    assert saved[:2] == ('investobot-competitive', '1.0.9')
    assert 'skill_version' not in json.loads(saved[2])
    assert show_skill('investobot-earnings')['skill_version'] == '1.0.0'
    assert show_skill('investobot-political-contributions')['skill_version'] == '1.0.0'


@pytest.mark.parametrize('subject,peer,rounded', [('120', '100', False), ('2', '3', True)])
def test_percentage_division_reports_rounding_honestly(ctx, subject, peer, rounded):
    from invest.competitive_queries import matrix
    ctx['payload']['metrics'][0]['value'] = subject
    ctx['payload']['metrics'][1]['value'] = peer
    run = accept(ctx)
    row = matrix(ctx['db'], run)['rows'][0]
    assert row['comparison_status'] == 'COMPARABLE'
    assert Decimal(row['absolute_difference']) == Decimal(subject) - Decimal(peer)
    warnings = ' '.join(row['warnings']).lower()
    assert ('round' in warnings or 'inexact' in warnings) is rounded


def test_unknown_peer_filter_reports_input_error(ctx):
    from invest.competitive_queries import matrix
    run = accept(ctx)
    with pytest.raises(DomainError) as error:
        matrix(ctx['db'], run, peer='unknown-peer')
    assert error.value.code == 1


def test_tiny_reported_decimals_remain_plain_and_revalidatable(ctx):
    from invest.competitive import import_research
    from invest.competitive_models import CompetitiveResearchInput
    from invest.competitive_queries import show
    ctx['payload']['metrics'][0]['value'] = '0.00000000000000000000000000000100'
    run = accept(ctx)
    saved = show(ctx['db'], run)
    subject_metric = next(m for m in saved['metrics'] if m['entity_id'] == 'subject')
    assert subject_metric['value'] == '0.000000000000000000000000000001'
    original = {k: v for k, v in saved.items() if k in CompetitiveResearchInput.model_fields}
    assert CompetitiveResearchInput.model_validate(original)
    assert import_research(ctx['db'], original, yes=True)['status'] == 'UNCHANGED'


def test_segment_name_whitespace_does_not_break_verified_overlap(ctx):
    from invest.competitive_queries import matrix
    subject, peer = ctx['payload']['metrics']
    subject.update(scope='SEGMENT', segment_name='Cloud   Applications',
                   overlap_id='enterprise-workflow')
    peer.update(scope='SEGMENT', segment_name='Enterprise Services',
                overlap_id='enterprise-workflow')
    run = accept(ctx)
    assert matrix(ctx['db'], run)['rows'][0]['comparison_status'] == 'COMPARABLE'
