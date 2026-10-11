import copy

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from invest.ledger import Ledger
from invest.models import DomainError

scenarios('features/sync_v2.feature')


def snapshot():
    return {
        'account': {'id': 'sync', 'name': 'Synthetic', 'tax_status': 'TAXABLE'},
        'positions': [
            {'security': 'AAA', 'cusip': 'C1', 'quantity': '10', 'price': '100',
             'market_value': '1000', 'cost_basis': '800', 'as_of': '2026-10-08', 'displayed_price_precision': 0, 'displayed_market_value_precision': 0},
            {'security': 'BBB', 'isin': 'I2', 'quantity': '5', 'price': '100',
             'market_value': '500', 'as_of': '2026-10-08', 'displayed_price_precision': 0, 'displayed_market_value_precision': 0},
        ],
        'lots': [{'id': 'sync-lot', 'security': 'AAA', 'quantity': '10',
                  'remaining_quantity': '10', 'cost_basis': '800',
                  'acquisition_date': '2024-01-01'}],
        'cash': '500', 'source_hash': 'synthetic-sync',
        'source_timestamp': '2026-10-08', 'positions_complete': True, 'lots_complete': True,
    }


@pytest.fixture
def ctx(tmp_path):
    return {'ledger': Ledger(tmp_path / 'db')}


@given('an accepted complete dated account snapshot')
def accepted(ctx):
    ctx['snap'] = snapshot()
    ctx['ledger'].apply(ctx['snap'])
    ctx['before'] = ctx['ledger'].state()


@when(parsers.parse('the next snapshot changes "{field}" to "{value}"'))
def valuation(ctx, field, value):
    ctx['snap']['positions'][0][field] = value
    ctx['diff'] = ctx['ledger'].reconcile(ctx['snap'])


@then(parsers.parse('reconciliation reports "{field}" as CHANGED_VALUE'))
def changed(ctx, field):
    assert any(c['kind'] == field and c['status'] == 'CHANGED_VALUE'
               for c in ctx['diff']['changes'])


@when('an incomplete snapshot omits a holding and all lots')
def partial(ctx):
    ctx['snap'].update(positions_complete=False, lots_complete=False, lots=[])
    ctx['snap']['positions'] = ctx['snap']['positions'][:1]
    ctx['ledger'].apply(ctx['snap'])


@then('the unobserved holding and previous lots remain')
def retained(ctx):
    assert len(ctx['ledger'].state()['positions']) == 2
    assert len(ctx['ledger'].state()['lots']) == 1


@when('a complete snapshot omits a holding')
def complete(ctx):
    ctx['snap']['positions'] = ctx['snap']['positions'][1:]
    ctx['snap']['lots'] = []
    ctx['ledger'].apply(ctx['snap'])


@then('the absent holding and its lots are removed')
def removed(ctx):
    assert [p['security'] for p in ctx['ledger'].state()['positions']] == ['BBB']
    assert ctx['ledger'].state()['lots'] == []


@when('an incomplete snapshot changes quantity without lots')
def quantity(ctx):
    ctx['snap'].update(lots_complete=False, lots=[])
    ctx['snap']['positions'][0]['quantity'] = '8'
    ctx['ledger'].apply(ctx['snap'])


@then('the updated position has unresolved lot state')
def unresolved(ctx):
    p = next(p for p in ctx['ledger'].state()['positions'] if p['security'] == 'AAA')
    assert p['lot_state'] == 'UNRESOLVED'
    assert len(ctx['ledger'].state()['lots']) == 1


@when('an older snapshot is applied without override')
def older(ctx):
    ctx['snap']['source_timestamp'] = '2026-10-01'
    try:
        ctx['ledger'].apply(ctx['snap'])
    except DomainError as exc:
        ctx['error'] = exc


@then('application conflicts and leaves the ledger unchanged')
def atomic(ctx):
    assert ctx['error'].code == 3
    assert ctx['ledger'].state() == ctx['before']


@when('an older snapshot is applied with a justified override')
def override(ctx):
    ctx['snap']['source_timestamp'] = '2026-10-01'
    ctx['result'] = ctx['ledger'].apply(ctx['snap'], allow_older=True, justification='Corrected source')


@then('the override justification is audited')
def audited(ctx):
    assert any(s.get('override_justification') == 'Corrected source'
               for s in ctx['ledger'].state()['snapshots'])


@when('the identical snapshot is applied again')
def duplicate(ctx):
    ctx['ledger'].apply(copy.deepcopy(ctx['snap']))


@then('there is still one snapshot transition')
def once(ctx):
    assert len(ctx['ledger'].state()['snapshots']) == 1


@when('a snapshot bridges conflicting security identifiers')
def identity(ctx):
    ctx['snap']['positions'][0]['isin'] = 'I2'
    try:
        ctx['ledger'].apply(ctx['snap'])
    except DomainError as exc:
        ctx['error'] = exc


@when('the account classification changes')
def classification(ctx):
    ctx['snap']['account']['tax_status'] = 'TAX_FREE'
    ctx['diff'] = ctx['ledger'].reconcile(ctx['snap'])


@then('reconciliation reports account classification changes')
def classified(ctx):
    assert any(c['kind'] == 'account_classification' for c in ctx['diff']['changes'])
