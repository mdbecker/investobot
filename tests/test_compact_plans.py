import copy
import json
from decimal import Decimal
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from typer.testing import CliRunner

from invest import plans
from invest.cli import app
from invest.ledger import Ledger
from invest.market import MarketClient
from invest.models import DomainError
from invest.plan_storage import save_plan
from invest.reports import render
from invest.targets import save

scenarios('features/compact_plans.feature')

SUMMARY_KEYS = {'id', 'name', 'target_version_id', 'created_at', 'as_of', 'status',
                'generated_status', 'trade_count', 'turnover', 'tax_summary', 'drift_summary',
                'warning_count', 'warnings_preview', 'storage_identity'}


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.setenv('INVEST_DB', str(tmp_path / 'ledger.db'))
    monkeypatch.setenv('INVEST_CONFIG', str(tmp_path / 'config.toml'))
    monkeypatch.setenv('INVEST_FIXTURES', '/app/tests/fixtures/fmp-synthetic.json')
    ledger = Ledger(tmp_path / 'ledger.db')
    yield {'ledger': ledger, 'monkeypatch': monkeypatch, 'ids': []}
    ledger.connection.close()


@given('an empty household')
def empty(ctx):
    pass


@given('twenty saved alternatives with large synthetic histories')
def alternatives(ctx):
    baseline = plans.state_hash(ctx['ledger'].planning_state())
    for i in range(20):
        pid = f'plan-{i:02}'
        value = {'id': pid, 'name': f'Alternative {i}', 'target_version_id': 'version-1',
                 'created_at': f'2026-10-{8 + i // 2:02}T12:00:00Z', 'as_of': '2026-10-08',
                 'status': 'READY_FOR_HUMAN_REVIEW', 'source_state_hash': baseline,
                 'source_snapshot_ids': ['snapshot-1'],
                 'source_state': ctx['ledger'].planning_state(),
                 'assumptions': {'prices': {'security': {'price': '100'}}, 'tax_rates': None},
                 'target': {'planning_constraints': {'target_tolerance': '0.01'}},
                 'proposed_actions': [{'type': 'SELL', 'quantity': '1', 'price': '100'}],
                 'trade_count': 1, 'turnover': '100',
                 'tax_analysis': {'short_term_gain_loss': '0', 'long_term_gain_loss': '12.50',
                                  'estimated_tax_effect': None, 'analyses': ['details']},
                 'remaining_target_drift': [{'difference_weight': '-0.02'},
                                            {'difference_weight': '0.01'}],
                 'warnings': [f'Saved warning {j}' for j in range(8)]}
        with ctx['ledger'].connection:
            save_plan(ctx['ledger'], value)
        ctx['ids'].append(pid)


def guarded(ctx, operation):
    ledger = ctx['ledger']
    original_rows, original_state, original_hash = ledger.rows, ledger.state, plans.state_hash
    counts = {'state': 0, 'hash': 0}

    def rows(table):
        assert table != 'plans', 'Compact requests must project SQLite JSON, not load full plans'
        return original_rows(table)

    def state():
        counts['state'] += 1
        return original_state()

    def hashed(value):
        counts['hash'] += 1
        return original_hash(value)

    with ctx['monkeypatch'].context() as patch:
        patch.setattr(ledger, 'rows', rows)
        patch.setattr(ledger, 'state', state)
        patch.setattr(plans, 'state_hash', hashed)
        result = operation()
    assert counts['state'] <= 1
    assert counts['hash'] <= 1
    return result


@when('the agent lists alternatives')
def listed(ctx):
    ctx['result'] = guarded(ctx, lambda: plans.list_plans(ctx['ledger']))


@when('the agent compares alternatives')
def compared(ctx):
    ctx['result'] = guarded(ctx, lambda: plans.compare(ctx['ledger'], *ctx['ids']))


