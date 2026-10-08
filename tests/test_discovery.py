from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from pytest_bdd import given, when, then, scenarios

scenarios('features/discovery.feature')


@pytest.fixture
def context(tmp_path):
    from invest.ledger import Ledger
    return {'ledger': Ledger(tmp_path / 'discovery.db')}


@given('synthetic discovery data')
def fixture_client(context):
    from invest.market import MarketClient
    context['client'] = MarketClient(context['ledger'], fixture_path=Path(__file__).parent / 'fixtures/discovery-synthetic.json')


@when('I screen technology equities above a market capitalization threshold')
def screen_tech(context):
    from invest.discovery import screen
    context['result'] = screen(context['client'], {'sector':'Technology','marketCapMoreThan':'1000000'})


@then('only the matching equity is returned with provenance')
def screened(context):
    assert [r['symbol'] for r in context['result']['candidates']] == ['TECH']
    assert context['result']['source'] == 'SYNTHETIC_FMP_FIXTURE'
    assert context['result']['retrieved_at']


@when('I search ETFs by expense ratio AUM and issuer')
def fund_search(context):
    from invest.discovery import search
    context['result'] = search(context['client'], {'fund_type':'ETF','expense_ratio_max':'0.06','aum_min':'1500000','issuer':'Synthetic One'})


@then('only the qualifying synthetic fund is returned')
def qualifying(context):
    assert [r['symbol'] for r in context['result']['candidates']] == ['SAME']
    assert context['result']['candidates'][0]['expense_ratio'] == '0.05'


@when('I request a profitability filter unavailable in the provider adapter')
def unsupported(context):
    from invest.discovery import screen
    from invest.models import DomainError
    with pytest.raises(DomainError) as exc:
        screen(context['client'], {'profitability_min':'0.2'})
    context['error'] = exc.value


@then('the unsupported filter is an input error')
def input_error(context):
    assert context['error'].code == 1
    assert 'profitability_min' in str(context['error'])


@when('I rank ORIGINAL SAME DIFFERENT and UNKNOWN against ORIGINAL')
def rank(context):
    from invest.discovery import replacements
    context['result'] = replacements(context['client'], 'ORIGINAL', ['ORIGINAL','SAME','DIFFERENT','UNKNOWN'])


@then('SAME ranks above the high correlation low overlap fund')
def rank_metrics(context):
    rows = context['result']['candidates']
    assert [r['ticker'] for r in rows[:2]] == ['SAME','DIFFERENT']
    assert rows[0]['score'] > rows[1]['score']
    assert Decimal(rows[0]['overlap']) == Decimal('0.9')
    assert Decimal(rows[0]['active_share']) == Decimal('0.1')
    assert Decimal(rows[0]['expense_ratio_difference']) == Decimal('-0.05')
    assert rows[1]['historical_return_correlation'] == pytest.approx(1)
    assert Decimal(rows[1]['overlap']) == 0


@then('the original fund is excluded')
def excluded(context):
    assert all(r['ticker'] != 'ORIGINAL' for r in context['result']['candidates'])


@then('unknown metrics remain unavailable')
def unknown(context):
    row = next(r for r in context['result']['candidates'] if r['ticker'] == 'UNKNOWN')
    assert row['status'] == 'DATA_UNAVAILABLE'
    assert row['score'] is None
    assert row['overlap'] is None


@then('the exact tax similarity disclaimer is present')
def disclaimer(context):
    assert context['result']['disclaimer'] == 'This score does not determine whether securities are substantially identical for tax purposes.'


@given('a discovery client whose external provider fails')
def failing(context, monkeypatch):
    from invest.market import MarketClient
    context['client'] = MarketClient(context['ledger'], api_key='synthetic')
    def fail(*args, **kwargs):
        raise httpx.ConnectError('external outage')
    monkeypatch.setattr(httpx, 'get', fail)


@when('I request an equity screen')
def failed_screen(context):
    from invest.discovery import screen
    from invest.models import DomainError
    with pytest.raises(DomainError) as exc:
        screen(context['client'], {})
    context['error'] = exc.value


@then('discovery reports an external data error')
def external_error(context):
    assert context['error'].code == 2


@when('I screen with a negative price bound')
def invalid(context):
    from invest.discovery import screen
    from invest.models import DomainError
    with pytest.raises(DomainError) as exc:
        screen(context['client'], {'priceMoreThan': '-1'})
    context['error'] = exc.value


@then('the invalid filter is an input error')
def invalid_error(context):
    assert context['error'].code == 1
