"""Fictional filing corrections: retain history and require explicit provenance."""

import copy
import json
import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when
from typer.testing import CliRunner

from invest.cli import app
from invest.ledger import Ledger

scenarios('features/insider_corrections.feature')


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    path = tmp_path / 'corrections.db'
    monkeypatch.setenv('INVEST_DB', str(path))
    package = json.loads((Path(__file__).parent / 'fixtures/insiders.json').read_text())
    package['schema_version'] = '1.1'
    package['transactions'] = []
    package['ownership'] = []
    return {'package': package, 'path': path, 'file': tmp_path / 'corrections.json',
            'runner': CliRunner()}


def call(ctx, command, *args, code=0):
    ctx['file'].write_text(json.dumps(ctx['package']))
    result = ctx['runner'].invoke(app, ['research', 'insiders', command, *map(str, args)])
    assert result.exit_code == code, result.stderr
    if code:
        assert not result.stdout
    parsed = json.loads(result.stderr if code else result.stdout)
    if code:
        assert 'no such command' not in parsed['error'].lower()
    return parsed


def validate_baseline(ctx):
    assert call(ctx, 'validate', ctx['file'])['valid']


def accept(ctx):
    result = call(ctx, 'import', ctx['file'], '--yes')
    ctx['run'] = result['research_run_id']
    return result


def holding(id='original', source='f4', date='2026-05-02', quantity='125', **extra):
    return {'id': id, 'person_id': 'p1', 'source_id': source, 'source_row_id': id,
            'as_of_date': date, 'table_type': 'NON_DERIVATIVE', 'security_title': 'Common Stock',
            'reported_quantity': quantity, 'ownership_form': 'DIRECT',
            'indirect_ownership_nature': None, 'notes': 'Fictional disclosed ownership.', **extra}


def transaction(id='original', source='f4', date='2026-05-02', code='M', **extra):
    return {'id': id, 'person_id': 'p1', 'source_id': source, 'source_row_id': id,
            'transaction_date': date, 'table_type': 'NON_DERIVATIVE', 'security_title': 'Common Stock',
            'transaction_code': code, 'acquired_disposed': 'A', 'quantity': '200',
            'price_per_unit': '40', 'price_currency': 'USD', 'ownership_form': 'DIRECT',
            'indirect_ownership_nature': None, 'purchase_venue': 'UNKNOWN',
            'purchase_venue_locator': None, 'rule_10b5_1_status': 'NOT_DISCLOSED',
            'review_status': 'VERIFIED', 'supersedes_id': None, 'duplicate_of_id': None,
            'notes': 'Fictional disclosed transaction.', **extra}


def ownership_pair(ctx):
    ctx['package']['ownership'] = [holding(), holding('corrected', 'amend', quantity='120',
        supersedes_id='original', correction_source_locator='Amendment footnote 1 corrects shares held.')]


@given('an amendment repeats an original holding without a correction link')
def amendment_repeat(ctx):
    ctx['package']['ownership'] = [holding(), holding('amended-repeat', 'amend',
        duplicate_of_id='original')]


@then('the amended repeat remains unresolved and the original remains latest')
def amended_repeat_unresolved(ctx):
    row = next(r for r in ctx['ownership']['observations'] if r['id'] == 'amended-repeat')
    assert row['status'] == 'UNRESOLVED'
    assert row['exclusion_reason'] == 'UNRESOLVED' and row['is_effective'] is False
    assert [r['id'] for r in ctx['ownership']['latest_observations']] == ['original']


@given('a supported correction targets an unresolved original transaction')
def unresolved_original_transaction(ctx):
    transaction_pair(ctx)
    validate_baseline(ctx)
    ctx['package']['transactions'][0].update(review_status='UNRESOLVED',
        notes='Original economic event identity remains unverified.')


