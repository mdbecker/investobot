"""User-visible fund diligence behavior, exclusively fictional offline evidence."""

import copy
import json
from decimal import Decimal
from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when
from typer.testing import CliRunner

from invest.cli import app
from invest.ledger import Ledger

scenarios('features/fund_diligence.feature')


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    path = tmp_path / 'selected.db'
    monkeypatch.setenv('INVEST_DB', str(path))
    return {'runner': CliRunner(), 'path': path, 'directory': tmp_path,
            'file': tmp_path / 'fund.json', 'package': json.loads(
                (Path(__file__).parent / 'fixtures/fund_diligence.json').read_text())}


def invoke(ctx, args, code=0):
    result = ctx['runner'].invoke(app, args)
    assert result.exit_code == code, result.stderr
    assert 'No such command' not in result.stderr, result.stderr
    if code:
        assert not result.stdout
    return json.loads(result.stdout if code == 0 else result.stderr)


def research(ctx, command, *args, code=0):
    # Invalid inputs must exercise a real command, never count a missing command as rejection.
    help_result = ctx['runner'].invoke(app, ['research', 'funds', '--help'])
    assert help_result.exit_code == 0, help_result.stderr
    ctx['file'].write_text(json.dumps(ctx['package']))
    return invoke(ctx, ['research', 'funds', command, *map(str, args)], code)


def accept(ctx):
    result = research(ctx, 'import', ctx['file'], '--yes')
    ctx['run'] = result['run_id']
    return result


def metric(ctx, code, value, unit='PCT', scope='CLASS', **kwargs):
    row = dict(id=code.lower(), code=code, value=value, unit=unit, scope=scope,
               period_start=None, period_end=None, observed_as_of='2026-09-20',
               waiver_end_date=None, source_id='prospectus', source_locator=code,
               notes='Explicitly reported fictional disclosure.')
    row.update(kwargs)
    ctx['package']['metrics'].append(row)


def mutual(ctx):
    ctx['package']['fund'].update(fund_type='MUTUAL_FUND', exchange=None)


def output_metrics(ctx):
    return {row['code']: row for row in ctx['summary']['metrics']}


def all_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from all_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from all_keys(child)


@given('the bundled Investobot research skills')
def bundled(ctx):
    ctx['skills'] = invoke(ctx, ['research', 'skills', 'list'])['skills']


@when('they are installed for Codex or Claude Code')
def installed(ctx):
    for agent, folder in [('codex', '.agents'), ('claude-code', '.claude')]:
        invoke(ctx, ['research', 'skills', 'install', '--agent', agent,
                     '--workspace', str(ctx['directory'])])
        assert (ctx['directory'] / folder / 'skills/investobot-fund-diligence/SKILL.md').is_file()
    modified = ctx['directory'] / '.agents/skills/investobot-earnings/SKILL.md'
    modified.write_text('User customized research instructions')
    ctx['modified'] = modified
    invoke(ctx, ['research', 'skills', 'install', '--agent', 'codex',
                 '--workspace', str(ctx['directory'])], code=1)


@then('fund diligence guidance and its authoritative JSON contract are discoverable')
def discovered(ctx):
    skill = invoke(ctx, ['research', 'skills', 'show', 'investobot-fund-diligence'])
    assert skill['skill_version'] == '1.0.0'
    assert {'SKILL.md', 'references/research-method.md', 'references/fees-and-tax.md',
            'references/holdings-liquidity.md', 'references/json-contract.md'} <= skill['files'].keys()
    assert 'invest schema' in '\n'.join(skill['files'].values())
    tool = invoke(ctx, ['tools', 'describe', 'research.funds.import'])
    assert tool['mutation_scope'] == 'research'
    assert tool['json_input_schema']['additionalProperties'] is False


@then('existing customized skills remain untouched')
def customized(ctx):
    assert ctx['modified'].read_text() == 'User customized research instructions'
    assert len(ctx['skills']) >= 6


@given('the same SEC fund series has Class A and Class I shares')
def classes(ctx):
    mutual(ctx)
    ctx['package']['fund'].update(class_id='C000000124', class_name='Class I')
    ctx['package']['sources'][0]['class_id'] = 'C000000124'


