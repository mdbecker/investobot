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


def test_confirmed_transactions_are_atomic_and_run_scoped(tmp_path):
    from test_political_models import package as research_package
    from test_political_models import reviewed_policy

    from invest.political import import_research
    from invest.political_queries import summary
    db = Ledger(tmp_path / 'research.db')
    try:
        payload = research_package()
        policy = tmp_path / "policy.json"
        policy.write_text(json.dumps(reviewed_policy()))
        before = db.planning_state()
        first = import_research(db, payload, yes=True, policy_path=policy)
        assert summary(db, first['research_run_id'])['verified_transactions'] == 1
        assert db.planning_state() == before
        changed = copy.deepcopy(payload)
        changed['limitations'].append('Independent follow-up.')
        second = import_research(db, changed, yes=True, policy_path=policy)
        assert first['research_run_id'] != second['research_run_id']
        sources = db.connection.execute('SELECT id,run_id FROM research_political_sources').fetchall()
        contributions = db.connection.execute('SELECT id,run_id FROM research_political_contributions').fetchall()
        foreign_source = next(s[0] for s in sources if s[1] == second['research_run_id'])
        original = next(c[0] for c in contributions if c[1] == first['research_run_id'])
        with pytest.raises(sqlite3.IntegrityError), db.connection:
            db.connection.execute('INSERT INTO research_political_evidence VALUES (?,?,?)',
                                  (original, foreign_source, first['research_run_id']))
        with db.connection:
            db.connection.execute("CREATE TRIGGER fail_research BEFORE INSERT ON research_political_contributions BEGIN SELECT RAISE(ABORT, 'synthetic failure'); END")
        changed['limitations'].append('Fail atomically.')
        with pytest.raises(sqlite3.IntegrityError):
            import_research(db, changed, yes=True, policy_path=policy)
        assert db.connection.execute('SELECT COUNT(*) FROM research_political_runs').fetchone()[0] == 2
        assert db.connection.execute('PRAGMA foreign_key_check').fetchall() == []
    finally:
        db.connection.close()


def test_equivalent_decimal_research_is_idempotent(tmp_path):
    from test_political_models import package as research_package
    from test_political_models import reviewed_policy

    from invest.political import import_research
    db = Ledger(tmp_path / 'normalized.db')
    policy = tmp_path / 'policy.json'
    policy.write_text(json.dumps(reviewed_policy()))
    try:
        first = research_package()
        second = copy.deepcopy(first)
        second['contributions'][0]['amount_usd'] = '1000.0000'
        second['sources'].reverse()
        assert import_research(db, first, yes=True, policy_path=policy)['research_run_id'] == import_research(db, second, yes=True, policy_path=policy)['research_run_id']
    finally:
        db.connection.close()


def test_research_preserves_saved_plan_and_cli_readonly_checks(tmp_path, monkeypatch):
    from planning_fixtures import saved_proposal
    from test_storage_stabilization import snapshot

    from invest.market import MarketClient
    from invest.plans import show
    from invest.political import import_research
    from invest.targets import save
    db_path = tmp_path / 'plan.db'
    db = Ledger(db_path)
    try:
        db.apply(snapshot(10, 'synthetic-original', '2026-10-08'))
        identity = db.resolve('SYN')['id']
        target = save(db, {'name': 'Synthetic allocation',
                          'target_allocations': {identity: '.5', 'CASH': '.5'},
                          'planning_constraints': {'eligible_accounts': ['ira']}})
        client = MarketClient(db, fixture_path='tests/fixtures/fmp-synthetic.json')
        plan = saved_proposal(db, client, target['id'], as_of='2026-10-08')
        before = show(db, plan['id'])
        incoming = package()
        incoming['limitations'] = ['Synthetic limitation ' + str(i) + 'x' * 3000 for i in range(700)]
        file = tmp_path / 'large.json'
        file.write_text(json.dumps(incoming))
        monkeypatch.setenv('INVEST_DB', str(db_path))
        runner = CliRunner()
        db_bytes = db_path.read_bytes()
        assert runner.invoke(app, ['research', 'political', 'validate', str(file)]).exit_code == 0
        preview = runner.invoke(app, ['research', 'political', 'import', str(file)])
        assert preview.exit_code == 0
        assert json.loads(preview.stdout)['committed'] is False
        assert db_path.read_bytes() == db_bytes
        accepted = import_research(db, incoming, yes=True)
        assert show(db, plan['id']) == before
        for args in [['list', '--ticker', 'fiction'], ['show', accepted['research_run_id']],
                     ['summary', accepted['research_run_id']]]:
            result = runner.invoke(app, ['research', 'political', *args])
            assert result.exit_code == 0, result.stderr
            json.loads(result.stdout)
        result = runner.invoke(app, ['research', 'skills', 'show', 'investobot-political-contributions'])
        assert result.exit_code == 0
    finally:
        db.connection.close()