def transaction_pair(ctx, date='2026-05-03', code='P'):
    ctx['package']['transactions'] = [transaction(), transaction('corrected', 'amend', date, code,
        supersedes_id='original', correction_source_locator='Amendment note corrects date and code.')]


def rows(ctx, command):
    accept(ctx)
    result = call(ctx, command, ctx['run'])
    ctx[command] = result
    return result


@given('a Form 4 discloses 125 directly held common shares on May 2')
def original(ctx):
    ctx['package']['ownership'] = [holding()]


@given('its cited Form 4 amendment corrects the same holding to 120 shares on May 2')
def amended(ctx):
    ownership_pair(ctx)


@given('two sourced unlinked ownership observations for the same holding and date')
def unlinked(ctx):
    ctx['package']['ownership'] = [holding(), holding('unlinked', 'f5')]


@given('their reported quantities disagree')
def disagree(ctx):
    ctx['package']['ownership'][1]['reported_quantity'] = '120'


@given('an amended balance without a verifiable original-row link')
def unsupported_holding(ctx):
    ctx['package']['ownership'] = [holding(), holding('unsupported', 'amend', quantity='120')]


@when('the insider ownership report is requested')
def report_ownership(ctx):
    rows(ctx, 'ownership')


@then('both original and amended observations remain inspectable')
def retained(ctx):
    observations = {r['id']: r for r in ctx['ownership']['observations']}
    assert len(observations) == 2
    assert observations['original']['status'] == 'SUPERSEDED'
    assert observations['original']['is_effective'] is False
    assert observations['original']['exclusion_reason'] == 'SUPERSEDED'
    assert observations['corrected']['status'] == 'EFFECTIVE'
    assert observations['corrected']['supersedes_id'] == 'original'
    assert observations['corrected']['correction_source_locator']
    assert '0000000001-26-000004' in json.dumps(observations)


@then('only 120 shares appear as the effective latest reported balance')
def latest_corrected(ctx):
    latest = ctx['ownership']['latest_observations']
    assert len(latest) == 1 and Decimal(latest[0]['reported_quantity']) == 120
    assert ctx['ownership']['conflicting_latest_observations'] == []


@then('neither amount is selected as a uniquely current balance')
def no_arbitrary_balance(ctx):
    assert ctx['ownership']['latest_observations'] == []


@then('both filings appear as conflicting latest observations')
def conflicts(ctx):
    assert {r['id'] for r in ctx['ownership']['conflicting_latest_observations']} == {'original', 'unlinked'}
    warnings = json.dumps(ctx['ownership']['warnings'])
    assert 'f4' in warnings and 'f5' in warnings


@then('the amended balance is marked unresolved')
def unresolved_holding(ctx):
    row = next(r for r in ctx['ownership']['observations'] if r['id'] == 'unsupported')
    assert row['status'] == 'UNRESOLVED' and row['is_effective'] is False
    assert row['exclusion_reason'] == 'UNRESOLVED'
    assert 'unsupported' in json.dumps(ctx['ownership']['warnings'])


@then('the original balance remains the effective latest observation')
def original_latest(ctx):
    assert [r['id'] for r in ctx['ownership']['latest_observations']] == ['original']


@given('an original exercise and documented purchase correction')
def corrected_trade(ctx):
    transaction_pair(ctx)


@when('insider activity is summarized')
def activity_summary(ctx):
    rows(ctx, 'activity')
    ctx['summary'] = call(ctx, 'summary', ctx['run'])


@then('the original exercise is superseded')
def exercise_superseded(ctx):
    old = next(r for r in ctx['activity']['transactions'] if r['id'] == 'original')
    assert old['transaction_code'] == 'M' and old['transaction_date'] == '2026-05-02'
    assert old['effective'] is False and old['exclusion_reason'] == 'SUPERSEDED'


