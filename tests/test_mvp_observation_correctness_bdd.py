"""Observable synthetic reconciliation contracts; source evidence is fictional."""
import copy
from decimal import Decimal

import pytest
from pytest_bdd import given, scenarios, then, when

from invest.ledger import Ledger
from invest.models import DomainError

scenarios('features/mvp/observation_correctness.feature')


@pytest.fixture
def ctx(tmp_path):
    selected = Ledger(tmp_path / 'fictional.db')
    yield {'ledger': selected}
    selected.connection.close()


@given('accepted fictional holdings and cash')
def accepted(ctx):
    snapshot = {'account': {'id': 'fictional', 'name': 'Fictional IRA', 'tax_status': 'TAX_FREE'},
        'positions': [{'security': 'OLD', 'isin': 'FICTIONAL-ISIN', 'asset_type': 'STOCK',
            'quantity': '10', 'price': '100', 'market_value': '1000', 'cost_basis': '800',
            'as_of': '2026-10-08', 'displayed_price_precision': 2,
            'displayed_market_value_precision': 2}],
        'lots': [{'id': 'fictional-lot', 'security': 'OLD', 'quantity': '10',
            'remaining_quantity': '10', 'cost_basis': '800', 'acquisition_date': '2024-01-01'}],
        'cash': '500', 'source_hash': 'fictional-original', 'source_timestamp': '2026-10-08',
        'positions_complete': True, 'lots_complete': True, 'data_environment': 'SYNTHETIC'}
    ctx['ledger'].apply(snapshot)
    ctx['before'] = copy.deepcopy(ctx['ledger'].state())
    ctx['snapshot'] = copy.deepcopy(snapshot)
    ctx['snapshot'].update(source_hash='fictional-later', source_timestamp='2026-10-09')


@when('a purchase of two unmarked shares is confirmed')
def buy(ctx):
    ctx['ledger'].register_security({'ticker': 'UNMARKED', 'name': 'Fictional shares',
        'asset_type': 'STOCK', 'currency': 'USD', 'source': 'Reviewed fictional identity'})
    ctx['ledger'].record_activity({'activity_id': 'fictional-buy', 'account_id': 'fictional',
        'type': 'BUY', 'security': 'UNMARKED', 'quantity': '2', 'price': '10', 'fee': '0',
        'date': '2026-10-09'}, yes=True)


@given('a sourced position has known quantity and market value but no observed price')
def absent_observed_price(ctx):
    ctx['snapshot']['positions'][0].update(price=None, quantity='11', market_value='1100')
    ctx['snapshot']['issues'] = [{'code': 'PROVISIONAL_ADAPTER',
        'message': 'Fictional source awaits original review', 'blocks_acceptance': False,
        'blocks_calculation': False, 'blocks_proposals': True, 'blocks_execution_review': True}]


@given('its printed precision metadata is present')
def printed_precision(ctx):
    ctx['snapshot']['positions'][0].update(displayed_price_precision=2,
                                          displayed_market_value_precision=2)


@when('the incomplete valuation snapshot is reconciled')
def reconcile_incomplete_valuation(ctx):
    ctx['preview'] = ctx['ledger'].reconcile(ctx['snapshot'])


@then('missing price is a typed source issue and other review observations remain visible')
def missing_price_issue(ctx):
    result = ctx['preview']
    issue = next(issue for issue in result['issues'] if issue['code'] == 'INCOMPLETE_POSITION_VALUATION')
    assert issue['security'] == 'OLD'
    assert issue['blocks_acceptance'] is True
    assert result['status'] == 'REVIEW_REQUIRED'
    assert ctx['snapshot']['issues'][0] in result['issues']
    assert result['value_checks'] == []
    assert any(change['kind'] == 'quantity' for change in result['changes'])
    assert ctx['snapshot']['positions'][0]['price'] is None


@then('reconciliation leaves accepted state unchanged')
def reconciliation_unchanged(ctx):
    assert ctx['ledger'].state() == ctx['before']


@then('summary reports partial valuation with the known subtotal')
def partial_summary(ctx):
    before = ctx['ledger'].state()
    result = ctx['ledger'].summary()
    assert result['status'] == 'PARTIAL' and result['total_value'] is None
    assert Decimal(result['known_value_subtotal']) == 1480
    assert 'MISSING_VALUATION_MARK' in {i['code'] for i in result['issues']}
    assert ctx['ledger'].state() == before