@then('twenty compact summaries preserve saved financial metrics')
def metrics(ctx):
    assert len(ctx['result']['plans']) == 20
    for value in ctx['result']['plans']:
        assert set(value) == SUMMARY_KEYS
        assert value['trade_count'] == 1
        assert Decimal(value['turnover']) == 100
        assert value['tax_summary'] == {'short_term_gain_loss': '0',
            'long_term_gain_loss': '12.50', 'estimated_tax_effect': None}
        assert Decimal(value['drift_summary']['maximum_absolute_weight_drift']) == Decimal('.02')
        assert value['drift_summary']['positions_outside_tolerance'] == 1
        assert value['warning_count'] == 8
        assert value['warnings_preview'] == [f'Saved warning {j}' for j in range(5)]
        assert value['generated_status'] == 'READY_FOR_HUMAN_REVIEW'


@then('the response is smaller than 128 KiB without detailed financial state')
def small(ctx):
    assert len(json.dumps(ctx['result']).encode()) < 128 * 1024
    for value in ctx['result']['plans']:
        assert not {'source_state', 'proposed_actions', 'exposure_analysis', 'tax_analysis',
                    'remaining_target_drift', 'assumptions'} & value.keys()


@then('alternatives are ordered by newest creation time and stable ID')
def ordered(ctx):
    values = ctx['result']['plans']
    assert [p['created_at'] for p in values] == sorted(
        [p['created_at'] for p in values], reverse=True)
    for first, second in zip(values, values[1:]):
        if first['created_at'] == second['created_at']:
            assert first['id'] > second['id']


@then('compatible alternatives disclose matching assumptions without ranking')
def compatible(ctx):
    result = ctx['result']
    assert all(result[key] is True for key in ('same_source_snapshot', 'same_price_assumptions',
                                               'same_tax_assumptions', 'same_analysis_date'))
    assert result['warnings'] == []
    assert result['ranking'] is None


@given(parsers.parse('one alternative has different {assumption}'))
def incompatible(ctx, assumption):
    value = plans.persisted(ctx['ledger'], ctx['ids'][0])
    if assumption == 'prices':
        value['assumptions']['prices']['security']['price'] = '110'
    elif assumption == 'tax rates':
        value['assumptions']['tax_rates'] = {'long_term': '.15'}
    elif assumption == 'analysis date':
        value['as_of'] = '2026-10-09'
    else:
        value['source_state']['activities'] = [{'id': 'different-baseline'}]
        value['source_snapshot_ids'] = ['snapshot-2']
    with ctx['ledger'].connection:
        ctx['ledger'].connection.execute('DELETE FROM plan_runs WHERE id=?', (value['id'],))
        save_plan(ctx['ledger'], value)


@then(parsers.parse('comparison identifies incompatible {assumption}'))
def incompatibility(ctx, assumption):
    key, phrase = {'prices': ('same_price_assumptions', 'price'),
                   'tax rates': ('same_tax_assumptions', 'tax'),
                   'analysis date': ('same_analysis_date', 'analysis date'),
                   'source snapshot': ('same_source_snapshot', 'source snapshot')}[assumption]
    assert ctx['result'][key] is False
    assert any(phrase in w.lower() for w in ctx['result']['warnings'])


@given('a target is ready for synthetic retirement planning')
def target(ctx):
    ledger = ctx['ledger']
    ledger.apply({'account': {'id': 'ira', 'name': 'IRA', 'tax_status': 'TAX_FREE'},
        'positions': [{'security': 'SYN', 'asset_type': 'STOCK', 'quantity': '10',
                       'price': '100', 'market_value': '1000', 'as_of': '2026-10-08', 'displayed_price_precision': 0, 'displayed_market_value_precision': 0}],
        'cash': '100', 'source_hash': 'synthetic', 'source_timestamp': '2026-10-08',
        'data_environment': 'SYNTHETIC'})
    sid = ledger.resolve('SYN')['id']
    ctx['target'] = save(ledger, {'name': 'Synthetic target',
        'target_allocations': {sid: '.5', 'CASH': '.5'},
        'planning_constraints': {'eligible_accounts': ['ira'], 'permitted_securities': {'ira': [sid]}}})
    ctx['client'] = MarketClient(ledger, fixture_path=Path('tests/fixtures/fmp-synthetic.json'))


