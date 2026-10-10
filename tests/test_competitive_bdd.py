"""CLI behavior baseline for entirely fictional competitive research."""

import json
from decimal import Decimal
from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when
from typer.testing import CliRunner

from invest.cli import app
from invest.ledger import Ledger

scenarios('features/competitive.feature')


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    path = tmp_path / 'selected.db'
    monkeypatch.setenv('INVEST_DB', str(path))
    return {'runner': CliRunner(), 'path': path, 'directory': tmp_path,
            'file': tmp_path / 'competitive.json',
            'package': json.loads((Path(__file__).parent / 'fixtures/competitive.json').read_text())}


def invoke(ctx, args, code=0):
    result = ctx['runner'].invoke(app, args)
    assert result.exit_code == code, result.stderr
    if code:
        assert not result.stdout
    return json.loads(result.stdout if not code else result.stderr)


def research(ctx, command, *args, code=0):
    ctx['file'].write_text(json.dumps(ctx['package']))
    return invoke(ctx, ['research', 'competitive', command, *map(str, args)], code)


def accept(ctx):
    result = research(ctx, 'import', ctx['file'], '--yes')
    ctx['run'] = result.get('run_id', result.get('research_run_id'))
    assert ctx['run']
    return result


def rows(ctx):
    return ctx['matrix'].get('rows', ctx['matrix'].get('comparisons', []))


@given('a valid fictional peer-research package')
@given('a product claim is sourced but competitive superiority is unproven')
def valid(ctx):
    assert ctx['package']['findings'][0]['uncertainty']


@given('Investobot has bundled research skills')
def skills(ctx):
    ctx['skills'] = invoke(ctx, ['research', 'skills', 'list'])['skills']


@when('a user installs them for Codex or Claude Code')
def install(ctx):
    for agent, folder in [('codex', '.agents'), ('claude-code', '.claude')]:
        invoke(ctx, ['research', 'skills', 'install', '--agent', agent,
                     '--workspace', str(ctx['directory'])])
        root = ctx['directory'] / folder / 'skills'
        assert (root / 'investobot-competitive/SKILL.md').is_file()
    ctx['modified'] = ctx['directory'] / '.agents/skills/investobot-earnings/SKILL.md'
    ctx['modified'].write_text('User instructions')
    ctx['before'] = ctx['modified'].read_bytes()
    invoke(ctx, ['research', 'skills', 'install', '--agent', 'codex',
                 '--workspace', str(ctx['directory'])], code=1)


@then('competitive research is discoverable with its method and JSON contract')
def discover(ctx):
    skill = invoke(ctx, ['research', 'skills', 'show', 'investobot-competitive'])
    assert skill['skill_version'] == '1.0.0'
    assert {'SKILL.md', 'references/research-method.md', 'references/comparability-rules.md',
            'references/json-contract.md'} <= skill['files'].keys()
    assert 'invest schema' in '\n'.join(skill['files'].values())
    assert 'research.competitive.matrix' in json.dumps(invoke(ctx, ['tools', 'list']))


@then('existing installed skills and user modifications are preserved')
def preserved(ctx):
    assert ctx['modified'].read_bytes() == ctx['before']
    assert {'investobot-earnings', 'investobot-news', 'investobot-political-contributions'} <= {
        entry['name'] for entry in ctx['skills']}


@when('their competitive research is validated')
def validate(ctx):
    ctx['validation'] = research(ctx, 'validate', ctx['file'])


@then('the corresponding business segments and common market are recognized')
def recognized(ctx):
    assert ctx['validation']['valid']
    preview = research(ctx, 'import', ctx['file'])
    assert preview['peer_count'] == preview['overlap_count'] == 1
    assert not ctx['path'].exists()


@given('a peer is named without evidence of overlapping markets')
def unsupported(ctx):
    ctx['package']['overlaps'] = []
    ctx['package']['findings'] = []


@when('its research package is rejected')
def rejected(ctx):
    assert 'overlap' in research(ctx, 'validate', ctx['file'], code=1)['error'].lower()


@then('no database is created')
def absent(ctx):
    assert not ctx['path'].exists()


@given("Fictional B is linked to Fictional C's registered security ID")
def unrelated(ctx):
    db = Ledger(ctx['path'])
    sec = db.register_security({'ticker': 'FICC', 'name': 'Fictional C',
                               'asset_type': 'STOCK', 'currency': 'USD', 'source': 'Synthetic'})
    db.connection.close()
    ctx['package']['peers'][0]['security_id'] = sec['id']
    ctx['before_db'] = ctx['path'].read_bytes()


@when('its conflicting identity is validated')
def conflict(ctx):
    ctx['error'] = research(ctx, 'validate', ctx['file'], code=3)


@then('the conflicting identity is rejected without writes')
def unchanged_identity(ctx):
    assert 'ticker' in ctx['error']['error'].lower()
    assert ctx['path'].read_bytes() == ctx['before_db']