@then('the corrected purchase is counted once under May 3')
def corrected_purchase(ctx):
    effective = [r for r in ctx['activity']['transactions'] if r['effective']]
    assert len(effective) == 1
    assert effective[0]['transaction_code'] == 'P' and effective[0]['transaction_date'] == '2026-05-03'
    assert effective[0]['correction_source_locator']
    assert ctx['summary']['transaction_counts']['PURCHASE'] == 1
    assert ctx['summary']['transaction_counts']['OPTION_EXERCISE_OR_CONVERSION'] == 0
    assert '0000000001-26-000003' in json.dumps(ctx['activity'])
    assert '0000000001-26-000004' in json.dumps(ctx['activity'])


@then('its purchase venue remains unknown')
def unknown_venue(ctx):
    assert all(r['purchase_venue'] == 'UNKNOWN' for r in ctx['activity']['transactions'])


@given('a proposed code correction without amendment evidence')
def undocumented(ctx):
    transaction_pair(ctx, code='P')
    row = ctx['package']['transactions'][1]
    row.update(review_status='UNRESOLVED', correction_source_locator=None,
               notes='Correction evidence is absent; proposed code is unverified.')


@when('the unresolved activity is accepted')
def unresolved_activity(ctx):
    activity_summary(ctx)


@then('the unsupported correction remains excluded')
def unsupported_transaction(ctx):
    row = next(r for r in ctx['activity']['transactions'] if r['id'] == 'corrected')
    assert row['effective'] is False and row['exclusion_reason'] == 'UNRESOLVED'
    assert ctx['summary']['transaction_counts']['PURCHASE'] == 0


@then('the original transaction remains effective')
def original_effective(ctx):
    old = next(r for r in ctx['activity']['transactions'] if r['id'] == 'original')
    assert old['effective'] is True
    assert ctx['summary']['transaction_counts']['OPTION_EXERCISE_OR_CONVERSION'] == 1


@given('a correction attributed to an unrelated reporting owner')
def unrelated(ctx):
    transaction_pair(ctx)
    validate_baseline(ctx)
    ctx['package']['transactions'][1]['person_id'] = 'p2'


@when('correction validation is attempted')
def rejection(ctx):
    assert call(ctx, 'validate', ctx['file'], code=1)['error']


@then('the correction is rejected without creating storage')
def absent(ctx):
    assert not ctx['path'].exists()


@given('a source-backed correction package')
def correction_package(ctx):
    ownership_pair(ctx)


@when('correction commands and schemas are inspected')
def discovery(ctx):
    for args in [['schema'], ['tools', 'describe', 'research.insiders.import']]:
        result = ctx['runner'].invoke(app, args)
        assert result.exit_code == 0
        assert '"1.1"' in result.stdout
    result = ctx['runner'].invoke(app, ['research', 'skills', 'show', 'investobot-management-insiders'])
    assert result.exit_code == 0
    ctx['skill'] = json.loads(result.stdout)


@then('input version 1.1 and trusted skill version 1.1.0 are exposed')
def trusted_identity(ctx):
    assert ctx['skill']['skill_version'] == '1.1.0'
    result = accept(ctx)
    saved = call(ctx, 'show', result['research_run_id'])
    assert saved['schema_version'] == '1.1' and saved['skill_version'] == '1.1.0'


@then('accepted research uses fresh schema 9')
def schema9(ctx):
    with sqlite3.connect(ctx['path']) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 9


@pytest.mark.parametrize('form', ['3', '4', '5'])
@pytest.mark.parametrize('changed_date', [False, True])
def test_matching_base_forms_correct_ownership(ctx, form, changed_date):
    ownership_pair(ctx)
    original_source = next(s for s in ctx['package']['sources'] if s['id'] == 'f4')
    amended_source = next(s for s in ctx['package']['sources'] if s['id'] == 'amend')
    original_source['source_type'] = form
    amended_source['source_type'] = form + '/A'
    if changed_date:
        ctx['package']['ownership'][1].update(as_of_date='2026-05-03',
            correction_source_locator='Amendment note explicitly corrects ownership date and quantity.')
    report = rows(ctx, 'ownership')
    latest = report['latest_observations']
    assert len(latest) == 1 and latest[0]['id'] == 'corrected'
    assert latest[0]['as_of_date'] == ('2026-05-03' if changed_date else '2026-05-02')


