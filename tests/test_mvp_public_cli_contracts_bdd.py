"""Public CLI publication and discovery contracts."""
import copy
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when
from typer.testing import CliRunner

from invest.cli import app
from invest.ledger import Ledger
from invest.planning import save_policy
from test_mvp_research_workflows_bdd import accepted_household

scenarios('features/mvp/public_cli_contracts.feature')


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    path = tmp_path / 'fictional.db'
    monkeypatch.setenv('INVEST_DB', str(path))
    monkeypatch.setenv('INVEST_CONFIG', str(tmp_path / 'config.toml'))
    monkeypatch.delenv('FMP_API_KEY', raising=False)
    return {'path': path, 'tmp': tmp_path, 'runner': CliRunner()}


def state(ctx):
    selected = Ledger(ctx['path'])
    try:
        return selected.state()
    finally:
        selected.connection.close()


def invoke(ctx, argv):
    return ctx['runner'].invoke(app, argv)


@given('a fictional accepted household and dataset manifest')
def household(ctx):
    accepted_household(ctx)
    ctx['manifest'] = ctx['tmp'] / 'manifest.json'
    ctx['manifest'].write_text(json.dumps({'id': 'fictional-reviewed-data',
        'as_of': '2026-10-10', 'data_environment': 'SYNTHETIC', 'artifacts': []}))
    ctx['before'] = copy.deepcopy(state(ctx))


@when('the manifest is submitted without confirmation')
def preview(ctx):
    ctx['result'] = invoke(ctx, ['data', 'snapshot', '--file', str(ctx['manifest'])])


@then('it is validated without persistent writes')
def no_write(ctx):
    assert ctx['result'].exit_code == 0, ctx['result'].output
    assert json.loads(ctx['result'].stdout)['committed'] is False
    assert state(ctx) == ctx['before']


@when('the manifest is explicitly confirmed twice')
def publish(ctx):
    ctx['first'] = invoke(ctx, ['data', 'snapshot', '--file', str(ctx['manifest']), '--confirm'])
    ctx['second'] = invoke(ctx, ['data', 'snapshot', '--file', str(ctx['manifest']), '--confirm'])


@then('exactly one immutable manifest is published')
def once(ctx):
    assert ctx['first'].exit_code == ctx['second'].exit_code == 0
    assert json.loads(ctx['first'].stdout)['committed'] is True
    assert json.loads(ctx['second'].stdout)['committed'] is False
    result = invoke(ctx, ['data', 'list'])
    assert result.exit_code == 0
    selected = Ledger(ctx['path'])
    try:
        assert len(json.loads(result.stdout)['snapshots']) == 1
    finally:
        selected.connection.close()


@when('public planning commands are discovered')
def discover(ctx):
    ctx['preview'] = invoke(ctx, ['tools', 'describe', 'plan.preview'])
    ctx['retired'] = invoke(ctx, ['plan', 'generate', '--help'])


@then('preview is read only and generate is absent')
def retired(ctx):
    assert ctx['preview'].exit_code == 0, ctx['preview'].output
    assert json.loads(ctx['preview'].stdout)['mutates_persistent_state'] is False
    assert ctx['retired'].exit_code != 0
    assert state(ctx) == ctx['before']


@when('an approved proposal is requested with an embedded target')
def embedded(ctx):
    selected = Ledger(ctx['path'])
    try:
        policy = save_policy(selected, {'id': 'fictional-approved', 'version': '1',
            'data_environment': 'SYNTHETIC', 'source': 'Reviewed fictional policy',
            'minimum_notional': '1', 'fee_per_trade': '0', 'cash_floors': {'synthetic': '0'},
            'permissions': {'synthetic': {ctx['security']: {'can_buy': True,
                'can_sell': False, 'can_hold': True, 'share_increment': '1'}}}}, confirm=True)
    finally:
        selected.connection.close()
    file = ctx['tmp'] / 'proposal.json'
    file.write_text(json.dumps({'data_environment': 'SYNTHETIC', 'account_id': 'synthetic',
        'target': {'id': 'hidden-target', 'weights': {ctx['security']: '1'}}, 'prices': {}}))
    ctx['before'] = state(ctx)
    ctx['result'] = invoke(ctx, ['plan', 'propose', '--file', str(file), '--policy', policy['id'],
        '--mode', 'contributions-only', '--as-of', '2026-10-10'])


