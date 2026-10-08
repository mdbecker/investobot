from decimal import Decimal
from pathlib import Path
import pytest
from pytest_bdd import scenarios, given, when, then
scenarios('features/exposure.feature')
@pytest.fixture
def ctx(tmp_path):
    from invest.ledger import Ledger
    from invest.market import MarketClient
    return {'client': MarketClient(Ledger(tmp_path/'db'),fixture_path=Path('tests/fixtures/fmp-synthetic.json')), 'state':{'positions':[], 'cash_balances':[], 'securities':[]}}

def position(symbol, value, asset='ETF', account='tax'):
    return {'security':symbol,'security_id':symbol,'account_id':account,'market_value':str(value),'asset_type':asset,'quantity':'10'}
@given('direct Apple shares and two synthetic funds in different accounts')
def full(ctx):
    ctx['state']['positions']=[position('AAPL',100,'STOCK'),position('AAA',1000),position('BBB',1000,account='ira')]
    ctx['state']['securities']=[{'id':'AAPL','ticker':'AAPL','isin':'US0378331005','asset_type':'STOCK'}]
@when('I compute household exposure')
def expose(ctx):
    from invest.analytics import exposure
    ctx['result']=exposure(ctx['state'],ctx['client'])
@then('Apple direct and indirect value are combined')
def combined(ctx):
    apple=next(r for r in ctx['result']['exposures'] if r['ticker']=='AAPL')
    assert Decimal(apple['direct_value'])==100
    assert Decimal(apple['indirect_value'])==900
    assert Decimal(apple['total_value'])==1000
    assert len(apple['contributions'])==3
    assert Decimal(ctx['result']['unknown_exposure_value'])==0
@then('known sector values are aggregated')
def sectors(ctx):
    assert Decimal(ctx['result']['by_sector']['Technology'])==1500
@given('a fund with twenty percent available holdings and household cash')
def partial(ctx):
    ctx['state']['positions']=[position('PART',1000)]
    ctx['state']['cash_balances']=[{'account_id':'bank','amount':'500'}]
@then('eighty percent of the fund remains unknown')
def unknown(ctx):
    assert Decimal(ctx['result']['unknown_exposure_value'])==800
    assert Decimal(ctx['result']['unknown_exposure_percentage'])==Decimal(800)/Decimal(1500)*100
@then('cash remains visible')
def cash(ctx):
    assert Decimal(next(r for r in ctx['result']['exposures'] if r['ticker']=='CASH')['total_value'])==500
@given('a fund without holdings and an unsupported position')
def absent(ctx):
    ctx['state']['positions']=[position('MISSING',1000),position('OPTION',200,'OTHER')]
@then('all invested value is unknown')
def all_unknown(ctx):
    assert Decimal(ctx['result']['unknown_exposure_value'])==1200
@given('a fund with provider weights exceeding one hundred percent')
def excessive(ctx):
    import json
    fixture=ctx['client'].fixture_path.parent/'fmp-synthetic.json'
    data=json.loads(fixture.read_text())
    data['holdings']['EXCESS']=[{'asset':'AAPL','weightPercentage':'120'}]
    target=ctx['client'].ledger.path.parent/'fixture.json'
    target.write_text(json.dumps(data))
    ctx['client'].fixture_path=target
    ctx['state']['positions']=[position('EXCESS',1000)]
@then('the inconsistent fund remains unknown')
def no_inflate(ctx):
    assert Decimal(ctx['result']['unknown_exposure_value'])==1000
    assert ctx['result']['warnings']