@pytest.mark.parametrize('date,code', [('2026-05-03', 'M'), ('2026-05-02', 'P'),
                                      ('2026-05-03', 'P')])
def test_supported_date_and_code_corrections(ctx, date, code):
    transaction_pair(ctx, date, code)
    report = rows(ctx, 'activity')
    effective = [r for r in report['transactions'] if r['effective']]
    assert len(effective) == 1
    assert effective[0]['transaction_date'] == date and effective[0]['transaction_code'] == code


def test_unchanged_date_code_price_and_quantity_correction_remains_supported(ctx):
    transaction_pair(ctx, '2026-05-02', 'M')
    ctx['package']['transactions'][1].update(quantity='201.000000000000000000000000000001',
                                            price_per_unit='40.000000000000000000000000000001',
                                            correction_source_locator=None)
    report = rows(ctx, 'activity')
    effective = [r for r in report['transactions'] if r['effective']]
    assert len(effective) == 1 and effective[0]['id'] == 'corrected'


@pytest.mark.parametrize('kind', ['ownership', 'transactions'])
@pytest.mark.parametrize('case', ['self', 'cycle', 'branch', 'missing_target', 'both_links',
    'wrong_person', 'wrong_instrument', 'wrong_table', 'wrong_form', 'wrong_accession',
    'wrong_issuer', 'wrong_owner', 'earlier_amendment', 'duplicate_target',
    'wrong_ownership_form', 'wrong_indirect_nature', 'missing_locator'])
def test_unsafe_correction_links_fail_read_only(ctx, kind, case):
    (ownership_pair if kind == 'ownership' else transaction_pair)(ctx)
    validate_baseline(ctx)
    p = ctx['package']
    records = p[kind]
    old, new = records
    source = next(s for s in p['sources'] if s['id'] == 'amend')
    if case == 'self':
        new['supersedes_id'] = new['id']
    elif case == 'cycle':
        old.update(source_id='amend', supersedes_id='corrected',
                   correction_source_locator='Fictional cyclic correction.')
    elif case == 'branch':
        records.append(dict(new, id='branch', source_row_id='branch'))
    elif case == 'missing_target':
        new['supersedes_id'] = 'other-run-record'
    elif case == 'both_links':
        new['duplicate_of_id'] = 'original'
    elif case == 'wrong_person':
        new['person_id'] = 'p2'
    elif case == 'wrong_instrument':
        new['security_title'] = 'Preferred Shares'
    elif case == 'wrong_table':
        new['table_type'] = 'DERIVATIVE'
    elif case == 'wrong_form':
        source['source_type'] = '5/A'
    elif case == 'wrong_accession':
        source['original_accession_number'] = '0000000001-26-999999'
    elif case == 'wrong_issuer':
        source['cik'] = '0000000009'
    elif case == 'wrong_owner':
        source['reporting_owner_ciks'] = ['0000000003']
    elif case == 'earlier_amendment':
        source.update(filed_at='2026-05-04', accepted_at='2026-05-04T12:00:00Z')
    elif case == 'duplicate_target':
        duplicate = dict(old, id='duplicate', source_row_id='duplicate', source_id='f5',
                         duplicate_of_id='original')
        records.append(duplicate)
        source['source_type'] = '5/A'
        source['original_accession_number'] = next(s for s in p['sources'] if s['id'] == 'f5')['accession_number']
        new['supersedes_id'] = 'duplicate'
    elif case == 'wrong_ownership_form':
        new.update(ownership_form='INDIRECT', indirect_ownership_nature='Fictional trust')
    elif case == 'wrong_indirect_nature':
        old.update(ownership_form='INDIRECT', indirect_ownership_nature='First trust')
        new.update(ownership_form='INDIRECT', indirect_ownership_nature='Other trust')
    elif case == 'missing_locator':
        new['correction_source_locator'] = None
    assert call(ctx, 'validate', ctx['file'], code=1)['error']
    assert not ctx['path'].exists()