@given('a fee table is reported only for Class A')
def class_a(ctx):
    ctx['package']['sources'][1]['class_id'] = 'C000000123'
    ctx['package']['sources'][2]['class_id'] = None


@when('Class I research is validated')
def class_validate(ctx):
    ctx['error'] = research(ctx, 'validate', ctx['file'], code=1)


@then('Class A fees cannot be reported as Class I fees')
def wrong_class(ctx):
    assert 'class' in ctx['error']['error'].lower()
    assert not ctx['path'].exists()


@given('a registrant offers two different funds')
def two_funds(ctx):
    assert ctx['package']['fund']['series_id']


@when("one fund's holdings are attributed to the other series")
def wrong_series(ctx):
    ctx['package']['sources'][2]['series_id'] = 'S000000999'
    ctx['error'] = research(ctx, 'import', ctx['file'], '--yes', code=1)


@then('the unsupported research is rejected before acceptance')
def rejected_series(ctx):
    assert 'series' in ctx['error']['error'].lower()
    assert not ctx['path'].exists()


@given('a mutual-fund class reports a 0.60% net expense ratio and a 3% front load')
def loads(ctx):
    mutual(ctx)
    ctx['package']['metrics'][0]['value'] = '0.60'
    metric(ctx, 'MAX_FRONT_LOAD', '3')


@when('its research summary is requested')
@when('its research is summarized')
@when('its method is summarized')
@when('its diligence summary is requested')
@when('its tax evidence is summarized')
@when('its summary is requested')
def summarized(ctx):
    accept(ctx)
    ctx['summary'] = research(ctx, 'summary', ctx['run'])


@then('the two fee types remain separately labeled and sourced')
def separate_fees(ctx):
    rows = output_metrics(ctx)
    assert Decimal(rows['NET_EXPENSE_RATIO']['value']) == Decimal('0.60')
    assert Decimal(rows['MAX_FRONT_LOAD']['value']) == Decimal('3')
    assert rows['NET_EXPENSE_RATIO']['source_id'] == rows['MAX_FRONT_LOAD']['source_id'] == 'prospectus'


@then('they are not added into a fabricated annual fee')
def no_fee_total(ctx):
    assert not {'annual_fee_total', 'combined_expense_ratio'} & set(all_keys(ctx['summary']))
    assert '3.6' not in {row['value'] for row in ctx['summary']['metrics']}


@given('an ETF reports a 0.25% gross expense ratio and 0.15% net ratio with a dated waiver')
def waiver(ctx):
    metric(ctx, 'GROSS_EXPENSE_RATIO', '0.25')
    ctx['package']['metrics'][0].update(waiver_end_date='2027-09-20',
                                      notes='Contractual fee waiver expires 2027-09-20.')


@then('both ratios and the waiver expiry remain visible')
def waiver_visible(ctx):
    rows = output_metrics(ctx)
    assert Decimal(rows['GROSS_EXPENSE_RATIO']['value']) == Decimal('0.25')
    assert Decimal(rows['NET_EXPENSE_RATIO']['value']) == Decimal('0.15')
    assert rows['NET_EXPENSE_RATIO']['waiver_end_date'] == '2027-09-20'


@given('an ETF publishes two top positions weighing 6% and 4%')
def top_two(ctx):
    for row, weight in zip(ctx['package']['holdings'], ['6', '4']):
        row['weight_pct'] = weight


@when('its holdings are inspected')
def inspected(ctx):
    accept(ctx)
    ctx['holdings'] = research(ctx, 'holdings', ctx['run'])


@then('reported weight totals 10%')
def total(ctx):
    assert Decimal(ctx['holdings']['observed_weight_sum_pct']) == Decimal('10')


@then('the other 90% is not assigned to fabricated holdings')
def no_fabricated(ctx):
    assert len(ctx['holdings']['holdings']) == 2
    assert ctx['holdings'].get('unreported_residual_pct') is None
    assert ctx['holdings']['coverage'] == 'TOP_N'


@then('full-portfolio top-ten concentration remains unavailable')
def no_top_ten(ctx):
    assert ctx['holdings']['largest_10_observed_weight_pct'] is None
    assert ctx['holdings']['warnings']


@given('an index fund names its index but does not disclose reconstitution rules')
def unknown_rules(ctx):
    assert ctx['package']['methodology']['index_name']
    ctx['package']['methodology']['reconstitution_policy'] = None


