"""Human approval must expose immutable policy versions through discoverable CLI."""

import copy
import json

import pytest
from test_mvp_research_workflows_bdd import accepted_household
from typer.testing import CliRunner

from invest.cli import app
from invest.ledger import Ledger
from invest.planning import get_policy, list_policies


@pytest.fixture
def policy_context(tmp_path, monkeypatch):
    path = tmp_path / 'fictional-ledger.db'
    ctx = {'path': path}
    accepted_household(ctx)
    monkeypatch.setenv('INVEST_DB', str(path))
    monkeypatch.setenv('INVEST_CONFIG', str(tmp_path / 'config.toml'))
    payload = {'id': 'fictional-approved-v1', 'version': '1',
        'data_environment': 'SYNTHETIC', 'source': 'Explicit fictional human-reviewed trading policy',
        'minimum_notional': '25', 'fee_per_trade': '0',
        'max_position_age_days': 30, 'cash_floors': {'synthetic': '100'},
        'permissions': {'synthetic': {ctx['security']: {'can_buy': True, 'can_sell': False,
            'can_hold': True, 'share_increment': '0.001'}}}}
    file = tmp_path / 'reviewed-policy.json'
    file.write_text(json.dumps(payload))
    return {'path': path, 'file': file, 'payload': payload, 'runner': CliRunner()}


def invoke(ctx, args):
    return ctx['runner'].invoke(app, args)


def stored(ctx):
    ledger = Ledger(ctx['path'])
    try:
        return list_policies(ledger)
    finally:
        ledger.connection.close()


def approve(ctx, confirm=False):
    result = invoke(ctx, ['policy', 'approve', '--file', str(ctx['file'])] +
                    (['--confirm'] if confirm else []))
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout)


def test_policy_preview_and_explicit_approval_are_idempotent_with_public_list_show(policy_context):
    ctx = policy_context
    before = stored(ctx)
    preview = approve(ctx)
    assert preview['status'] == 'PREVIEW' and preview['committed'] is False
    assert stored(ctx) == before
    accepted = approve(ctx, confirm=True)
    assert accepted['status'] == 'APPROVED' and accepted['committed'] is True
    approved_rows = stored(ctx)
    assert len(approved_rows['policies']) == 1
    repeated = approve(ctx, confirm=True)
    assert repeated['status'] == 'UNCHANGED' and repeated['committed'] is False
    assert stored(ctx) == approved_rows
    listed = invoke(ctx, ['policy', 'list'])
    assert listed.exit_code == 0, listed.output
    assert json.loads(listed.stdout) == approved_rows
    shown = invoke(ctx, ['policy', 'show', ctx['payload']['id']])
    assert shown.exit_code == 0, shown.output
    ledger = Ledger(ctx['path'])
    try:
        assert json.loads(shown.stdout) == get_policy(ledger, ctx['payload']['id'])
    finally:
        ledger.connection.close()


def test_policy_version_conflict_rejects_atomically(policy_context):
    ctx = policy_context
    approve(ctx, confirm=True)
    before = stored(ctx)
    changed = copy.deepcopy(ctx['payload'])
    changed['permissions']['synthetic'][next(iter(changed['permissions']['synthetic']))]['can_sell'] = True
    ctx['file'].write_text(json.dumps(changed))
    result = invoke(ctx, ['policy', 'approve', '--file', str(ctx['file']), '--confirm'])
    assert result.exit_code == 3, result.output
    assert 'immutable' in json.loads(result.stderr)['error'].lower()
    assert stored(ctx) == before


@pytest.mark.parametrize('mutation', ['missing_environment', 'missing_source', 'missing_version',
    'string_permission', 'unknown_permission', 'float_increment', 'missing_buy_permission'])
def test_policy_cli_strict_input_rejection_does_not_accept_versions(policy_context, mutation):
    ctx = policy_context
    assert approve(ctx)['status'] == 'PREVIEW'
    payload = copy.deepcopy(ctx['payload'])
    rule = payload['permissions']['synthetic'][next(iter(payload['permissions']['synthetic']))]
    if mutation.startswith('missing_') and mutation != 'missing_buy_permission':
        payload.pop({'missing_environment': 'data_environment', 'missing_source': 'source',
                     'missing_version': 'version'}[mutation])
    elif mutation == 'string_permission':
        rule['can_sell'] = 'false'
    elif mutation == 'unknown_permission':
        rule['automatic_trade'] = True
    elif mutation == 'float_increment':
        rule['share_increment'] = 0.001
    else:
        rule.pop('can_buy')
    ctx['file'].write_text(json.dumps(payload))
    result = invoke(ctx, ['policy', 'approve', '--file', str(ctx['file']), '--confirm'])
    assert result.exit_code == 1, result.output
    assert isinstance(json.loads(result.stderr)['error'], str)
    assert stored(ctx)['policies'] == []


@pytest.mark.parametrize('reference', ['account', 'security'])
def test_policy_approval_requires_existing_canonical_references(policy_context, reference):
    ctx = policy_context
    assert approve(ctx)['status'] == 'PREVIEW'
    payload = copy.deepcopy(ctx['payload'])
    if reference == 'account':
        payload['permissions']['fictional-unknown'] = payload['permissions'].pop('synthetic')
    else:
        rules = payload['permissions']['synthetic']
        rules['fictional-unknown'] = rules.pop(next(iter(rules)))
    ctx['file'].write_text(json.dumps(payload))
    result = invoke(ctx, ['policy', 'approve', '--file', str(ctx['file']), '--confirm'])
    assert result.exit_code == 3, result.output
    assert isinstance(json.loads(result.stderr)['error'], str)
    assert stored(ctx)['policies'] == []


def test_policy_preview_does_not_create_absent_selected_ledger(policy_context, monkeypatch, tmp_path):
    path = tmp_path / 'absent-selected.db'
    monkeypatch.setenv('INVEST_DB', str(path))
    result = invoke(policy_context, ['policy', 'approve', '--file', str(policy_context['file'])])
    assert not path.exists(), 'Policy preview must not initialize the selected ledger'
    assert result.exit_code == 3, result.output
    assert isinstance(json.loads(result.stderr)['error'], str)


def test_policy_tools_discovery_exposes_confirmation_and_strict_input_model(policy_context):
    result = invoke(policy_context, ['tools', 'describe', 'policy.approve'])
    assert result.exit_code == 0, result.output
    contract = json.loads(result.stdout)
    assert contract['mutation_scope'] == 'policy'
    assert contract['mutates_persistent_state'] is True
    assert contract['input_schema']['properties']['confirm']['type'] == 'boolean'
    schema = contract['json_input_schema']
    assert schema['additionalProperties'] is False
    assert {'version', 'permissions', 'data_environment', 'source'} <= set(schema['required'])
    assert schema['properties']['permissions']['type'] == 'object'
    assert schema['$defs'], 'Nested permissions need discoverable independent buy/sell/hold constraints'
    for command in ['policy.list', 'policy.show']:
        described = invoke(policy_context, ['tools', 'describe', command])
        assert described.exit_code == 0, described.output
        output = json.loads(described.stdout)
        assert output['mutation_scope'] == 'read'
        assert output['mutates_persistent_state'] is False
