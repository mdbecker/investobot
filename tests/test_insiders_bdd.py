"""Behavior contracts using only fictional management and filing evidence."""

import copy
import json
from decimal import Decimal
from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when
from typer.testing import CliRunner

from invest.cli import app
from invest.ledger import Ledger

scenarios('features/insiders.feature')


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    path = tmp_path / 'selected.db'
    monkeypatch.setenv('INVEST_DB', str(path))
    return {'runner': CliRunner(), 'path': path, 'directory': tmp_path,
            'file': tmp_path / 'insiders.json',
            'package': json.loads((Path(__file__).parent / 'fixtures/insiders.json').read_text())}


def invoke(ctx, args, code=0):
    result = ctx['runner'].invoke(app, args)
    assert result.exit_code == code, result.stderr
    if code:
        assert not result.stdout
    return json.loads(result.stdout if code == 0 else result.stderr)


def research(ctx, command, *args, code=0):
    ctx['file'].write_text(json.dumps(ctx['package']))
    result = invoke(ctx, ['research', 'insiders', command, *map(str, args)], code)
    if code:
        assert 'no such command' not in result['error'].lower(), result['error']
    return result


def accept(ctx):
    result = research(ctx, 'import', ctx['file'], '--yes')
    ctx['run'] = result.get('run_id', result.get('research_run_id'))
    assert ctx['run']
    return result


@given('a fictional insider package with sourced people')
def package(ctx):
    assert ctx['package']['scope']['coverage_status'] == 'PARTIAL'


@given('bundled investment research skills')
def bundled(ctx):
    ctx['skills'] = invoke(ctx, ['research', 'skills', 'list'])['skills']


@when('insider skills are installed for both agents')
def installed(ctx):
    for agent, folder in [('codex', '.agents'), ('claude-code', '.claude')]:
        invoke(ctx, ['research', 'skills', 'install', '--agent', agent,
                     '--workspace', str(ctx['directory'])])
        assert (ctx['directory'] / folder / 'skills/investobot-management-insiders/SKILL.md').is_file()
    ctx['custom'] = ctx['directory'] / '.agents/skills/investobot-earnings/SKILL.md'
    ctx['custom'].write_text('User customized instructions')
    invoke(ctx, ['research', 'skills', 'install', '--agent', 'codex',
                 '--workspace', str(ctx['directory'])], code=1)


@then('the new method and authoritative contract are available')
def skill_contract(ctx):
    skill = invoke(ctx, ['research', 'skills', 'show', 'investobot-management-insiders'])
    assert skill['skill_version'] == '1.0.0'
    assert {'SKILL.md', 'references/research-method.md', 'references/sec-transaction-codes.md',
            'references/compensation-ownership-rules.md', 'references/json-contract.md'} <= skill['files'].keys()
    assert 'invest schema' in '\n'.join(skill['files'].values())


@then('existing customized skills remain untouched')
def customized(ctx):
    assert ctx['custom'].read_text() == 'User customized instructions'
    assert {'investobot-earnings', 'investobot-news', 'investobot-competitive'} <= {
        entry['name'] for entry in ctx['skills']}


@when('management research is accepted and summarized')
def summary(ctx):
    accept(ctx)
    ctx['summary'] = research(ctx, 'summary', ctx['run'])


@then('historical tenure and entity ownership remain distinguishable')
def people(ctx):
    text = json.dumps(ctx['summary'])
    assert '2026-06-01' in text and 'Former Chief Executive' in text
    assert 'TEN_PERCENT_OWNER' in text and 'ENTITY' in text
    saved = research(ctx, 'show', ctx['run'])
    assert 'Fictional Holdings LLC' in json.dumps(saved)


@given('a transaction without a verified owner CIK')
def unknown_owner(ctx):
    ctx['package']['people'][0]['reporting_owner_cik'] = None


@when('insider validation rejects the package')
def invalid(ctx):
    error = research(ctx, 'validate', ctx['file'], code=1)
    assert 'owner' in error['error'].lower()


@then('no selected database exists')
def absent(ctx):
    assert not ctx['path'].exists()


@when('management activity is accepted and inspected')
def activity(ctx):
    accept(ctx)
    ctx['activity'] = research(ctx, 'activity', ctx['run'])
    ctx['rows'] = ctx['activity']['transactions']


@then('each original SEC code retains its economic category')
def categories(ctx):
    expected = {'P': 'PURCHASE', 'S': 'SALE', 'M': 'OPTION_EXERCISE_OR_CONVERSION',
                'A': 'AWARD_OR_GRANT', 'F': 'TAX_OR_EXERCISE_PAYMENT', 'G': 'GIFT', 'J': 'OTHER'}
    for row in ctx['rows']:
        assert row['transaction_category'] == expected[row['transaction_code']]