@when('a comparative finding is saved')
def save_finding(ctx):
    accept(ctx)
    ctx['saved'] = research(ctx, 'show', ctx['run'])


@then('its factual basis and possible implication remain distinguishable')
def separate(ctx):
    text = json.dumps(ctx['saved'])
    finding = ctx['package']['findings'][0]
    assert finding['factual_basis'] in text and finding['interpretation'] in text
    assert finding['factual_basis'] != finding['interpretation']


@then('its uncertainty remains visible')
def uncertainty(ctx):
    assert ctx['package']['findings'][0]['uncertainty'] in json.dumps(ctx['saved'])


@when('their peer matrix is requested')
def matrix(ctx):
    accept(ctx)
    ctx['matrix'] = research(ctx, 'matrix', ctx['run'])
    assert rows(ctx)


@then('the subject-minus-peer difference is 20 million USD')
def absolute(ctx):
    row = rows(ctx)[0]
    assert row['comparison_status'] == 'COMPARABLE'
    assert Decimal(row['absolute_difference']) == Decimal('20000000')


@then('the peer-relative difference is 20 percent')
def percentage(ctx):
    assert Decimal(rows(ctx)[0]['percentage_difference']) == Decimal('20')


@then('both observations retain their original source references')
def citations(ctx):
    text = json.dumps(rows(ctx))
    assert 'a-financials' in text and 'b-financials' in text and 'Revenue' in text


@given('a subject and peer report different currencies bases and periods')
def incompatible(ctx):
    ctx['package']['metrics'][0].update(unit='EUR', accounting_basis='NON_GAAP',
                                      period_start='2025-07-01')


@given('similar-sounding segment revenues have no explicit overlap association')
def segments(ctx):
    for metric, segment in zip(ctx['package']['metrics'], ['Cloud Applications', 'Enterprise Services']):
        metric.update(scope='SEGMENT', segment_name=segment, overlap_id=None)


@then('both reported values remain visible without numeric differences')
def incomparable(ctx):
    text = json.dumps(rows(ctx))
    assert '120000000' in text and '100000000' in text
    for row in rows(ctx):
        assert row['comparison_status'] == 'NOT_COMPARABLE'
        assert row['absolute_difference'] is None and row['percentage_difference'] is None
        assert row['warnings']


@given('a documented private competitor has no published revenue')
def private(ctx):
    ctx['package']['peers'][0]['ticker'] = None
    ctx['package']['metrics'] = ctx['package']['metrics'][:1]
    ctx['package']['limitations'].append('Private-company revenue is undisclosed.')


@then('private revenue remains unavailable rather than zero')
def unknown(ctx):
    row = rows(ctx)[0]
    assert row['peer_value'] is None
    assert row['comparison_status'] == 'NOT_COMPARABLE'
    assert row['absolute_difference'] is None


@when('its import is previewed')
def preview(ctx):
    ctx['preview'] = research(ctx, 'import', ctx['file'])


@then('the preview declares research-only mutation')
def preview_scope(ctx):
    assert ctx['preview']['status'] == 'PREVIEW'
    assert ctx['preview']['committed'] is False
    assert ctx['preview']['mutation_scope'] == 'research'


@given('an accepted fictional peer-research package')
def accepted(ctx):
    accept(ctx)
    ctx['first_run'] = ctx['run']
    db = Ledger(ctx['path'])
    ctx['financial_before'] = db.planning_state()
    db.connection.close()


@when('the same facts are imported with reordered sources and metrics')
def reordered(ctx):
    ctx['package']['sources'].reverse()
    ctx['package']['metrics'].reverse()
    ctx['package']['metrics'][0]['value'] += '00'
    ctx['repeat'] = accept(ctx)


@then('no duplicate run is created')
def no_duplicate(ctx):
    assert ctx['repeat']['status'] == 'UNCHANGED'
    assert ctx['run'] == ctx['first_run']
    assert len(research(ctx, 'list')['runs']) == 1


@then('a corrected package creates a separate historical run')
def corrected(ctx):
    ctx['package']['findings'][0]['uncertainty'] += ' Revised evidence remains uncertain.'
    accept(ctx)
    assert ctx['run'] != ctx['first_run']
    assert len(research(ctx, 'list')['runs']) == 2
    assert research(ctx, 'show', ctx['first_run'])
    db = Ledger(ctx['path'])
    assert db.planning_state() == ctx['financial_before']
    db.connection.close()


@given('accepted research and a new package referencing its absent source')
def foreign_source(ctx):
    accept(ctx)
    ctx['package']['sources'] = [s for s in ctx['package']['sources'] if s['id'] != 'b-financials']
    ctx['before_db'] = ctx['path'].read_bytes()


@when('the new import is rejected')
def rejected_import(ctx):
    assert 'source' in research(ctx, 'import', ctx['file'], '--yes', code=1)['error'].lower()


@then('no partial company metric or finding is saved')
def atomic(ctx):
    assert ctx['path'].read_bytes() == ctx['before_db']
    assert len(research(ctx, 'list')['runs']) == 1


