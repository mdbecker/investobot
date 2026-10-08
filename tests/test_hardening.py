import json
from decimal import Decimal
from pathlib import Path
import pytest
from pytest_bdd import scenarios,given,when,then
scenarios('features/hardening.feature')
@pytest.fixture
def ctx(tmp_path,monkeypatch):
    from invest.ledger import Ledger
    monkeypatch.setenv('INVEST_DB',str(tmp_path/'db'))
    monkeypatch.setenv('INVEST_CONFIG',str(tmp_path/'config.toml'))
    return {'ledger':Ledger(tmp_path/'db')}

def snapshot(cash_known=True):
    return {'account':{'id':'synthetic','name':'synthetic'},'positions':[{'security':'OLD','name':'Synthetic company','asset_type':'STOCK','cusip':'SYNTH0001','quantity':'10','market_value':'1000','price':'100','cost_basis':'1200','as_of':'2026-10-08'}],'cash':'500','cash_known':cash_known,'source_hash':'synthetic'}
@given('a snapshot with a CUSIP identified stock')
def existing(ctx):
    ctx['ledger'].apply(snapshot())
    ctx['uuid']=ctx['ledger'].state()['securities'][0]['id']
@when('I apply the same CUSIP under a new ticker')
def rename(ctx):
    snap=snapshot()
    snap['positions'][0]['security']='NEW'
    ctx['ledger'].apply(snap)
@then('the security UUID remains the same')
def identity(ctx):
    assert len(ctx['ledger'].state()['securities'])==1
    assert ctx['ledger'].resolve('NEW')['id']==ctx['uuid']
@then('its CUSIP is stored')
def cusip(ctx):
    assert ctx['ledger'].resolve('SYNTH0001')['id']==ctx['uuid']
@when('I record a confirmed purchase')
def purchase(ctx):
    ctx['ledger'].record_activity({'account_id':'synthetic','security':'OLD','type':'BUY','quantity':'2','price':'100','fee':'1','date':'2026-10-08'},yes=True)
@then('the summary includes the new known basis')
def basis(ctx):
    assert Decimal(ctx['ledger'].summary()['unrealized_gain_loss_known_basis'])==-201
@given('a snapshot without known cash')
def missing(ctx):
    ctx['ledger'].apply(snapshot(False))
@when('I request a summary')
def summary(ctx):
    ctx['result']=ctx['ledger'].summary()
@then('a missing cash warning is visible')
def warnings(ctx):
    assert any('cash' in w.lower() for w in ctx['result']['warnings'])
@given('a synthetic market history source')
def synthetic(ctx,monkeypatch):
    monkeypatch.setenv('INVEST_FIXTURES',str(Path('tests/fixtures/fmp-synthetic.json')))
@when('I request security history from the CLI')
def history(ctx):
    from typer.testing import CliRunner
    from invest.cli import app
    ctx['command']=CliRunner().invoke(app,['market','history','AAA'])
@then('return volatility drawdown and rolling series are supplied')
def metrics(ctx):
    assert ctx['command'].exit_code==0
    data=json.loads(ctx['command'].stdout)
    assert data['analytics']['total_return']==pytest.approx(.089)
    assert data['analytics']['maximum_drawdown']==pytest.approx(-.1)
    assert data['analytics']['annualized_volatility']>0
    assert isinstance(data['analytics']['rolling_returns'],list)
