"""Snapshot CLI previews cannot implicitly accept financial facts or create a ledger."""

import copy
import json

import pytest
from typer.testing import CliRunner

from invest.cli import app
from invest.ledger import Ledger


def snapshot(cash='100'):
    return {'account': {'id': 'fictional', 'name': 'Fictional confirmation account',
                        'tax_status': 'TAX_FREE', 'history_complete': True},
            'positions': [], 'lots': [], 'cash': cash, 'cash_known': True,
            'positions_complete': True, 'lots_complete': True,
            'source_timestamp': '2026-10-10', 'source_hash': 'fictional-reviewed-source-' + cash,
            'data_environment': 'SYNTHETIC'}


@pytest.fixture
def context(tmp_path, monkeypatch):
    path = tmp_path / 'fictional-confirmation.db'
    monkeypatch.setenv('INVEST_DB', str(path))
    return {'path': path, 'directory': tmp_path, 'runner': CliRunner()}


def invoke(ctx, payload, *, confirm=False):
    source = ctx['directory'] / 'fictional-snapshot.json'
    source.write_text(json.dumps(payload))
    command = ['portfolio', 'apply', str(source)]
    if confirm:
        command.append('--confirm')
    return ctx['runner'].invoke(app, command)


def test_unconfirmed_snapshot_preview_does_not_create_selected_ledger(context):
    response = invoke(context, snapshot())
    assert response.exit_code == 0, response.stderr
    assert not context['path'].exists(), 'A preview cannot initialize or accept the selected ledger'
    result = json.loads(response.stdout)
    assert result['committed'] is False
    assert result['status'] in {'PREVIEW', 'AVAILABLE', 'REVIEW_REQUIRED'}


def test_unconfirmed_snapshot_preview_does_not_change_existing_financial_facts(context):
    ledger = Ledger(context['path'])
    try:
        original = snapshot('100')
        original['source_timestamp'] = '2026-10-09'
        ledger.apply(original)
        before = copy.deepcopy(ledger.state())
        response = invoke(context, snapshot('200'))
        assert response.exit_code == 0, response.stderr
        assert ledger.state() == before
        assert json.loads(response.stdout)['committed'] is False
    finally:
        ledger.connection.close()


def test_explicit_confirmation_accepts_once_and_repeated_source_is_idempotent(context):
    payload = snapshot()
    first = invoke(context, payload, confirm=True)
    assert first.exit_code == 0, first.stderr
    assert json.loads(first.stdout)['status'] == 'APPLIED'
    ledger = Ledger(context['path'])
    try:
        accepted = copy.deepcopy(ledger.state())
        assert accepted['cash_balances'][0]['amount'] == '100'
        repeated = invoke(context, payload, confirm=True)
        assert repeated.exit_code == 0, repeated.stderr
        assert json.loads(repeated.stdout)['status'] == 'UNCHANGED'
        assert ledger.state() == accepted
    finally:
        ledger.connection.close()


def test_invalid_confirmed_snapshot_does_not_initialize_selected_file(context):
    payload = snapshot()
    payload['cash'] = 'not-a-financial-number'
    response = invoke(context, payload, confirm=True)
    assert response.exit_code == 1
    assert response.stdout == ''
    assert json.loads(response.stderr)['error']
    assert not context['path'].exists(), 'Validation precedes selected database creation'