@then('option exercises grants and withholding never inflate purchases')
def purchases(ctx):
    counted = [r for r in ctx['rows'] if r['effective'] and r['transaction_category'] == 'PURCHASE']
    assert len(counted) == 1 and Decimal(counted[0]['quantity']) == 100
    assert counted[0]['purchase_venue'] == 'UNKNOWN'


@then('missing trading-plan disclosure remains unknown')
def plan_unknown(ctx):
    assert all(r['rule_10b5_1_status'] == 'NOT_DISCLOSED' for r in ctx['rows'])
    assert not {'intent', 'sentiment', 'score'} & ctx['activity'].keys()


@then('only the corrected sale contributes 120 shares')
def corrected_sale(ctx):
    rows = [r for r in ctx['rows'] if r['effective'] and r['transaction_code'] == 'S']
    assert len(rows) == 1 and Decimal(rows[0]['quantity']) == 120
    assert rows[0]['supersedes_id'] == 'sale'


@then('original duplicate and unresolved rows retain exclusion reasons')
def excluded(ctx):
    indexed = {r['id']: r for r in ctx['rows']}
    for key in ['sale', 'duplicate-sale', 'unresolved']:
        assert indexed[key]['effective'] is False
        assert indexed[key]['exclusion_reason']
    assert '0000000001-26-000004' in json.dumps(ctx['activity'])


@when('accepted ownership is inspected')
def ownership(ctx):
    accept(ctx)
    ctx['ownership'] = research(ctx, 'ownership', ctx['run'])


@then('both dated observations remain visible and latest holdings are 125')
def holdings(ctx):
    assert len(ctx['ownership']['observations']) == 2
    assert len(ctx['ownership']['latest_observations']) == 1
    assert Decimal(ctx['ownership']['latest_observations'][0]['reported_quantity']) == 125
    assert '225' not in json.dumps(ctx['ownership'])


@then('grant-date values retain their basis and reported totals remain separate')
def compensation(ctx):
    groups = ctx['summary']['compensation']
    items = [item for group in groups for item in group['items']]
    stock = next(item for item in items if item['compensation_type'] == 'STOCK_AWARD')
    assert stock['value_basis'] == 'GRANT_DATE_FAIR_VALUE'
    totals = [item for group in groups for item in group['reported_totals']]
    assert len(totals) == 1 and Decimal(totals[0]['value']) == 300000
    assert all(Decimal(item['value']) != 600000 for item in items)


@when('insider research is validated and previewed')
def preview(ctx):
    assert research(ctx, 'validate', ctx['file'])['valid']
    ctx['preview'] = research(ctx, 'import', ctx['file'])


@then('preview declares research-only mutation without writes')
def preview_only(ctx):
    assert ctx['preview']['status'] == 'PREVIEW'
    assert ctx['preview']['committed'] is False
    assert ctx['preview']['mutation_scope'] == 'research'
    assert not ctx['path'].exists()


@given('an accepted fictional insider package')
def accepted(ctx):
    accept(ctx)
    ctx['first'] = ctx['run']


@when('equivalent research is accepted in another order')
def reordered(ctx):
    for key in ['sources', 'people', 'compensation', 'transactions', 'ownership']:
        ctx['package'][key].reverse()
    ctx['package']['transactions'][-1]['quantity'] = '100.000'
    ctx['repeat'] = accept(ctx)


@then('its existing immutable run is reused')
def unchanged(ctx):
    assert ctx['repeat']['status'] == 'UNCHANGED' and ctx['run'] == ctx['first']
    assert len(research(ctx, 'list')['runs']) == 1


@then('corrected evidence creates a separate run')
def new_run(ctx):
    ctx['package']['limitations'].append('A revised independent source review.')
    accept(ctx)
    assert ctx['run'] != ctx['first']
    assert len(research(ctx, 'list')['runs']) == 2
    assert research(ctx, 'show', ctx['first'])


@when('another package cites a different filing issuer')
def wrong_issuer(ctx):
    ctx['before'] = ctx['path'].read_bytes()
    ctx['package']['sources'][2]['cik'] = '0000000009'


@then('its import fails without changing the ledger')
def atomic(ctx):
    assert research(ctx, 'import', ctx['file'], '--yes', code=1)['error']
    assert ctx['path'].read_bytes() == ctx['before']
    assert len(research(ctx, 'list')['runs']) == 1


@given('an initialized financial ledger')
def financial(ctx):
    db = Ledger(ctx['path'])
    ctx['state'] = db.state()
    ctx['planning'] = db.planning_state()
    db.connection.close()