@when('the peer summary is requested')
def summary(ctx):
    accept(ctx)
    ctx['summary'] = research(ctx, 'summary', ctx['run'])


@then('the advantage is shown with assumptions and evidence')
def attributed(ctx):
    text = json.dumps(ctx['summary'])
    finding = ctx['package']['findings'][0]
    assert finding['assumptions'] in text and finding['source_id'] in text
    assert finding['interpretation'] in text and finding['uncertainty'] in text


@then('no score target allocation or trade recommendation is produced')
def no_recommendation(ctx):
    def keys(value):
        if isinstance(value, dict):
            for key, child in value.items():
                yield key
                yield from keys(child)
        elif isinstance(value, list):
            for child in value:
                yield from keys(child)
    assert not {'score', 'ranking', 'target_weights', 'trade_recommendation', 'trades'} & set(keys(ctx['summary']))


@pytest.mark.parametrize('case', [
    'unknown_field', 'float', 'boolean', 'exponent', 'nan', 'duplicate_source',
    'duplicate_peer', 'subject_peer', 'wrong_peer', 'wrong_overlap', 'wrong_source',
    'future_metric', 'reversed_period', 'instant_start', 'consolidated_segment',
    'wrong_unit', 'duplicate_metric', 'wrong_cik', 'wrong_segment',
])
def test_invalid_contract_is_rejected_without_database(ctx, case):
    p = ctx['package']
    m = p['metrics'][0]
    if case == 'unknown_field':
        p['forecast'] = 'unsupported'
    elif case in {'float', 'boolean', 'exponent', 'nan'}:
        m['value'] = {'float': 1.2, 'boolean': True, 'exponent': '1e8', 'nan': 'NaN'}[case]
    elif case == 'duplicate_source':
        p['sources'].append(dict(p['sources'][0]))
    elif case == 'duplicate_peer':
        p['peers'].append(dict(p['peers'][0]))
    elif case == 'subject_peer':
        p['peers'][0]['entity_id'] = 'subject'
    elif case == 'wrong_peer':
        p['overlaps'][0]['peer_id'] = 'absent'
    elif case == 'wrong_overlap':
        p['findings'][0]['overlap_id'] = 'absent'
    elif case == 'wrong_source':
        p['findings'][0]['corroborating_source_ids'] = ['absent']
    elif case == 'future_metric':
        m['period_end'] = '2027-01-01'
    elif case == 'reversed_period':
        m['period_start'] = '2026-07-01'
    elif case == 'instant_start':
        m['period_type'] = 'INSTANT'
    elif case == 'consolidated_segment':
        m['segment_name'] = 'Misassociated'
    elif case == 'wrong_unit':
        m['unit'] = 'count'
    elif case == 'duplicate_metric':
        duplicate = dict(m, id='duplicate')
        p['metrics'].append(duplicate)
    elif case == 'wrong_cik':
        p['subject']['cik'] = '0000000001'
        p['sources'][2]['cik'] = '0000000002'
    elif case == 'wrong_segment':
        m.update(scope='SEGMENT', segment_name='Wrong segment', overlap_id='enterprise-workflow')
    result = research(ctx, 'validate', ctx['file'], code=1)
    assert 'no such command' not in result['error'].lower()
    assert not ctx['path'].exists()


@pytest.mark.parametrize('denominator', ['0', '-100'])
def test_nonpositive_peer_denominator_has_no_percentage(ctx, denominator):
    ctx['package']['metrics'][1]['value'] = denominator
    matrix(ctx)
    row = rows(ctx)[0]
    assert row['comparison_status'] == 'COMPARABLE'
    assert row['percentage_difference'] is None and row['warnings']


def test_exact_decimal_subtraction_beyond_default_precision(ctx):
    ctx['package']['metrics'][0]['value'] = '123456789012345678901234567890.01'
    ctx['package']['metrics'][1]['value'] = '123456789012345678901234567890.00'
    matrix(ctx)
    assert Decimal(rows(ctx)[0]['absolute_difference']) == Decimal('0.01')


def test_segment_comparison_uses_explicit_overlap_despite_different_names(ctx):
    for metric, segment in zip(ctx['package']['metrics'], ['Cloud Applications', 'Enterprise Services']):
        metric.update(scope='SEGMENT', segment_name=segment, overlap_id='enterprise-workflow')
    matrix(ctx)
    assert rows(ctx)[0]['comparison_status'] == 'COMPARABLE'


def test_competitive_reads_and_schema_are_available_without_creating_database(ctx):
    assert research(ctx, 'list')['runs'] == []
    for command in ['show', 'summary', 'matrix']:
        assert research(ctx, command, 'missing-run', code=1)['error']
    tool = invoke(ctx, ['tools', 'describe', 'research.competitive.import'])
    assert tool['mutation_scope'] == 'research'
    assert tool['json_input_schema']['additionalProperties'] is False
    assert 'competitive_research' in invoke(ctx, ['schema'])
    assert not ctx['path'].exists()