@then('the index remains identified with source evidence')
def index(ctx):
    assert ctx['summary']['methodology']['index_name'] == ctx['package']['methodology']['index_name']
    assert ctx['summary']['methodology']['source_ids'] == ['prospectus']


@then('the absent reconstitution method remains unknown')
def unknown_method(ctx):
    assert ctx['summary']['methodology']['reconstitution_policy'] is None
    assert ctx['summary']['methodology']['uncertainty']


@given('a mutual fund reports 18% annual portfolio turnover')
def turnover(ctx):
    mutual(ctx)
    metric(ctx, 'PORTFOLIO_TURNOVER', '18', scope='SERIES',
           period_start='2025-01-01', period_end='2025-12-31', observed_as_of=None)


@then('18% is shown as portfolio turnover with its fiscal period')
def turnover_visible(ctx):
    row = output_metrics(ctx)['PORTFOLIO_TURNOVER']
    assert Decimal(row['value']) == 18
    assert (row['period_start'], row['period_end']) == ('2025-01-01', '2025-12-31')


@then('not as ETF daily trading volume')
def not_volume(ctx):
    assert 'AVG_DAILY_DOLLAR_VOLUME' not in output_metrics(ctx)


@given('an ETF has a disclosed 0.08% median bid-ask spread')
def spread(ctx):
    metric(ctx, 'MEDIAN_BID_ASK_SPREAD', '0.08', period_start='2026-08-20',
           period_end='2026-09-20')


@given('a mutual fund deals at end-of-day NAV with a redemption restriction')
def nav(ctx):
    ctx['etf'] = copy.deepcopy(ctx['package'])
    mutual(ctx)
    ctx['package']['metrics'] = ctx['package']['metrics'][:1]
    ctx['package']['findings'].append(dict(id='nav', category='LIQUIDITY',
        fact='Deals at end-of-day NAV; redemption restricted for seven days.',
        interpretation=None, uncertainty='Terms may change.', source_ids=['prospectus'],
        source_locator='Redemption terms'))


@when('their respective research summaries are requested')
def respective(ctx):
    summarized(ctx)
    ctx['mutual_summary'] = ctx['summary']
    ctx['package'] = ctx['etf']
    summarized(ctx)


@then('each retains its own trading or redemption characteristics')
def characteristics(ctx):
    assert Decimal(output_metrics(ctx)['MEDIAN_BID_ASK_SPREAD']['value']) == Decimal('0.08')
    assert 'end-of-day NAV' in json.dumps(ctx['mutual_summary'])
    assert 'MEDIAN_BID_ASK_SPREAD' not in json.dumps(ctx['mutual_summary'])


@then('no shared liquidity score is invented')
def no_score(ctx):
    assert 'liquidity_score' not in set(all_keys(ctx['summary']))
    assert 'liquidity_score' not in set(all_keys(ctx['mutual_summary']))


@given('a fund reports a 0.40 USD-per-share capital gain distribution')
def distribution(ctx):
    metric(ctx, 'LONG_TERM_CAPITAL_GAIN_DISTRIBUTION', '0.40', unit='USD_PER_SHARE',
           period_end='2026-09-15', observed_as_of=None, notes='Payable date 2026-09-15.')


@then('the historical distribution and source date are shown')
def distribution_visible(ctx):
    row = output_metrics(ctx)['LONG_TERM_CAPITAL_GAIN_DISTRIBUTION']
    assert Decimal(row['value']) == Decimal('0.40')
    assert row['period_end'] == '2026-09-15' and row['source_id'] == 'prospectus'
    assert row['unit'] == 'USD_PER_SHARE'


@then('no investor tax bill or after-tax return is calculated')
def no_personal_tax(ctx):
    assert not {'investor_tax', 'tax_bill', 'after_tax_return', 'tax_efficiency_score'} & set(all_keys(ctx['summary']))


@given('a partial research run finds no distribution history')
def absent_distributions(ctx):
    ctx['package']['limitations'].append('Distribution history unavailable.')


@then('the distribution history is unavailable')
def unavailable(ctx):
    assert not any('DISTRIBUTION' in row['code'] for row in ctx['summary']['metrics'])
    assert 'Distribution history unavailable.' in ctx['summary']['limitations']


