"""Accepted source environment is explicit; absence never becomes provenance."""
import copy
import json

import pytest
from typer.testing import CliRunner

from invest.cli import app
from invest.ledger import Ledger
from invest.models import DomainError


def source(environment='SYNTHETIC'):
    return {'account': {'id': 'fictional', 'name': 'Fictional source account',
                       'currency': 'USD', 'tax_status': 'TAX_FREE', 'history_complete': True},
            'positions': [], 'lots': [], 'cash': '100', 'cash_known': True,
            'positions_complete': True, 'lots_complete': True,
            'source_timestamp': '2026-03-01', 'source_hash': 'fictional-reviewed-cash-source',
            'data_environment': environment}


@pytest.mark.parametrize('omitted', [True, False])
def test_unknown_environment_apply_rejects_atomic(tmp_path, omitted):
    ledger = Ledger(tmp_path / 'source.db')
    try:
        payload = source(None)
        if omitted:
            payload.pop('data_environment')
        before = copy.deepcopy(ledger.state())
        with pytest.raises(DomainError) as failure:
            ledger.apply(payload)
        assert failure.value.code == 3
        assert any(i['code'] == 'UNKNOWN_DATA_ENVIRONMENT'
                   for i in failure.value.result['issues'])
        assert ledger.state() == before
        assert ledger.rows('snapshots') == []
    finally:
        ledger.connection.close()


def test_reconcile_unknown_environment_returns_typed_review_without_writes(tmp_path):
    ledger = Ledger(tmp_path / 'review.db')
    try:
        before = copy.deepcopy(ledger.state())
        result = ledger.reconcile(source(None))
        assert result['status'] == 'REVIEW_REQUIRED'
        issue = next(i for i in result['issues'] if i['code'] == 'UNKNOWN_DATA_ENVIRONMENT')
        assert issue.get('blocks_acceptance', True)
        assert ledger.state() == before
    finally:
        ledger.connection.close()


def test_cli_confirm_missing_environment_cannot_create_selected_database(tmp_path, monkeypatch):
    selected = tmp_path / 'absent.db'
    monkeypatch.setenv('INVEST_DB', str(selected))
    payload = source()
    payload.pop('data_environment')
    path = tmp_path / 'source.json'
    path.write_text(json.dumps(payload))
    result = CliRunner().invoke(app, ['portfolio', 'apply', str(path), '--confirm'])
    assert result.exit_code == 3
    assert 'UNKNOWN_DATA_ENVIRONMENT' in result.stderr
    assert not selected.exists()


@pytest.mark.parametrize('environment', ['REAL', 'SYNTHETIC'])
def test_explicit_environment_control_is_accepted(tmp_path, environment):
    ledger = Ledger(tmp_path / 'control.db')
    try:
        assert ledger.apply(source(environment))['status'] == 'APPLIED'
        assert ledger.rows('snapshots')[0]['data_environment'] == environment
    finally:
        ledger.connection.close()
