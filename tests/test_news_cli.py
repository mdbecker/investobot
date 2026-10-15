import copy
import json

import pytest
from pytest_bdd import given, scenarios, then, when
from test_news_storage import news_package
from typer.testing import CliRunner

from invest.cli import app

scenarios('features/news_cli.feature')


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    path = tmp_path / 'ledger.db'
    monkeypatch.setenv('INVEST_DB', str(path))
    return {'path': path, 'file': tmp_path / 'news.json', 'runner': CliRunner(),
            'payload': news_package()}


def invoke(ctx, args, code=0):
    result = ctx['runner'].invoke(app, ['research', 'news', *args])
    assert result.exit_code == code, result.stderr
    if code:
        assert not result.stdout
    return json.loads(result.stdout if not code else result.stderr)


@given('a selected missing ledger and fictional news input')
def input_file(ctx):
    ctx['file'].write_text(json.dumps(ctx['payload']))


@when('news is validated previewed and its baseline requested')
def preview(ctx):
    assert invoke(ctx, ['validate', str(ctx['file'])])['valid']
    assert not invoke(ctx, ['import', str(ctx['file'])])['committed']
    assert not invoke(ctx, ['context', '--ticker', 'FAKE'])['baseline_available']
    assert invoke(ctx, ['list'])['runs'] == []
    assert invoke(ctx, ['changes', '--ticker', 'FAKE'])['baseline_available'] is False


@then('no database is created')
def absent(ctx):
    assert not ctx['path'].exists()


@when('three fictional observations are explicitly accepted')
def three_runs(ctx):
    from planning_fixtures import saved_proposal
    from test_storage_stabilization import snapshot

    from invest.ledger import Ledger
    from invest.market import MarketClient
    from invest.plans import show
    from invest.targets import save
    db = Ledger(ctx['path'])
    db.apply(snapshot(10, 'fictional-original', '2026-10-08'))
    security = db.resolve('SYN')['id']
    target = save(db, {'name': 'Fictional allocation',
        'target_allocations': {security: '.5', 'CASH': '.5'},
        'planning_constraints': {'eligible_accounts': ['ira']}})
    plan = saved_proposal(db, MarketClient(db, fixture_path='tests/fixtures/fmp-synthetic.json'),
                    target['id'], as_of='2026-10-08')
    ctx['plan_id'] = plan['id']
    ctx['state'] = db.planning_state()
    ctx['plan_before'] = show(db, ctx['plan_id'])
    db.connection.close()
    data = ctx['payload']
    data['events'] = []
    ctx['file'].write_text(json.dumps(data))
    ctx['first'] = invoke(ctx, ['import', str(ctx['file']), '--yes'])['research_run_id']
    data = news_package()
    data['catalysts'] = [{'catalyst_id': 'availability', 'title': 'Product availability',
        'related_event_key': 'product-release', 'scheduled_date': '2026-11-01',
        'date_status': 'EXPECTED', 'status': 'EXPECTED', 'source_id': 'release',
        'source_locator': 'Availability paragraph', 'qualifiers': 'Fictional expected date'}]
    data['theses'] = [{'thesis_id': 'demand', 'statement': 'Enterprise adoption matters.',
        'assessment': 'INSUFFICIENT_EVIDENCE', 'rationale': 'No adoption evidence.',
        'related_event_keys': ['product-release'], 'uncertainty': 'Uptake unknown.'}]
    ctx['file'].write_text(json.dumps(data))
    ctx['second'] = invoke(ctx, ['import', str(ctx['file']), '--yes'])['research_run_id']
    changed = copy.deepcopy(data)
    changed['events'][0]['facts'].append({'fact_key': 'available',
        'statement': 'Commercial availability was confirmed.', 'source_id': 'release',
        'source_locator': 'Availability update', 'verification_status': 'VERIFIED'})
    changed['catalysts'][0].update(status='DELAYED', scheduled_date='2026-12-01',
                                 qualifiers='Explicitly postponed in fictional update.')
    changed['theses'][0].update(assessment='MIXED', rationale='Availability confirmed, uptake unknown.')
    ctx['file'].write_text(json.dumps(changed))
    ctx['third'] = invoke(ctx, ['import', str(ctx['file']), '--yes'])['research_run_id']


@then('the history exposes added facts postponed catalysts and changed research assessments')
def history(ctx):
    from invest.ledger import Ledger
    from invest.plans import show
    first_delta = invoke(ctx, ['compare', ctx['first'], ctx['second']])
    assert first_delta['new_events'][0]['event_key'] == 'product-release'
    delta = invoke(ctx, ['compare', ctx['second'], ctx['third']])
    assert 'FACT_ADDED' in delta['updated_events'][0]['change_types']
    assert delta['catalyst_changes'][0]['new_status'] == 'DELAYED'
    assert delta['thesis_changes'][0]['new_assessment'] == 'MIXED'
    assert invoke(ctx, ['show', ctx['second']])['skill_version'] == '1.0.1'
    assert invoke(ctx, ['summary', ctx['third']])['events']
    assert len(invoke(ctx, ['list', '--ticker', 'FAKE'])['runs']) == 3
    assert invoke(ctx, ['context', '--ticker', 'FAKE'])['research_run_id'] == ctx['third']
    assert invoke(ctx, ['changes', '--ticker', 'FAKE'])['to_run_id'] == ctx['third']
    db = Ledger(ctx['path'])
    assert db.planning_state() == ctx['state']
    assert show(db, ctx['plan_id']) == ctx['plan_before']
    db.connection.close()
    described = ctx['runner'].invoke(app, ['tools', 'describe', 'research.news.import'])
    tool = json.loads(described.stdout)
    assert tool['mutation_scope'] == 'research'
    assert tool['json_input_schema']['additionalProperties'] is False
    assert 'news_research' in json.loads(ctx['runner'].invoke(app, ['schema']).stdout)


def test_invalid_news_stderr_and_no_database(ctx):
    ctx['file'].write_text('{invalid')
    invoke(ctx, ['validate', str(ctx['file'])], code=1)
    assert not ctx['path'].exists()
