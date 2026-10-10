import copy
import json
import sqlite3

import pytest
from pytest_bdd import given, scenarios, then, when
from typer.testing import CliRunner

from invest.cli import app
from invest.ledger import Ledger

scenarios('features/political_import.feature')


def package():
    return {'schema_version': '1.0', 'research_type': 'EXECUTIVE_POLITICAL_CONTRIBUTIONS',
            'company': {'name': 'Fictional Corporation', 'ticker': 'FICTION', 'security_id': None},
            'scope': {'jurisdiction': 'US_FEDERAL', 'period_start': '2024-01-01',
                      'period_end': '2026-10-09', 'researched_as_of': '2026-10-09',
                      'coverage_status': 'BLOCKED', 'rights_status': 'PENDING_REVIEW'},
            'sources': [], 'executives': [], 'recipients': [], 'contributions': [],
            'unresolved_matches': [], 'limitations': ['Personal source permissions pending.']}


@pytest.fixture
def ctx(tmp_path):
    ledger = Ledger(tmp_path / 'test.db')
    yield {'ledger': ledger, 'file': tmp_path / 'input.json'}
    ledger.connection.close()


@given('a fictional corporate research package')
def research(ctx):
    ctx['package'] = package()
    ctx['before'] = copy.deepcopy(ctx['ledger'].planning_state())


@when('research import is previewed')
def preview(ctx):
    from invest.political import import_research
    ctx['result'] = import_research(ctx['ledger'], ctx['package'])


@then('no research is persisted')
def no_write(ctx):
    assert ctx['result']['committed'] is False
    assert ctx['ledger'].connection.execute('SELECT COUNT(*) FROM research_political_runs').fetchone()[0] == 0


@when('research import is confirmed twice')
def accept(ctx):
    from invest.political import import_research
    ctx['first'] = import_research(ctx['ledger'], ctx['package'], yes=True)
    ctx['second'] = import_research(ctx['ledger'], ctx['package'], yes=True)


@then('one immutable run is saved without financial changes')
def isolated(ctx):
    from invest.political_queries import show
    assert ctx['first']['research_run_id'] == ctx['second']['research_run_id']
    assert ctx['second']['status'] == 'UNCHANGED'
    assert ctx['ledger'].planning_state() == ctx['before']
    assert ctx['ledger'].connection.execute('SELECT COUNT(*) FROM research_political_runs').fetchone()[0] == 1
    assert show(ctx['ledger'], ctx['first']['research_run_id'])['company']['name'] == 'Fictional Corporation'


@when('political tool contracts are inspected')
def contracts(ctx):
    runner = CliRunner()
    ctx['result'] = runner.invoke(app, ['tools', 'describe', 'research.political.import'])


@then('import is explicitly scoped to research and has the authoritative schema')
def scoped(ctx):
    assert ctx['result'].exit_code == 0
    tool = json.loads(ctx['result'].stdout)
    assert tool['mutation_scope'] == 'research'
    assert tool['json_input_schema']['additionalProperties'] is False


def test_schema_four_rejects_three_without_reset(tmp_path):
    from invest.models import DomainError
    path = tmp_path / 'old.db'
    with sqlite3.connect(path) as conn:
        conn.execute('PRAGMA user_version=3')
        conn.execute('CREATE TABLE sentinel (id TEXT)')
    before = path.read_bytes()
    with pytest.raises(DomainError):
        Ledger(path)
    assert path.read_bytes() == before