@when('insider research is accepted')
def accept_step(ctx):
    accept(ctx)


@then('household state and planning state remain unchanged')
def financial_unchanged(ctx):
    db = Ledger(ctx['path'])
    assert db.state() == ctx['state']
    assert db.planning_state() == ctx['planning']
    db.connection.close()


@when('unavailable research is inspected')
def missing(ctx):
    assert research(ctx, 'list')['runs'] == []
    for command in ['show', 'summary', 'activity', 'ownership']:
        assert research(ctx, command, 'absent', code=1)['error']


@then('unknown runs and people are rejected without creating a ledger')
def discovery(ctx):
    tool = invoke(ctx, ['tools', 'describe', 'research.insiders.import'])
    assert tool['mutation_scope'] == 'research'
    assert 'insider_research' in invoke(ctx, ['schema'])
    assert not ctx['path'].exists()


@pytest.mark.parametrize('case', [
    'extra', 'float', 'bool', 'exponent', 'negative_quantity', 'zero_quantity',
    'unknown_person', 'unknown_source', 'missing_owner', 'wrong_owner', 'wrong_issuer',
    'duplicate_person_cik', 'duplicate_row', 'duplicate_source', 'future_filing',
    'future_accepted', 'outside_window', 'reversed_role', 'missing_role',
    'unpriced_currency', 'priced_no_currency', 'venue_no_evidence',
    'grant_wrong_basis', 'terms_with_value', 'negative_compensation',
    'self_link', 'cycle', 'both_links', 'cross_person', 'cross_instrument',
    'amendment_no_original', 'ordinary_supersedes', 'missing_link',
    'unresolved_no_note', 'wrong_accession_path', 'wrong_archive_cik', 'private_field',
])
def test_invalid_insider_evidence_is_rejected_without_writes(ctx, case):
    p = ctx['package']
    t = p['transactions'][0]
    if case == 'extra':
        p['prediction'] = 'unsupported'
    elif case in {'float', 'bool', 'exponent', 'negative_quantity', 'zero_quantity'}:
        t['quantity'] = {'float': 1.1, 'bool': True, 'exponent': '1e2',
                         'negative_quantity': '-1', 'zero_quantity': '0'}[case]
    elif case == 'unknown_person':
        t['person_id'] = 'other-run-person'
    elif case == 'unknown_source':
        t['source_id'] = 'other-run-source'
    elif case == 'missing_owner':
        p['people'][0]['reporting_owner_cik'] = None
    elif case == 'wrong_owner':
        p['sources'][2]['reporting_owner_ciks'] = ['0000000003']
    elif case == 'wrong_issuer':
        p['sources'][2]['cik'] = '0000000009'
    elif case == 'duplicate_person_cik':
        p['people'][1]['reporting_owner_cik'] = '0000000002'
    elif case == 'duplicate_row':
        p['transactions'].append(dict(t, id='another'))
    elif case == 'duplicate_source':
        p['sources'].append(dict(p['sources'][0]))
    elif case == 'future_filing':
        p['sources'][2]['filed_at'] = '2027-01-01'
    elif case == 'future_accepted':
        p['sources'][2]['accepted_at'] = '2027-01-01T12:00:00Z'
    elif case == 'outside_window':
        t['transaction_date'] = '2025-01-01'
    elif case == 'reversed_role':
        p['people'][0]['roles'][0]['end_date'] = '2019-01-01'
    elif case == 'missing_role':
        p['people'][0]['roles'] = []
    elif case == 'unpriced_currency':
        t['price_per_unit'] = None
    elif case == 'priced_no_currency':
        t['price_currency'] = None
    elif case == 'venue_no_evidence':
        t['purchase_venue'] = 'OPEN_MARKET'
    elif case == 'grant_wrong_basis':
        p['compensation'][1]['value_basis'] = 'REPORTED_ANNUAL_AMOUNT'
    elif case == 'terms_with_value':
        p['compensation'][0]['value_basis'] = 'UNQUANTIFIED_TERMS'
    elif case == 'negative_compensation':
        p['compensation'][0]['value'] = '-1'
    elif case == 'self_link':
        t['duplicate_of_id'] = t['id']
    elif case == 'cycle':
        t['duplicate_of_id'] = 'gift'
        p['transactions'][4]['duplicate_of_id'] = t['id']
    elif case == 'both_links':
        p['transactions'][7]['duplicate_of_id'] = 'sale'
    elif case == 'cross_person':
        p['transactions'][7]['person_id'] = 'p2'
    elif case == 'cross_instrument':
        p['transactions'][7]['security_title'] = 'Preferred Stock'
    elif case == 'amendment_no_original':
        p['sources'][3]['original_accession_number'] = None
    elif case == 'ordinary_supersedes':
        p['transactions'][7]['source_id'] = 'f4'
    elif case == 'missing_link':
        p['transactions'][7]['supersedes_id'] = 'other-run-row'
    elif case == 'unresolved_no_note':
        p['transactions'][-1]['notes'] = ''
    elif case == 'wrong_accession_path':
        p['sources'][2]['url'] = 'https://www.sec.gov/Archives/edgar/data/1/000000000126999999/filing.xml'
    elif case == 'wrong_archive_cik':
        p['sources'][2]['url'] = p['sources'][2]['url'].replace('/data/1/', '/data/9/')
    elif case == 'private_field':
        p['people'][0]['home_address'] = 'Forbidden private address'
    assert research(ctx, 'validate', ctx['file'], code=1)['error']
    assert not ctx['path'].exists()


