"""Read-only inspection and unsuccessful previews never initialize a selected ledger."""

import json

import pytest
from typer.testing import CliRunner

from invest.cli import app


@pytest.fixture
def context(tmp_path, monkeypatch):
    selected = tmp_path / 'absent-fictional-ledger.db'
    monkeypatch.setenv('INVEST_DB', str(selected))
    monkeypatch.setenv('INVEST_PROMPTS', str(tmp_path / 'prompts'))
    return {'directory': tmp_path, 'path': selected, 'runner': CliRunner()}


def inspect(context, command, *, success):
    response = context['runner'].invoke(app, command)
    assert not context['path'].exists(), 'Read-only operations cannot create the selected financial ledger'
    if success:
        assert response.exit_code == 0, response.stderr
        assert not response.stderr
        return json.loads(response.stdout)
    assert response.exit_code in {1, 3}, response.stderr
    assert response.stdout == ''
    assert json.loads(response.stderr)['error']


@pytest.mark.parametrize('command', [
    ['portfolio', 'summary'], ['target', 'list'], ['plan', 'list'],
], ids=['portfolio_summary', 'target_list', 'plan_list'])
def test_empty_selected_ledger_read_queries_do_not_initialize_file(context, command):
    assert isinstance(inspect(context, command, success=True), dict)


@pytest.mark.parametrize('command', [
    ['target', 'show', 'fictional-missing'], ['target', 'diff', 'fictional-missing'],
    ['plan', 'show', 'fictional-missing'],
], ids=['target_show', 'target_diff', 'plan_show'])
def test_unknown_selected_objects_return_json_without_creating_ledger(context, command):
    inspect(context, command, success=False)


def write(context, name, value):
    path = context['directory'] / name
    path.write_text(json.dumps(value))
    return str(path)


def test_snapshot_reconciliation_previews_without_creating_selected_ledger(context):
    source = write(context, 'fictional-snapshot.json', {
        'account': {'id': 'fictional', 'name': 'Fictional reconcile account', 'tax_status': 'TAX_FREE'},
        'positions': [], 'lots': [], 'cash': '100', 'cash_known': True,
        'positions_complete': True, 'lots_complete': True, 'source_timestamp': '2026-10-10',
        'source_hash': 'fictional-original-account-source', 'data_environment': 'SYNTHETIC',
    })
    assert isinstance(inspect(context, ['portfolio', 'reconcile', source], success=True), dict)


def test_unknown_account_activity_preview_does_not_initialize_ledger(context):
    source = write(context, 'fictional-activity.json', {
        'activity_id': 'fictional-deposit', 'account_id': 'fictional-missing',
        'type': 'CASH_DEPOSIT', 'date': '2026-10-10', 'amount': '100',
        'source': 'Reviewed fictional broker cash record',
    })
    inspect(context, ['portfolio', 'record-activity', source], success=False)


def test_unknown_security_classification_preview_does_not_initialize_ledger(context):
    inspect(context, ['security', 'classify', 'fictional-missing', '--asset-type', 'ETF',
                      '--source', 'Reviewed fictional issuer classification'], success=False)


def test_unknown_account_update_preview_does_not_initialize_ledger(context):
    source = write(context, 'fictional-account-update.json', {
        'name': 'Fictional updated account', 'reason': 'Human reviewed account name correction',
        'source': 'Reviewed fictional account settings',
    })
    inspect(context, ['account', 'update', 'fictional-missing', '--file', source], success=False)
