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


def invested_source():
    payload = source()
    payload['positions'] = [dict(security='FICT', quantity='1', price='10',
        market_value='10', cost_basis='8', displayed_price_precision=2,
        displayed_market_value_precision=2)]
    payload['lots'] = [dict(id='fictional-lot', security='FICT',
        acquisition_date='2026-01-01', quantity='1', remaining_quantity='1', cost_basis='8')]
    return payload


def test_accepted_financial_rows_inherit_explicit_source_environment(tmp_path):
    ledger = Ledger(tmp_path / 'inherit.db')
    try:
        ledger.apply(invested_source())
        for table in ('accounts', 'positions', 'lots', 'cash_balances', 'securities'):
            assert ledger.rows(table)[0]['data_environment'] == 'SYNTHETIC'
    finally:
        ledger.connection.close()


@pytest.mark.parametrize('table', ['positions', 'lots'])
def test_mixed_child_source_is_rejected_without_writes(tmp_path, table):
    ledger = Ledger(tmp_path / 'mixed.db')
    try:
        payload = invested_source()
        payload[table][0]['data_environment'] = 'REAL'
        before = ledger.state()
        with pytest.raises(DomainError) as failure:
            ledger.apply(payload)
        assert failure.value.code == 3
        assert any(i['code'] == 'MIXED_DATA_ENVIRONMENT' for i in failure.value.result['issues'])
        assert ledger.state() == before
    finally:
        ledger.connection.close()


def test_synthetic_observation_cannot_replace_real_account(tmp_path):
    ledger = Ledger(tmp_path / 'real.db')
    try:
        ledger.apply(source('REAL'))
        payload = source('SYNTHETIC')
        payload.update(source_timestamp='2026-03-02', source_hash='fictional-new-source')
        before = ledger.state()
        with pytest.raises(DomainError) as failure:
            ledger.apply(payload)
        assert failure.value.code == 3
        assert any(i['code'] == 'MIXED_DATA_ENVIRONMENT' for i in failure.value.result['issues'])
        assert ledger.state() == before
    finally:
        ledger.connection.close()
