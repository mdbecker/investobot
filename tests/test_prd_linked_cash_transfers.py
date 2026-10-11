"""Explicit linked cash transfer CLI preserves both accounts and actual performance."""

import copy
import json
from decimal import Decimal

import pytest
from typer.testing import CliRunner

from invest.cli import app
from invest.ledger import Ledger


@pytest.fixture
def context(tmp_path, monkeypatch):
    path = tmp_path / 'transfers.db'
    monkeypatch.setenv('INVEST_DB', str(path))
    ledger = Ledger(path)
    yield {'ledger': ledger, 'runner': CliRunner(), 'root': tmp_path}
    ledger.connection.close()


def checkpoint(ctx, account, cash='1000', timestamp='2026-03-01', *, currency='USD',
               environment='SYNTHETIC', cash_known=True):
    return ctx['ledger'].apply({'account': {'id': account, 'name': 'Fictional ' + account,
        'currency': currency, 'tax_status': 'TAX_FREE', 'history_complete': True},
        'positions': [], 'lots': [], 'cash': cash, 'cash_known': cash_known,
        'source_timestamp': timestamp, 'positions_complete': True, 'lots_complete': True,
        'data_environment': environment, 'source_hash': f'{account}:{cash}:{timestamp}'})


def household(ctx):
    checkpoint(ctx, 'from')
    checkpoint(ctx, 'to')


def payload(**changes):
    return {'transfer_id': 'fictional-transfer-001', 'from_account_id': 'from',
        'to_account_id': 'to', 'amount': '100', 'currency': 'USD',
        'data_environment': 'SYNTHETIC', 'event_timestamp': '2026-03-02T12:00:00Z',
        'source': 'Human-reviewed fictional paired bank transfer notice', **changes}


def invoke(ctx, data, *, confirm=False):
    file = ctx['root'] / 'transfer.json'
    file.write_text(json.dumps(data))
    return ctx['runner'].invoke(app, ['portfolio', 'record-cash-transfer', '--file', str(file),
                                    *(['--confirm'] if confirm else [])])


def success(result):
    assert result.exit_code == 0, result.stderr
    return json.loads(result.stdout)


def test_transfer_preview_and_confirm_create_exact_atomic_paired_cash_legs(context):
    household(context)
    before = copy.deepcopy(context['ledger'].state())
    preview = success(invoke(context, payload()))
    assert preview['status'] == 'PREVIEW' and preview['committed'] is False
    assert context['ledger'].state() == before
    accepted = success(invoke(context, payload(), confirm=True))
    assert accepted['committed'] is True
    state = context['ledger'].state()
    cash = {row['account_id']: row['amount'] for row in state['cash_balances']}
    assert cash == {'from': '900', 'to': '1100'}
    assert len(state['activities']) == 2
    assert {(row['account_id'], row['type']) for row in state['activities']} == {
        ('from', 'CASH_WITHDRAWAL'), ('to', 'CASH_DEPOSIT')}
    for row in state['activities']:
        assert row['classification'] == 'INTERNAL_TRANSFER'
        assert row['transfer_id'] == 'fictional-transfer-001'
        assert row['amount'] == '100'
        assert row['event_timestamp'] == '2026-03-02T12:00:00Z'
        assert row['data_environment'] == 'SYNTHETIC'


def test_transfer_id_retry_is_noop_and_conflicting_facts_reject_atomically(context):
    household(context)
    success(invoke(context, payload(), confirm=True))
    before = copy.deepcopy(context['ledger'].state())
    assert success(invoke(context, payload(amount='100.00'), confirm=True))['status'] == 'UNCHANGED'
    assert context['ledger'].state() == before
    conflict = invoke(context, payload(amount='101'), confirm=True)
    assert conflict.exit_code == 3
    assert json.loads(conflict.stderr)['issues']
    assert context['ledger'].state() == before


@pytest.mark.parametrize('invalid', ['same_account', 'unknown_account', 'mixed_environment',
    'currency', 'insufficient_cash', 'unknown_cash', 'prior_event', 'undated', 'unknown_field'])
def test_invalid_transfer_rejects_both_legs_without_mutation(context, invalid):
    household(context)
    data = payload()
    if invalid == 'same_account':
        data['to_account_id'] = 'from'
    elif invalid == 'unknown_account':
        data['to_account_id'] = 'absent'
    elif invalid == 'mixed_environment':
        checkpoint(context, 'real', environment='REAL')
        data['to_account_id'] = 'real'
    elif invalid == 'currency':
        checkpoint(context, 'eur', currency='EUR')
        data['to_account_id'] = 'eur'
    elif invalid == 'insufficient_cash':
        data['amount'] = '1001'
    elif invalid == 'unknown_cash':
        checkpoint(context, 'unknown', cash_known=False)
        data['from_account_id'] = 'unknown'
    elif invalid == 'prior_event':
        context['ledger'].record_activity({'activity_id': 'later-confirmed', 'account_id': 'from',
            'type': 'CASH_DEPOSIT', 'date': '2026-03-03',
            'event_timestamp': '2026-03-03T12:00:00Z', 'amount': '1'}, yes=True)
    elif invalid == 'undated':
        data['event_timestamp'] = '2026-03-02'
    else:
        data['unrecognized'] = 'must never be ignored'
    before = copy.deepcopy(context['ledger'].state())
    result = invoke(context, data, confirm=True)
    assert result.exit_code in {1, 3}, result.stdout
    diagnostic = json.loads(result.stderr)
    assert diagnostic.get('issues'), diagnostic
    assert context['ledger'].state() == before


def test_actual_household_transfer_nets_internally_and_accounts_treat_legs_external(context):
    household(context)
    for account in ('from', 'to'):
        checkpoint(context, account, timestamp='2026-03-02T11:00:00Z')
    success(invoke(context, payload(), confirm=True))
    checkpoint(context, 'from', cash='900', timestamp='2026-03-03')
    checkpoint(context, 'to', cash='1100', timestamp='2026-03-03')
    before = copy.deepcopy(context['ledger'].state())
    for account in (None, 'from', 'to'):
        args = ['portfolio', 'performance', '--from', '2026-03-01', '--to', '2026-03-03']
        if account:
            args.extend(['--account', account])
        result = success(context['runner'].invoke(app, args))
        assert result['twr']['status'] == 'AVAILABLE', result
        assert Decimal(str(result['twr']['return'])) == 0
        if account is None:
            assert result['scope'] == 'HOUSEHOLD'
            assert result['net_external_contributions'] == '0'
        else:
            assert result['scope'] == 'ACCOUNT'
            assert result['net_external_contributions'] == ('-100' if account == 'from' else '100')
    assert context['ledger'].state() == before


def test_transfer_command_discovery_states_confirmed_financial_mutation_scope(context):
    result = success(context['runner'].invoke(app, ['tools', 'describe', 'portfolio.record-cash-transfer']))
    assert result['mutation_scope'] == 'actual_portfolio'
    assert result['mutates_persistent_state'] is True
    assert any('--confirm' in option['flags'] for option in result['options'])
    assert not context['ledger'].rows('activities')