@pytest.mark.parametrize('quantity', ['125', '120'])
def test_equal_or_differing_unlinked_latest_observations_require_review(ctx, quantity):
    ctx['package']['ownership'] = [holding(), holding('unlinked', 'f5', quantity=quantity)]
    report = rows(ctx, 'ownership')
    assert report['latest_observations'] == []
    assert len(report['conflicting_latest_observations']) == 2
    assert report['warnings']


def test_explicit_ownership_duplicate_is_excluded_without_guessing(ctx):
    ctx['package']['ownership'] = [holding(), holding('repeat', 'f5', duplicate_of_id='original')]
    report = rows(ctx, 'ownership')
    repeat = next(r for r in report['observations'] if r['id'] == 'repeat')
    assert repeat['status'] == 'DUPLICATE' and repeat['is_effective'] is False
    assert repeat['exclusion_reason'] == 'DUPLICATE'
    assert [r['id'] for r in report['latest_observations']] == ['original']


@pytest.mark.parametrize('case', ['quantity', 'date', 'identity'])
def test_inconsistent_ownership_duplicate_rejects(ctx, case):
    ctx['package']['ownership'] = [holding(), holding('repeat', 'f5', duplicate_of_id='original')]
    validate_baseline(ctx)
    row = ctx['package']['ownership'][1]
    row[{'quantity': 'reported_quantity', 'date': 'as_of_date', 'identity': 'security_title'}[case]] = {
        'quantity': '120', 'date': '2026-05-03', 'identity': 'Preferred Shares'}[case]
    assert call(ctx, 'validate', ctx['file'], code=1)['error']


def add_second_amendment(ctx):
    source = copy.deepcopy(next(s for s in ctx['package']['sources'] if s['id'] == 'amend'))
    source.update(id='amend2', accession_number='0000000001-26-000006',
        original_accession_number='0000000001-26-000004', filed_at='2026-05-08',
        accepted_at='2026-05-08T12:00:00Z',
        url='https://www.sec.gov/Archives/edgar/data/1/000000000126000006/filing.xml')
    ctx['package']['sources'].append(source)


def test_linear_ownership_amendments_preserve_all_filings(ctx):
    ownership_pair(ctx)
    add_second_amendment(ctx)
    ctx['package']['ownership'].append(holding('corrected2', 'amend2', quantity='119',
        supersedes_id='corrected', correction_source_locator='Second amendment note corrects prior amended quantity.'))
    report = rows(ctx, 'ownership')
    assert len(report['observations']) == 3
    assert [r['id'] for r in report['latest_observations']] == ['corrected2']
    assert sum(r['status'] == 'SUPERSEDED' for r in report['observations']) == 2


def test_amendment_cannot_target_unresolved_ownership(ctx):
    ownership_pair(ctx)
    validate_baseline(ctx)
    ctx['package']['ownership'][1]['supersedes_id'] = None
    add_second_amendment(ctx)
    ctx['package']['ownership'].append(holding('corrected2', 'amend2', quantity='119',
        supersedes_id='corrected', correction_source_locator='Purported second correction of unresolved row.'))
    assert call(ctx, 'validate', ctx['file'], code=1)['error']


def test_corrected_effective_date_not_latest_filing_drives_ownership(ctx):
    ownership_pair(ctx)
    ctx['package']['ownership'][1]['as_of_date'] = '2026-05-01'
    ctx['package']['ownership'][1]['correction_source_locator'] = 'Amendment note corrects quantity and date.'
    ctx['package']['ownership'].append(holding('newer-observation', 'f5', date='2026-05-03', quantity='130'))
    report = rows(ctx, 'ownership')
    assert [r['id'] for r in report['latest_observations']] == ['newer-observation']