@then('it is rejected without target or plan writes')
def rejection(ctx):
    assert ctx['result'].exit_code == 1, ctx['result'].output
    assert 'target' in json.loads(ctx['result'].stderr)['error'].lower()
    assert state(ctx) == ctx['before']


@when('current exposure is requested')
def exposure(ctx):
    ctx['result'] = invoke(ctx, ['portfolio', 'exposure'])


@then('the shared response reports date and numeric coverage without mutation')
def exposure_shape(ctx):
    assert ctx['result'].exit_code == 0, ctx['result'].output
    output = json.loads(ctx['result'].stdout)
    assert output['as_of'] == datetime.now(UTC).date().isoformat()
    assert {'known_value_subtotal', 'unknown_exposure_value', 'unresolved_identity_value',
            'stale_exposure_value', 'exposures', 'issues'} <= output.keys()
    assert state(ctx) == ctx['before']


@when('routine investing guidance is read')
def guidance(ctx):
    root = Path(__file__).resolve().parents[1] / 'skills'
    ctx['guidance'] = '\n'.join(path.read_text() for path in root.rglob('SKILL.md')).lower()


@then('it prefers monthly sessions and contributions without hard date gates')
def monthly(ctx):
    assert 'one routine discretionary trading session per month' in ctx['guidance']
    assert 'at most four rebalances per year' in ctx['guidance']
    assert 'contributions-only' in ctx['guidance']
    assert 'any valid date' in ctx['guidance']


@when('historical candidates are compared with a configured approved policy')
def compare(ctx):
    selected = Ledger(ctx['path'])
    try:
        policy = save_policy(selected, {'id': 'fictional-compare-policy', 'version': '1',
            'data_environment': 'SYNTHETIC', 'source': 'Reviewed fictional policy',
            'minimum_notional': '1', 'fee_per_trade': '0', 'cash_floors': {'synthetic': '0'},
            'permissions': {'synthetic': {ctx['security']: {'can_buy': True,
                'can_sell': False, 'can_hold': True, 'share_increment': '1'}}}}, confirm=True)
    finally:
        selected.connection.close()
    file = ctx['tmp'] / 'comparison.json'
    file.write_text(json.dumps({'start': '2026-10-08', 'end': '2026-10-09',
        'candidates': [{'id': 'fictional-index', 'weights': {ctx['security']: '1'}}, {'id': 'fictional-mix', 'weights': {ctx['security']: '.5', 'CASH': '.5'}}],
        'history': {ctx['security']: [{'date': '2026-10-08', 'total_return_index': '100'},
                                    {'date': '2026-10-09', 'total_return_index': '110'}]},
        'history_provenance': {'kind': 'DIVIDEND_ADJUSTED_TOTAL_RETURN_INDEX',
            'source_id': 'fictional-reviewed-history', 'data_environment': 'SYNTHETIC',
            'expected_sessions': ['2026-10-08', '2026-10-09']},
        'manifest_ids': ['fictional-history'], 'cash_return': '0', 'fees': '0', 'starting_value': '1000', 'rebalancing': 'NONE',
        'data_environment': 'SYNTHETIC', 'policy_id': policy['id']}))
    ctx['before'] = state(ctx)
    ctx['result'] = invoke(ctx, ['backtest', 'compare', str(file)])


@then('immutable runs are identified but targets and transition plans are not created')
def no_transition(ctx):
    assert ctx['result'].exit_code == 0, ctx['result'].output
    output = json.loads(ctx['result'].stdout)
    assert 'transition_plans' not in output
    assert output['candidates'][0]['id']
    assert state(ctx) == ctx['before']