@then('the fund is not labeled tax-free or tax-efficient by default')
def no_assumed_tax(ctx):
    assert not {'tax_free', 'tax_efficient', 'tax_efficiency_score'} & set(all_keys(ctx['summary']))


@given('a valid fictional ETF diligence package')
def valid(ctx):
    assert ctx['package']['fund']['fund_type'] == 'ETF'


@when('it is validated and previewed')
def preview(ctx):
    assert research(ctx, 'validate', ctx['file'])['valid']
    result = research(ctx, 'import', ctx['file'])
    assert result['status'] == 'PREVIEW' and result['committed'] is False
    assert result['mutation_scope'] == 'research'


@then('no persistent research database is created')
def no_db(ctx):
    assert not ctx['path'].exists()


@given('one accepted fictional fund research package')
def accepted(ctx):
    accept(ctx)
    ctx['first_run'] = ctx['run']
    ctx['original'] = research(ctx, 'show', ctx['run'])


@when('reordered but otherwise equivalent evidence is accepted again')
def reordered(ctx):
    for key in ['sources', 'metrics', 'findings', 'limitations']:
        ctx['package'][key].reverse()
    ctx['package']['metrics'][0]['value'] += '00'
    ctx['repeat'] = accept(ctx)


@then('no duplicate historical run is created')
def duplicate(ctx):
    assert ctx['repeat']['status'] == 'UNCHANGED'
    assert ctx['run'] == ctx['first_run']
    assert len(research(ctx, 'list')['runs']) == 1


@then('a genuine correction creates a separate immutable run')
def corrected(ctx):
    ctx['package']['limitations'].append('New source-reviewed limitation.')
    accept(ctx)
    assert ctx['run'] != ctx['first_run']
    assert len(research(ctx, 'list')['runs']) == 2
    assert research(ctx, 'show', ctx['first_run']) == ctx['original']


@given('a fund package contains an invalid same-run source reference')
def invalid_source(ctx):
    ctx['package']['metrics'][0]['source_id'] = 'missing-source'


@when('acceptance is attempted')
def attempt(ctx):
    ctx['error'] = research(ctx, 'import', ctx['file'], '--yes', code=1)


@then('no fund profile, holding, metric or finding is saved')
def atomic(ctx):
    assert 'source' in ctx['error']['error'].lower()
    assert not ctx['path'].exists()


@given('accepted household positions and a saved plan')
def household(ctx):
    from test_plans_v2 import setup

    from invest.market import MarketClient
    from invest.plan_storage import load_plan
    from invest.plans import generate
    from invest.targets import save

    db = Ledger(ctx['path'])
    portfolio = {'ledger': db}
    setup(portfolio, 'TAX_FREE')
    target = save(db, portfolio['payload'])
    client = MarketClient(db, fixture_path=Path('tests/fixtures/fmp-synthetic.json'))
    plan = generate(db, client, target['id'], as_of='2026-10-08')
    ctx['plan_id'] = plan['id']
    ctx['financial_before'] = db.planning_state()
    ctx['state_before'] = db.state()
    ctx['plan_before'] = load_plan(db, plan['id'])
    ctx['cache_before'] = [tuple(row) for row in db.connection.execute('SELECT * FROM fund_holdings_cache')]
    db.connection.close()


@when('separate fund diligence is accepted')
def separate_accept(ctx):
    accept(ctx)


@then('positions, cached holdings and planning freshness are unchanged')
def unchanged(ctx):
    from invest.plan_storage import load_plan

    db = Ledger(ctx['path'])
    assert db.planning_state() == ctx['financial_before']
    assert db.state() == ctx['state_before']
    assert load_plan(db, ctx['plan_id']) == ctx['plan_before']
    assert [tuple(row) for row in db.connection.execute('SELECT * FROM fund_holdings_cache')] == ctx['cache_before']
    db.connection.close()


@when('its historical details and reports are read')
def reads(ctx):
    ctx['before_bytes'] = ctx['path'].read_bytes()
    for command in ['show', 'summary', 'holdings']:
        assert research(ctx, command, ctx['run'])
    assert research(ctx, 'list')['runs']


@then('the accepted ledger bytes remain unchanged')
def bytes_unchanged(ctx):
    assert ctx['path'].read_bytes() == ctx['before_bytes']