def test_changed_transaction_direction_rejects(ctx):
    transaction_pair(ctx)
    validate_baseline(ctx)
    ctx['package']['transactions'][1]['acquired_disposed'] = 'D'
    assert call(ctx, 'validate', ctx['file'], code=1)['error']


def test_corrected_purchase_cannot_infer_market_venue(ctx):
    transaction_pair(ctx)
    validate_baseline(ctx)
    ctx['package']['transactions'][1]['purchase_venue'] = 'OPEN_MARKET'
    assert call(ctx, 'validate', ctx['file'], code=1)['error']


def test_ownership_and_transaction_links_hash_idempotently(ctx):
    ownership_pair(ctx)
    transaction_pair(ctx)
    ctx['package']['ownership'][1]['reported_quantity'] = '0.000000000000000000000000000001'
    first = accept(ctx)['research_run_id']
    for field in ['sources', 'people', 'compensation', 'transactions', 'ownership']:
        ctx['package'][field].reverse()
    result = accept(ctx)
    assert result['status'] == 'UNCHANGED' and result['research_run_id'] == first
    saved = call(ctx, 'show', first)
    row = next(r for r in saved['ownership'] if r['id'] == 'corrected')
    assert row['reported_quantity'] == '0.000000000000000000000000000001'
    ctx['package']['ownership'][0]['correction_source_locator'] += ' Additional specific provenance.'
    assert accept(ctx)['research_run_id'] != first
    assert call(ctx, 'show', first)['ownership']


def test_optional_correction_fields_default_null_without_rewriting_contract(ctx):
    ctx['package']['ownership'] = [holding()]
    ctx['package']['transactions'] = [transaction()]
    accept(ctx)
    saved = call(ctx, 'show', ctx['run'])
    assert saved['transactions'][0]['correction_source_locator'] is None
    for field in ['supersedes_id', 'duplicate_of_id', 'correction_source_locator']:
        assert saved['ownership'][0][field] is None
    validate_baseline(ctx)
    ctx['package']['schema_version'] = '1.0'
    assert call(ctx, 'validate', ctx['file'], code=1)['error']


def test_correction_validate_and_preview_never_create_storage(ctx):
    ownership_pair(ctx)
    transaction_pair(ctx)
    validate_baseline(ctx)
    preview = call(ctx, 'import', ctx['file'])
    assert preview['status'] == 'PREVIEW' and preview['committed'] is False
    assert preview['mutation_scope'] == 'research'
    assert not ctx['path'].exists()


def test_schema8_rejection_preserves_selected_database(ctx):
    with sqlite3.connect(ctx['path']) as db:
        db.execute('CREATE TABLE preserved (value TEXT)')
        db.execute("INSERT INTO preserved VALUES ('untouched')")
        db.execute('PRAGMA user_version=8')
    before = ctx['path'].read_bytes()
    assert call(ctx, 'list', code=3)['error']
    assert ctx['path'].read_bytes() == before


def test_correction_queries_project_without_package_json(ctx, monkeypatch):
    ownership_pair(ctx)
    transaction_pair(ctx)
    accept(ctx)
    real_connect = sqlite3.connect

    def guarded_connect(*args, **kwargs):
        db = real_connect(*args, **kwargs)

        def authorize(action, table, column, database, trigger):
            if action == sqlite3.SQLITE_READ and table == 'research_runs' and column == 'package_json':
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        db.set_authorizer(authorize)
        return db

    monkeypatch.setattr(sqlite3, 'connect', guarded_connect)
    assert call(ctx, 'list')['runs']
    assert call(ctx, 'ownership', ctx['run'])['latest_observations'][0]['id'] == 'corrected'
    assert call(ctx, 'summary', ctx['run'])['transaction_counts']['PURCHASE'] == 1
    assert call(ctx, 'activity', ctx['run'])['transactions']