def test_all_form_types_and_multiple_reported_owners_validate(ctx):
    assert research(ctx, 'validate', ctx['file'])['valid']
    ctx['package']['sources'][2]['url'] = ctx['package']['sources'][2]['url'].replace('/data/1/', '/data/2/')
    assert research(ctx, 'validate', ctx['file'])['valid']
    assert not ctx['path'].exists()


@pytest.mark.parametrize('status', ['REPORTED_YES', 'REPORTED_NO', 'NOT_DISCLOSED'])
@pytest.mark.parametrize('venue', ['OPEN_MARKET', 'PRIVATE', 'UNKNOWN'])
def test_explicit_plan_status_and_documented_purchase_venue_are_preserved(ctx, status, venue):
    tx = ctx['package']['transactions'][0]
    tx.update(rule_10b5_1_status=status, purchase_venue=venue,
              purchase_venue_locator=None if venue == 'UNKNOWN' else 'Fictional footnote 1 explicitly states venue.')
    activity(ctx)
    row = next(r for r in ctx['rows'] if r['id'] == 'purchase')
    assert row['purchase_venue'] == venue and row['rule_10b5_1_status'] == status


@pytest.mark.parametrize('quantity,price,expected', [
    ('0.000000000000000000000000000001', '0.01', '0.00000000000000000000000000000001'),
    ('123456789012345678901234567890.01', '100', '12345678901234567890123456789001'),
    ('100', '0', '0'),
])
def test_exact_reported_gross_line_values(ctx, quantity, price, expected):
    ctx['package']['transactions'][0].update(quantity=quantity, price_per_unit=price)
    summary(ctx)
    groups = [g for g in ctx['summary']['transaction_groups'] if g['transaction_category'] == 'PURCHASE']
    assert len(groups) == 1
    assert Decimal(groups[0]['gross_line_values']['USD']) == Decimal(expected)


def test_no_transactions_or_unknown_prices_remain_absent(ctx):
    ctx['package']['transactions'] = []
    summary(ctx)
    assert ctx['summary']['transaction_groups'] == []
    assert ctx['summary']['warnings']


def test_unknown_person_is_rejected_on_accepted_run(ctx):
    accept(ctx)
    for command in ['activity', 'ownership']:
        assert research(ctx, command, ctx['run'], '--person', 'absent', code=1)['error']


def test_previous_schema_is_rejected_without_mutation(ctx):
    import sqlite3
    with sqlite3.connect(ctx['path']) as connection:
        connection.execute('CREATE TABLE preserved (value TEXT)')
        connection.execute("INSERT INTO preserved VALUES ('untouched')")
        connection.execute('PRAGMA user_version=7')
    before = ctx['path'].read_bytes()
    assert research(ctx, 'list', code=3)['error']
    assert ctx['path'].read_bytes() == before


def test_saved_plan_and_actual_lots_remain_unchanged(ctx):
    from test_storage_stabilization import snapshot

    from invest.market import MarketClient
    from invest.plans import generate, show
    from invest.targets import save
    db = Ledger(ctx['path'])
    db.apply(snapshot(10, 'fictional-original', '2026-10-08'))
    security = db.resolve('SYN')['id']
    target = save(db, {'name': 'Fictional allocation',
        'target_allocations': {security: '.5', 'CASH': '.5'},
        'planning_constraints': {'eligible_accounts': ['ira'],
                                 'permitted_securities': {'ira': [security]}}})
    plan = generate(db, MarketClient(db, fixture_path='tests/fixtures/fmp-synthetic.json'),
                    target['id'], as_of='2026-10-08')
    before = copy.deepcopy(db.state())
    plan_before = show(db, plan['id'])
    db.connection.close()
    accept(ctx)
    db = Ledger(ctx['path'])
    assert db.state() == before
    assert show(db, plan['id']) == plan_before
    db.connection.close()