@when('the agent generates a plan through the CLI')
def generated_cli(ctx):
    result = CliRunner().invoke(app, ['plan', 'generate', '--target', ctx['target']['id'],
                                     '--as-of', '2026-10-08'])
    assert result.exit_code == 0, result.output
    ctx['result'] = json.loads(result.stdout)


@then('the generation response contains the saved compact summary')
def generated_summary(ctx):
    assert set(ctx['result']) == {'plan'}
    summary = ctx['result']['plan']
    assert set(summary) == SUMMARY_KEYS | {'mode', 'data_environment', 'issues'}
    assert summary['mode'] == 'HYPOTHETICAL'
    assert summary['issues'][0]['code'] == 'UNAPPROVED_TRADING_POLICY'
    saved = plans.persisted(ctx['ledger'], summary['id'])
    assert summary['trade_count'] == len(saved['proposed_actions'])
    assert saved['source_state']['snapshots']
    assert summary == plans.list_plans(ctx['ledger'])['plans'][0]


@given('its complete plan and historical reports are saved')
def historical(ctx):
    ctx['original'] = copy.deepcopy(plans.generate(ctx['ledger'], ctx['client'],
        ctx['target']['id'], as_of='2026-10-08'))
    ctx['reports'] = {format: render(ctx['original'], format) for format in ('json', 'markdown')}


@when('accepted cash changes and summaries are inspected')
def changed(ctx):
    ctx['ledger'].record_activity({'activity_id': 'interest', 'account_id': 'ira',
        'type': 'INTEREST', 'amount': '1', 'date': '2026-10-08'}, yes=True)
    listed(ctx)


@then('listed status is stale while generated status is preserved')
def stale(ctx):
    value = ctx['result']['plans'][0]
    assert value['status'] == 'STALE'
    assert value['generated_status'] == ctx['original']['status']


@then('full retrieval retains original assumptions and proposed trades')
def full(ctx):
    value = plans.show(ctx['ledger'], ctx['original']['id'])
    assert value['source_state'] == ctx['original']['source_state']
    assert value['assumptions'] == ctx['original']['assumptions']
    assert value['proposed_actions'] == ctx['original']['proposed_actions']
    assert plans.persisted(ctx['ledger'], value['id']) == ctx['original']


@then('historical report bytes remain identical')
def reproducible(ctx):
    for format, original in ctx['reports'].items():
        assert render(plans.persisted(ctx['ledger'], ctx['original']['id']), format) == original


@given('a saved synthetic plan without optional financial fields')
def legacy(ctx):
    value = {'id': 'minimal', 'name': 'Synthetic minimal plan', 'status': 'REVIEW_REQUIRED',
             'source_state_hash': plans.state_hash(ctx['ledger'].planning_state()),
             'source_state': ctx['ledger'].planning_state(), 'created_at': '2026-10-08', 'as_of': '2026-10-08'}
    with ctx['ledger'].connection:
        ctx['ledger'].connection.execute('DELETE FROM plan_runs WHERE id=?', (value['id'],))
        save_plan(ctx['ledger'], value)


@then('unknown summary values are null and warnings are empty')
def unknown(ctx):
    value = ctx['result']['plans'][0]
    assert set(value) == SUMMARY_KEYS
    assert value['turnover'] is None
    assert all(v is None for v in value['tax_summary'].values())
    assert value['drift_summary']['maximum_absolute_weight_drift'] is None
    assert value['warning_count'] == 0
    assert value['warnings_preview'] == []


@then('the plans array is empty')
def empty_list(ctx):
    assert ctx['result'] == {'plans': []}


@when('the agent compares a missing identifier')
def invalid(ctx):
    try:
        plans.compare(ctx['ledger'], ctx['ids'][0], 'missing')
    except DomainError as exc:
        ctx['error'] = exc


@then('comparison fails with input exit code')
def input_error(ctx):
    assert ctx['error'].code == 1
