import json

import pytest
from pytest_bdd import given, scenarios, then, when
from test_earnings_models import package
from typer.testing import CliRunner

from invest.cli import app
from invest.ledger import Ledger

scenarios('features/earnings_cli.feature')


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    path = tmp_path / 'selected.db'
    monkeypatch.setenv('INVEST_DB', str(path))
    file = tmp_path / 'earnings.json'
    file.write_text(json.dumps(package()))
    return {'runner': CliRunner(), 'path': path, 'file': file, 'directory': tmp_path}


def invoke(ctx, arguments, code=0):
    result = ctx['runner'].invoke(app, arguments)
    assert result.exit_code == code, result.stderr
    return json.loads(result.stdout if code == 0 else result.stderr)


@given('a fictional earnings file and no selected database')
def initial(ctx):
    assert not ctx['path'].exists()


@when('earnings are validated previewed and listed')
def read_only(ctx):
    assert invoke(ctx, ['research', 'earnings', 'validate', str(ctx['file'])])['valid']
    ctx['preview'] = invoke(ctx, ['research', 'earnings', 'import', str(ctx['file'])])
    assert invoke(ctx, ['research', 'earnings', 'list'])['runs'] == []


@then('stdout is JSON and no database file is created')
def no_file(ctx):
    assert ctx['preview']['status'] == 'PREVIEW'
    assert not ctx['preview']['committed']
    assert not ctx['path'].exists()


@when('two source-backed annual comparison periods are confirmed')
def confirmed(ctx):
    prior = package()
    prior['reporting_period'].update(fiscal_year=2025, period_end='2025-06-30')
    prior['sources'][0]['filed_at'] = '2025-08-01'
    prior['metrics'][0].update(value='1000000000', fiscal_year=2025,
                              period_start='2025-04-01', period_end='2025-06-30')
    file = ctx['directory'] / 'prior.json'
    file.write_text(json.dumps(prior))
    ctx['prior'] = invoke(ctx, ['research', 'earnings', 'import', str(file), '--yes'])
    ctx['current'] = invoke(ctx, ['research', 'earnings', 'import', str(ctx['file']), '--yes'])


@then('saved history summaries and compatible comparisons are discoverable')
def history(ctx):
    current = ctx['current']['research_run_id']
    prior = ctx['prior']['research_run_id']
    assert invoke(ctx, ['research', 'earnings', 'show', current])['skill_version'] == '1.0.0'
    assert invoke(ctx, ['research', 'earnings', 'summary', current])['metrics']
    compared = invoke(ctx, ['research', 'earnings', 'compare', prior, current])
    assert compared['comparisons'][0]['absolute_change'] == '250000000'
    assert len(invoke(ctx, ['research', 'earnings', 'list', '--ticker', 'FAKE'])['runs']) == 2
    tool = invoke(ctx, ['tools', 'describe', 'research.earnings.import'])
    assert tool['mutation_scope'] == 'research'
    assert tool['json_input_schema']['additionalProperties'] is False
    assert 'earnings_research' in invoke(ctx, ['schema'])


def test_validators_verify_canonical_identity_readonly(ctx):
    from test_political_models import package as political_package
    from test_political_models import reviewed_policy
    db = Ledger(ctx['path'])
    sec = db.register_security({'ticker': 'RIGHT', 'name': 'Fictional issuer',
                               'asset_type': 'STOCK', 'currency': 'USD', 'source': 'Synthetic'})
    db.connection.close()
    before = ctx['path'].read_bytes()
    policy = ctx['directory'] / 'policy.json'
    policy.write_text(json.dumps(reviewed_policy()))
    for kind, payload in [('earnings', package()), ('political', political_package())]:
        if kind == 'political':
            payload['contributions'] = []
            payload['sources'] = payload['sources'][:1]
            payload['recipients'] = []
            payload['scope']['rights_status'] = 'PENDING_REVIEW'
        payload['company']['security_id'] = sec['id']
        payload['company']['ticker'] = 'WRONG'
        ctx['file'].write_text(json.dumps(payload))
        result = invoke(ctx, ['research', kind, 'validate', str(ctx['file'])], code=3)
        assert 'ticker' in result['error'].lower()
    assert before == ctx['path'].read_bytes()


@pytest.mark.parametrize('kind', ['political', 'earnings'])
def test_read_only_research_queries_never_create_default_database(ctx, kind):
    assert invoke(ctx, ['research', kind, 'list'])['runs'] == []
    invoke(ctx, ['research', kind, 'show', 'missing-run'], code=1)
    assert not ctx['path'].exists()


def test_cli_invalid_input_is_stderr_only_without_database(ctx):
    ctx['file'].write_text('{bad json')
    result = ctx['runner'].invoke(app, ['research', 'earnings', 'validate', str(ctx['file'])])
    assert result.exit_code == 1 and not result.stdout
    assert json.loads(result.stderr)['error']
    assert not ctx['path'].exists()


def test_explicit_cli_skill_install_reports_files_without_financial_writes(ctx):
    result = invoke(ctx, ['research', 'skills', 'install', '--agent', 'codex',
                          '--workspace', str(ctx['directory'])])
    assert result['copied_files'] and len(result['skills']) == 3
    assert not ctx['path'].exists()