def test_compact_reads_never_access_package_json(ctx, monkeypatch):
    import sqlite3
    accept(ctx)
    real_connect = sqlite3.connect

    def guarded_connect(*args, **kwargs):
        connection = real_connect(*args, **kwargs)

        def authorize(action, table, column, database, trigger):
            if action == sqlite3.SQLITE_READ and table == 'research_runs' and column == 'package_json':
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        connection.set_authorizer(authorize)
        return connection

    monkeypatch.setattr(sqlite3, 'connect', guarded_connect)
    assert len(research(ctx, 'list', '--ticker', 'FCSI')['runs']) == 1
    assert research(ctx, 'summary', ctx['run'])
    assert research(ctx, 'activity', ctx['run'])['transactions']
    assert research(ctx, 'ownership', ctx['run'])['observations']


def test_failed_insert_rolls_back_run_sources_and_all_domain_rows(ctx):
    import sqlite3
    db = Ledger(ctx['path'])
    tables = ['research_runs', 'research_sources', 'research_insider_people',
              'research_insider_compensation', 'research_insider_transactions',
              'research_insider_ownership']
    existing = {r[0] for r in db.connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert set(tables) <= existing
    with db.connection:
        db.connection.execute("CREATE TRIGGER force_failure BEFORE INSERT ON research_insider_ownership "
                              "BEGIN SELECT RAISE(ABORT, 'fictional deliberate failure'); END")
    db.connection.close()
    ctx['file'].write_text(json.dumps(ctx['package']))
    result = ctx['runner'].invoke(app, ['research', 'insiders', 'import', str(ctx['file']), '--yes'])
    assert result.exit_code == 4 and not result.stdout
    with sqlite3.connect(ctx['path']) as connection:
        assert all(connection.execute(f'SELECT count(*) FROM {table}').fetchone()[0] == 0
                   for table in tables)


def test_same_run_foreign_keys_prevent_cross_run_person_evidence(ctx):
    import sqlite3
    accept(ctx)
    first = ctx['run']
    ctx['package']['people'][0]['id'] = 'second-person'
    for name in ['compensation', 'transactions', 'ownership']:
        for row in ctx['package'][name]:
            if row['person_id'] == 'p1':
                row['person_id'] = 'second-person'
    accept(ctx)
    db = Ledger(ctx['path'])
    assert db.connection.execute('PRAGMA foreign_keys').fetchone()[0] == 1
    with pytest.raises(sqlite3.IntegrityError), db.connection:
        db.connection.execute('UPDATE research_insider_transactions SET person_id=? WHERE run_id=?',
                              ('second-person', first))
    db.connection.close()


@pytest.mark.parametrize('case', ['duplicate_accession', 'amendment_unlinked', 'branched_correction',
                                 'duplicate_price', 'duplicate_date', 'correction_direction',
                                 'form3_transaction', 'future_ownership', 'ownership_wrong_owner',
                                 'nonsec_filing', 'locator_accession'])
def test_inconsistent_filing_rows_fail_without_storage(ctx, case):
    p = ctx['package']
    if case == 'duplicate_accession':
        p['sources'].append(dict(p['sources'][2], id='same-filing'))
    elif case == 'amendment_unlinked':
        p['transactions'][7]['supersedes_id'] = None
    elif case == 'branched_correction':
        p['transactions'].append(dict(p['transactions'][7], id='branch', source_row_id='branch'))
    elif case == 'duplicate_price':
        p['transactions'][8]['price_per_unit'] = '99'
    elif case == 'duplicate_date':
        p['transactions'][8]['transaction_date'] = '2026-05-02'
    elif case == 'correction_direction':
        p['transactions'][7]['acquired_disposed'] = 'A'
    elif case == 'form3_transaction':
        p['transactions'][0]['source_id'] = 'f3'
    elif case == 'future_ownership':
        p['ownership'][0]['as_of_date'] = '2027-01-01'
    elif case == 'ownership_wrong_owner':
        p['sources'][1]['reporting_owner_ciks'] = ['0000000003']
    elif case == 'nonsec_filing':
        p['sources'][2]['url'] = 'https://fictional.example/filing.xml'
    elif case == 'locator_accession':
        p['sources'][2]['source_locator'] = 'SEC accession 0000000001-26-999999 row 1'
    assert research(ctx, 'validate', ctx['file'], code=1)['error']
    assert not ctx['path'].exists()
