"""A numeric snapshot cell never attests independent cash coverage."""

import pytest

from invest.ledger import Ledger
from invest.planning import propose, save_policy
from invest.targets import save


def observation(day, cash, *, known=True):
    payload = {
        'account': {'id': 'ira', 'name': 'Fictional cash evidence account',
                    'tax_status': 'TAX_FREE'},
        'positions': [], 'lots': [], 'cash': cash,
        'positions_complete': True, 'lots_complete': True,
        'source_timestamp': day, 'source_hash': f'fictional-cash-{day}-{cash}',
        'data_environment': 'SYNTHETIC',
    }
    if known is not None:
        payload['cash_known'] = known
    return payload


@pytest.fixture
def ledger(tmp_path):
    result = Ledger(tmp_path / 'cash.db')
    result.apply(observation('2026-10-01', '500'))
    yield result
    result.connection.close()


@pytest.mark.parametrize('known', [None, False])
def test_partial_numeric_zero_preserves_accepted_cash_and_reports_unknown(ledger, known):
    partial = observation('2026-10-10', '0', known=known)
    preview = ledger.reconcile(partial)
    assert {'kind': 'cash', 'status': 'UNKNOWN_VALUE'} in preview['observations']
    result = ledger.apply(partial)
    assert result['evidence_complete'] is False
    balance = ledger.rows('cash_balances')[0]
    assert balance['amount'] == '500'
    assert balance['as_of'] == '2026-10-01'
    assert ledger.rows('snapshots')[-1]['cash_known'] is False


def test_explicitly_attested_zero_replaces_accepted_cash(ledger):
    result = ledger.apply(observation('2026-10-10', '0'))
    assert result['evidence_complete'] is True
    assert ledger.rows('cash_balances')[0]['amount'] == '0'
    assert ledger.rows('cash_balances')[0]['as_of'] == '2026-10-10'


def test_unattested_zero_cannot_refresh_cash_for_a_saved_policy_proposal(ledger):
    ledger.apply(observation('2026-10-10', '0', known=None))
    sid = ledger.register_security({
        'ticker': 'FICTION', 'name': 'Fictional cash destination', 'asset_type': 'STOCK',
        'currency': 'USD', 'source': 'Reviewed fictional identity',
        'data_environment': 'SYNTHETIC',
    })['id']
    target = save(ledger, {
        'name': 'Fictional cash target', 'data_environment': 'SYNTHETIC',
        'target_allocations': {sid: '1'},
        'planning_constraints': {'eligible_accounts': ['ira']},
    })
    policy = save_policy(ledger, {
        'version': 'fictional-cash-coverage', 'data_environment': 'SYNTHETIC',
        'source': 'Reviewed fictional policy', 'max_cash_age_days': 1,
        'minimum_notional': '0', 'fee_per_trade': '0',
        'permissions': {'ira': {sid: {'can_buy': True, 'can_sell': False,
                                      'can_hold': True, 'share_increment': '1'}}},
    }, confirm=True)
    before = ledger.state()
    result = propose(ledger, target['id'], policy=policy['id'],
                     mode='contributions-only', as_of='2026-10-10', prices={sid: {
                         'price': '100', 'as_of': '2026-10-10', 'currency': 'USD',
                         'data_environment': 'SYNTHETIC', 'source': 'Fictional reviewed price',
                     }})
    assert result['status'] == 'BLOCKED'
    assert result['proposed_actions'] == []
    assert 'STALE_CASH' in {issue['code'] for issue in result['issues']}
    assert ledger.state() == before