@when('the later complete snapshot changes the ticker with the same ISIN')
def rename(ctx):
    ctx['snapshot']['positions'][0]['security'] = 'NEW'
    ctx['snapshot']['lots'][0]['security'] = 'NEW'
    ctx['preview'] = ctx['ledger'].reconcile(ctx['snapshot'])


@then('reconciliation shows metadata instead of liquidation and acceptance retains identity')
def canonical(ctx):
    changes = ctx['preview']['changes']
    assert not any(c['kind'] in {'removed_position', 'new_position'} for c in changes)
    assert any(c['kind'] == 'ticker' and c['before'] == 'OLD' and c['after'] == 'NEW'
               for c in changes)
    assert ctx['ledger'].state() == ctx['before']
    ctx['ledger'].apply(ctx['snapshot'])
    state = ctx['ledger'].state()
    assert len(state['positions']) == 1
    assert state['positions'][0]['security_id'] == ctx['before']['positions'][0]['security_id']
    assert state['lots'][0]['id'] == 'fictional-lot'


@when('a partial snapshot has provisional and unverified lot issues')
def provisional(ctx):
    ctx['snapshot'].update(positions_complete=False, lots_complete=False, lots=[],
        institution_status='PROVISIONAL', issues=[{'code': code, 'message': 'Fictional source review',
            'blocks_acceptance': False, 'blocks_calculation': False,
            'blocks_proposals': True, 'blocks_execution_review': True}
            for code in ('PROVISIONAL_ADAPTER', 'UNVERIFIED_LOT_IDENTITY')])
    ctx['preview'] = ctx['ledger'].reconcile(ctx['snapshot'])


@then('every typed issue survives and eligible evidence remains explicitly partial')
def issues(ctx):
    assert ctx['preview']['issues'] == ctx['snapshot']['issues']
    assert ctx['preview']['status'] == 'REVIEW_REQUIRED'
    assert ctx['ledger'].state() == ctx['before']
    result = ctx['ledger'].apply(ctx['snapshot'])
    assert result['issues'] == ctx['snapshot']['issues']
    assert result['status'] == 'APPLIED' and result['evidence_complete'] is False
    repeated = ctx['ledger'].apply(ctx['snapshot'])
    assert repeated['issues'] == result['issues']
    assert repeated['evidence_complete'] is False


@when('a partial snapshot omits positions lots and cash')
def missing(ctx):
    ctx['snapshot'].update(positions=[], lots=[], positions_complete=False, lots_complete=False,
                           cash_known=False)
    ctx['accepted_partial'] = ctx['ledger'].apply(ctx['snapshot'])


@then('accepted inventory cash and lots remain and repeat is idempotent')
def preserved(ctx):
    assert ctx['accepted_partial']['evidence_complete'] is False
    state = ctx['ledger'].state()
    for key in ('positions', 'lots', 'cash_balances'):
        assert state[key] == ctx['before'][key]
    assert ctx['ledger'].apply(ctx['snapshot'])['status'] == 'UNCHANGED'
    assert ctx['ledger'].state() == state


@when('a snapshot conflicts with the held strong identity')
def conflict(ctx):
    ctx['snapshot']['positions'][0]['isin'] = 'CONFLICTING-ISIN'


@when('source values exceed their printed precision tolerance')
def precision(ctx):
    ctx['snapshot']['positions'][0]['market_value'] = '1100'


@then('acceptance is blocked without mutation')
def blocked(ctx):
    with pytest.raises(DomainError) as error:
        ctx['ledger'].apply(ctx['snapshot'])
    assert error.value.code == 3
    assert ctx['ledger'].state() == ctx['before']


@when('a large exact mark and two cents cash are accepted')
def large_mark(ctx):
    position = ctx['snapshot']['positions'][0]
    position.update(price='100000000000000000000000000000.001',
        market_value='1000000000000000000000000000000.01', displayed_price_precision=3)
    ctx['snapshot']['cash'] = '0.02'
    ctx['ledger'].apply(ctx['snapshot'])


@then('summary retains every cent in totals and known gain')
def exact_summary(ctx):
    from fractions import Fraction

    before = ctx['ledger'].state()
    result = ctx['ledger'].summary()
    expected = Fraction('1000000000000000000000000000000.01') + Fraction('0.02')
    assert Fraction(result['total_value']) == expected
    assert Fraction(result['known_value_subtotal']) == expected
    assert Fraction(result['by_account']['fictional']) == expected
    assert Fraction(result['unrealized_gain_loss_known_basis']) == expected - Fraction('0.02') - 800
    assert ctx['ledger'].state() == before
