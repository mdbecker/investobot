import json
from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from invest import plans, targets
from invest.ledger import Ledger
from invest.web import _get_api, _planning_post

scenarios('features/compact_web.feature')


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.setenv('INVEST_CONFIG', str(tmp_path / 'config.toml'))
    monkeypatch.setenv('INVEST_FIXTURES', str(Path('tests/fixtures/fmp-synthetic.json').resolve()))
    ledger = Ledger(tmp_path / 'ledger.db')
    yield {'ledger': ledger}
    ledger.connection.close()


@given('a synthetic inspection planning portfolio')
def portfolio(ctx):
    ledger = ctx['ledger']
    ledger.apply({'account': {'id': 'ira', 'name': 'IRA', 'tax_status': 'TAX_FREE'},
        'positions': [{'security': 'AAA', 'asset_type': 'STOCK', 'quantity': '10',
                       'price': '100', 'market_value': '1000', 'as_of': '2026-10-08'}],
        'cash': '0', 'source_timestamp': '2026-10-08', 'source_hash': 'compact-web'})
    security_id = ledger.resolve('AAA')['id']
    ctx['target'] = targets.save(ledger, {'name': 'Hold synthetic shares',
        'target_allocations': {security_id: '1', 'CASH': '0'},
        'planning_constraints': {'eligible_accounts': ['ira'],
                                'permitted_securities': {'ira': [security_id]}}})


@when('a plan is generated through the inspection boundary')
def generate(ctx):
    ctx['generated'] = _planning_post(ctx['ledger'], '/api/plans/generate',
        {'target_id': ctx['target']['id'], 'as_of': '2026-10-08'})


@then('generation returns only the shared compact plan summary')
def generated_summary(ctx):
    response = ctx['generated']
    assert set(response) == {'plan'}
    saved = plans.persisted(ctx['ledger'], response['plan']['id'])
    assert response['plan'] == plans.plan_summary(saved)
    assert 'source_state' not in response['plan']
    assert 'proposed_actions' not in response['plan']


@when('two alternatives are generated and inspected')
def alternatives(ctx):
    generate(ctx)
    generate(ctx)
    ids = [p['id'] for p in ctx['ledger'].rows('plans')]
    ctx['list'] = _get_api(ctx['ledger'], '/api/plans', {})
    ctx['compare'] = _planning_post(ctx['ledger'], '/api/plans/compare', {'plan_ids': ids})


@then('inspection lists and compares the shared compact summaries')
def compact(ctx):
    for response in [ctx['list'], ctx['compare']]:
        assert len(response['plans']) == 2
        assert len(json.dumps(response).encode()) < 128 * 1024
        for summary in response['plans']:
            assert summary == plans.plan_summary(plans.persisted(ctx['ledger'], summary['id']))
            assert 'proposed_actions' not in summary
            assert 'source_state' not in summary


@then('explicit inspection retrieval preserves full details and reports')
def full(ctx):
    saved = ctx['ledger'].rows('plans')[0]
    assert _get_api(ctx['ledger'], '/api/plans/' + saved['id'], {}) == saved
    report, _, _ = _get_api(ctx['ledger'], '/api/plans/' + saved['id'] + '/report',
                                {'format': ['json']})
    assert json.loads(report) == saved
