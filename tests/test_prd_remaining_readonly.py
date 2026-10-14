"""Remaining financial inspections leave an absent selected ledger absent."""

import json

import pytest
from typer.testing import CliRunner

from invest.cli import app


@pytest.fixture
def context(tmp_path, monkeypatch):
    selected = tmp_path / 'absent-fictional-readonly.db'
    fixture = tmp_path / 'fictional-empty-public-data.json'
    fixture.write_text(json.dumps({'history': {}, 'holdings': {}, 'quote': {}}))
    monkeypatch.setenv('INVEST_DB', str(selected))
    monkeypatch.setenv('INVEST_FIXTURES', str(fixture))
    monkeypatch.setenv('INVEST_CONFIG', str(tmp_path / 'absent-config.toml'))
    return {'path': selected, 'directory': tmp_path, 'runner': CliRunner()}


def invoke(context, command, *, success):
    response = context['runner'].invoke(app, command)
    assert not context['path'].exists(), 'Financial inspection must not initialize a selected ledger'
    assert not context['path'].with_name(context['path'].name + '-wal').exists()
    if success:
        assert response.exit_code == 0, response.stderr
        assert response.stderr == ''
        assert isinstance(json.loads(response.stdout), (dict, list))
    else:
        assert response.exit_code in {1, 3}, response.stderr
        assert response.stdout == ''
        assert json.loads(response.stderr)['error']


@pytest.mark.parametrize('command', [
    ['tax', 'lots', '--as-of', '2026-10-10'],
    ['tax', 'harvest-candidates', '--as-of', '2026-10-10'],
    ['portfolio', 'overview'],
], ids=['tax_lots', 'harvest_candidates', 'portfolio_overview'])
def test_empty_portfolio_inspections_do_not_create_selected_database(context, command):
    invoke(context, command, success=True)


def test_tax_analysis_unknown_security_returns_json_without_ledger_creation(context):
    invoke(context, ['tax', 'analyze', '--account', 'fictional-missing', '--security', 'FICTIONAL',
                     '--quantity', '1', '--price', '100', '--sale-date', '2026-10-10'], success=False)


def test_hypothetical_risk_empty_baseline_returns_json_without_ledger_creation(context):
    invoke(context, ['portfolio', 'risk'], success=False)


def test_hypothetical_simulation_unknown_position_does_not_create_ledger(context):
    source = context['directory'] / 'fictional-actions.json'
    source.write_text(json.dumps([{'type': 'BUY', 'account_id': 'fictional-missing',
                                  'security': 'FICTIONAL', 'quantity': '1', 'price': '100',
                                  'fee': '0', 'date': '2026-10-10'}]))
    invoke(context, ['portfolio', 'simulate', str(source)], success=False)


def test_comparing_unknown_immutable_plans_does_not_create_ledger(context):
    invoke(context, ['plan', 'compare', 'fictional-first', 'fictional-second'], success=False)


def test_exporting_unknown_saved_plan_creates_neither_ledger_nor_report(context):
    output = context['directory'] / 'fictional-report.md'
    invoke(context, ['report', 'export', 'fictional-missing', '--output', str(output)], success=False)
    assert not output.exists()
