import pytest
from pytest_bdd import given, scenarios, then, when

from invest.ledger import Ledger
from invest.market import MarketClient
from invest.models import DomainError
from invest.scenarios import simulate

scenarios('features/transfer_safety.feature')


@pytest.fixture
def ctx(tmp_path):
    return {'ledger': Ledger(tmp_path / 'db')}


@given('loaded taxable and tax free accounts with cash')
def accounts(ctx):
    for name, status in [('taxable', 'TAXABLE'), ('roth', 'TAX_FREE')]:
        ctx['ledger'].apply({'data_environment': 'SYNTHETIC', 'account': {'id': name, 'name': name, 'tax_status': status},
                             'positions': [], 'cash_known': True, 'cash': '100', 'source_hash': name})
    ctx['before'] = ctx['ledger'].state()


@when('a cross tax treatment cash movement is simulated')
def movement(ctx):
    try:
        simulate(ctx['ledger'].state(), MarketClient(ctx['ledger']), [
            {'type': 'MOVE_CASH', 'account_id': 'taxable', 'to_account': 'roth',
             'amount': '50', 'classification': 'CASH_TRANSFER'}])
    except DomainError as exc:
        ctx['error'] = exc


@then('the simulation requires manual review without changing actual state')
def rejected(ctx):
    assert isinstance(ctx.get('error'), DomainError)
    assert ctx['ledger'].state() == ctx['before']