def test_correction_rows_and_shared_evidence_roll_back_atomically(ctx):
    ownership_pair(ctx)
    transaction_pair(ctx)
    validate_baseline(ctx)
    db = Ledger(ctx['path'])
    with db.connection:
        db.connection.execute("CREATE TRIGGER fail_corrected_holding BEFORE INSERT ON research_insider_ownership "
            "WHEN NEW.holding_id='corrected' BEGIN SELECT RAISE(ABORT, 'deliberate fictional failure'); END")
    db.connection.close()
    assert call(ctx, 'import', ctx['file'], '--yes', code=4)['error']
    with sqlite3.connect(ctx['path']) as db:
        for table in ['research_runs', 'research_sources', 'research_insider_people',
                      'research_insider_compensation', 'research_insider_transactions',
                      'research_insider_ownership']:
            assert db.execute(f'SELECT count(*) FROM {table}').fetchone()[0] == 0


def test_deferred_same_run_ownership_foreign_keys_and_link_check(ctx):
    ownership_pair(ctx)
    accept(ctx)
    first = ctx['run']
    p = ctx['package']
    p['ownership'][0]['id'] = 'second-original'
    p['ownership'][0]['source_row_id'] = 'second-original'
    p['ownership'][1]['supersedes_id'] = 'second-original'
    accept(ctx)
    db = Ledger(ctx['path'])
    assert db.connection.execute('PRAGMA user_version').fetchone()[0] == 9
    with pytest.raises(sqlite3.IntegrityError), db.connection:
        db.connection.execute('UPDATE research_insider_ownership SET supersedes_id=? WHERE run_id=? AND holding_id=?',
                              ('second-original', first, 'corrected'))
    with pytest.raises(sqlite3.IntegrityError), db.connection:
        db.connection.execute('UPDATE research_insider_ownership SET duplicate_of_id=? WHERE run_id=? AND holding_id=?',
                              ('original', first, 'corrected'))
    db.connection.close()


def test_corrected_research_preserves_saved_plan_holdings_and_lots(ctx):
    from test_storage_stabilization import snapshot

    from invest.market import MarketClient
    from invest.plans import generate, show
    from invest.targets import save
    ownership_pair(ctx)
    transaction_pair(ctx)
    validate_baseline(ctx)
    db = Ledger(ctx['path'])
    db.apply(snapshot(10, 'fictional-original', '2026-10-08'))
    security = db.resolve('SYN')['id']
    target = save(db, {'name': 'Fictional allocation',
        'target_allocations': {security: '.5', 'CASH': '.5'},
        'planning_constraints': {'eligible_accounts': ['ira'],
                                 'permitted_securities': {'ira': [security]}}})
    plan = generate(db, MarketClient(db, fixture_path='tests/fixtures/fmp-synthetic.json'),
                    target['id'], as_of='2026-10-08')
    before, planning_before = copy.deepcopy(db.state()), copy.deepcopy(db.planning_state())
    plan_before = show(db, plan['id'])
    db.connection.close()
    accept(ctx)
    db = Ledger(ctx['path'])
    assert db.state() == before and db.planning_state() == planning_before
    assert show(db, plan['id']) == plan_before
    db.connection.close()


def test_prior_run_ownership_is_not_implicitly_joined(ctx):
    ctx['package']['ownership'] = [holding()]
    first = accept(ctx)['research_run_id']
    ctx['package']['ownership'] = [holding('amended-unlinked', 'amend', quantity='120')]
    second = accept(ctx)['research_run_id']
    report = call(ctx, 'ownership', second)
    assert len(report['observations']) == 1
    assert report['observations'][0]['status'] == 'UNRESOLVED'
    assert report['latest_observations'] == []
    assert call(ctx, 'ownership', first)['latest_observations'][0]['reported_quantity'] == '125'
