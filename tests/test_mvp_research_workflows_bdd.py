"""Synthetic offline research/workflow acceptance; no real issuer or donor data.

Public API contracts here are specification, not mocked internal collaborators.
The scripted driver captures actual Typer input/output and never runs an agent.
"""

import copy
import hashlib
import importlib
import json
import socket
import sqlite3
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from typer.testing import CliRunner

from invest.cli import app
from invest.ledger import Ledger
from invest.models import DomainError

scenarios('features/mvp/research_workflows.feature')


@pytest.fixture
def research_ctx(tmp_path, monkeypatch):
    path = tmp_path / 'synthetic-research.sqlite'
    monkeypatch.setenv('INVEST_DB', str(path))
    monkeypatch.setenv('INVEST_PROMPTS', str(tmp_path / 'prompts'))
    monkeypatch.delenv('FMP_API_KEY', raising=False)
    return {'path': path, 'tmp': tmp_path, 'runner': CliRunner(), 'trace': []}


def invoke(ctx, args):
    result = ctx['runner'].invoke(app, args)
    ctx['trace'].append({'argv': args, 'stdout': result.stdout, 'exit_code': result.exit_code})
    assert result.exit_code == 0, f'Command {args} must succeed: {result.output}'
    return json.loads(result.stdout)


def required_module(name):
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as error:
        if error.name != name:
            raise
        pytest.fail(f'Required public {name} capability is absent; substantive assertions follow')


def accepted_household(ctx, source_date='2026-10-10', price='100', cash='2000',
                       history_complete=False):
    """Real accepted source state; search/research must preserve these facts."""
    ledger = Ledger(ctx['path'])
    snapshot = {
        'account': {'id': 'synthetic', 'name': 'Fictional household',
                    'tax_status': 'TAXABLE', 'history_complete': history_complete},
        'positions': [{'security': 'FUND-A', 'asset_type': 'ETF', 'quantity': '10',
                       'price': price, 'market_value': str(Decimal(price) * 10), 'cost_basis': '800',
                       'as_of': source_date, 'displayed_price_precision': 2,
                       'displayed_market_value_precision': 2}],
        'lots': [{'id': 'fictional-lot', 'security': 'FUND-A', 'quantity': '10',
                  'remaining_quantity': '10', 'cost_basis': '800',
                  'remaining_adjusted_basis': '800', 'source_lot_id': 'fictional-lot',
                  'identity_status': 'VERIFIED',
                  'identity_source': 'Reviewed fictional immutable broker lot reference',
                  'acquisition_date': '2024-01-01'}],
        'cash': cash, 'cash_known': True, 'source_hash': 'fictional-source-' + source_date,
        'source_timestamp': source_date, 'positions_complete': True,
        'lots_complete': True, 'data_environment': 'SYNTHETIC'}
    ledger.apply(snapshot)
    ctx['accepted_snapshot'] = snapshot
    ctx['security'] = ledger.resolve('FUND-A')['id']
    ctx['financial_before'] = copy.deepcopy(ledger.planning_state())
    ledger.connection.close()


def assert_financial_unchanged(ctx):
    ledger = Ledger(ctx['path'])
    try:
        assert ledger.planning_state() == ctx['financial_before']
    finally:
        ledger.connection.close()


def batch():
    issuers = [{'issuer_id': f'fictional-{i:02}', 'exposure_weight': '0.05'}
               for i in range(20)]
    return {'manifest_id': 'synthetic-universe-2026-10-10', 'as_of': '2026-10-10',
            'window_start': '2026-10-01', 'window_end': '2026-10-10',
            'data_environment': 'SYNTHETIC', 'requested_top': 20, 'issuers': issuers,
            'research': [{'issuer_id': issuer['issuer_id'], 'status': 'AVAILABLE',
                          'run_id': f'news-{i}', 'run_hash': f'{i:064x}', 'events': []}
                         for i, issuer in enumerate(issuers[:12])]}


@given('a frozen synthetic twenty issuer research batch')
def twenty(research_ctx):
    research_ctx['batch'] = batch()


@given('two sources cite the same synthetic issuer event')
def syndicated(research_ctx):
    research_ctx['batch'] = batch()
    research_ctx['batch']['research'][0]['events'] = [
        {'event_key': 'factory-opened', 'source_id': 'issuer-release',
         'source_url': 'https://example.invalid/issuer/release', 'fact': 'Factory opened.'},
        {'event_key': 'factory-opened', 'source_id': 'syndicated-release',
         'source_url': 'https://example.invalid/wire/release', 'fact': 'Factory opened.'}]


@given('sourced executive and corporate PAC evidence')
def political(research_ctx):
    research_ctx['batch'] = batch()
    research_ctx['batch']['research'][0]['political'] = [
        {'id': 'fictional-executive', 'category': 'EXECUTIVE_PERSONAL', 'amount': '100',
         'permission': 'REVIEWED', 'identity_verified': True, 'source_id': 'executive-record'},
        {'id': 'fictional-pac', 'category': 'CORPORATE_PAC', 'amount': '200',
         'permission': 'REVIEWED', 'relationship_verified': True, 'source_id': 'pac-record'}]


@given('named contributor evidence lacks reviewed permission')
def restricted(research_ctx):
    political(research_ctx)
    research_ctx['batch']['research'][0]['political'][0]['permission'] = 'UNKNOWN'
    research_ctx['batch']['human_approved'] = True


@when('portfolio research is summarized')
def summarize(research_ctx):
    module = required_module('invest.research_portfolio')
    research_ctx['result'] = module.summarize(research_ctx['batch'])


@then('twelve researched issuers cover sixty percent with eight not researched')
def partial(research_ctx):
    result = research_ctx['result']
    assert result['status'] == 'PARTIAL'
    assert result['coverage']['researched_issuers'] == 12
    assert result['coverage']['requested_issuers'] == 20
    assert result['coverage']['researched_weight'] == '0.6'
    assert sum(row['status'] == 'NOT_RESEARCHED' for row in result['companies']) == 8
    assert [row['issuer_id'] for row in result['companies']] == [
        f'fictional-{i:02}' for i in range(20)]


@then('one development retains both source citations')
def dedup(research_ctx):
    events = research_ctx['result']['companies'][0]['events']
    assert len(events) == 1
    assert events[0]['event_key'] == 'factory-opened'
    assert set(events[0]['source_ids']) == {'issuer-release', 'syndicated-release'}


@then('political categories remain separate without stance scores')
def categories(research_ctx):
    result = research_ctx['result']
    assert result['companies'][0]['political_totals'] == {
        'EXECUTIVE_PERSONAL': '100', 'CORPORATE_PAC': '200'}
    assert 'stance_score' not in json.dumps(result)
    assert 'trade_instruction' not in json.dumps(result)


@then('named contributions are excluded with explicit permission diagnostics')
def exclusions(research_ctx):
    result = research_ctx['result']
    assert result['companies'][0]['political_totals'] == {'CORPORATE_PAC': '200'}
    assert any(issue['code'] == 'CONTRIBUTOR_PERMISSION_UNVERIFIED'
               for issue in result['issues'])
    assert result['coverage']['excluded_contributions'] == 1


WORKFLOWS = {
    'sync': ('investobot-portfolio-sync', 'portfolio.reconcile',
             ['portfolio', 'reconcile'], 'explicit human approval'),
    'performance': ('investobot-portfolio-performance', 'portfolio.performance',
                    ['portfolio', 'performance', '--as-of', '2026-10-10'], 'actual'),
    'monthly': ('investobot-monthly-investing', 'plan.propose',
                ['plan', 'propose', '--policy', 'approved-synthetic',
                 '--mode', 'contributions-only', '--as-of', '2026-10-10'], 'human'),
    'harvest': ('investobot-tax-loss-harvesting', 'tax.harvest-plan',
                ['tax', 'harvest-plan', '--as-of', '2026-10-10'], 'review'),
    'screening': ('investobot-investment-screening', 'fund.search',
                  ['fund', 'search'], 'missing'),
    'research': ('investobot-portfolio-research', 'research.portfolio.plan',
                 ['research', 'portfolio', 'plan'], 'coverage'),
    'strategy': ('investobot-portfolio-strategy', 'backtest.compare',
                 ['backtest', 'compare'], 'hypothetical'),
}


@given(parsers.parse('the synthetic {workflow} workflow intent'))
def intent(research_ctx, workflow, monkeypatch):
    research_ctx['workflow'] = workflow
    # Driver inputs are separate from skill prose; Markdown is never executed.
    research_ctx['file'] = research_ctx['tmp'] / 'input.json'
    ledger = Ledger(research_ctx['path'])
    registered = ledger.register_security({'ticker': 'FUND-A', 'name': 'Fictional Fund A',
                                          'asset_type': 'ETF', 'currency': 'USD',
                                          'source': 'Reviewed fictional issuer record'})
    research_ctx['security'] = security = registered['id']
    ledger.connection.close()
    policy = research_ctx['tmp'] / 'policy.toml'
    policy.write_text('[planning]\npolicy_id = "approved-synthetic"\n')
    monkeypatch.setenv('INVEST_CONFIG', str(policy))
    research_ctx['policy_file'] = policy
    research_ctx['policy'] = {
        'id': 'approved-synthetic', 'version': 'approved-synthetic',
        'data_environment': 'SYNTHETIC', 'minimum_notional': '25',
        'fee_per_trade': '0',
        'quarterly_months': [3, 6, 9, 12], 'drift_trigger': '0.05',
        'max_position_age_days': 120, 'cash_floors': {'synthetic': '0'},
        'permissions': {'synthetic': {security: {'can_buy': True, 'can_sell': False,
                                                'can_hold': True, 'share_increment': '0.001'}}},
        'annual_tax_budget': {'year': 2026, 'annual_allowance': '0',
                              'short_term_rate': '0.4', 'long_term_rate': '0.2'},
        'source': 'Explicit fictional human policy approval; no claimed executed consumption',
    }
    inputs = {
        'sync': {'account': {'id': 'synthetic', 'name': 'Fictional household'},
                 'positions': [], 'lots': [], 'source_hash': 'fictional-undated-observation',
                 'source_timestamp': None, 'data_environment': 'SYNTHETIC'},
        'screening': {'expense_ratio_max': '0.002', 'fund_type': 'ETF'},
        'research': {'manifest_id': 'synthetic-universe', 'as_of': '2026-10-10',
                     'data_environment': 'SYNTHETIC', 'issuers': []},
        'strategy': {'candidate_ids': ['synthetic-a', 'synthetic-b'],
                     'start': '2020-01-02', 'end': '2020-01-06',
                     'data_environment': 'SYNTHETIC'},
    }
    inputs['monthly'] = {
        'data_environment': 'SYNTHETIC', 'as_of': '2026-10-10',
        'mode': 'contributions-only', 'account_id': 'synthetic',
        'policy_id': 'approved-synthetic',
        'target': {'id': 'target-synthetic', 'weights': {security: '1'}},
        'prices': {security: {'price': '100', 'as_of': '2026-10-10', 'currency': 'USD',
                              'data_environment': 'SYNTHETIC',
                              'source': 'Reviewed fictional dated market observation',
                              'manifest_id': 'price-synthetic-2026-10-10'}},
        'manifest_ids': ['price-synthetic-2026-10-10'],
    }
    inputs['research']['issuers'] = [
        {'issuer_id': 'fictional-00', 'exposure_weight': '0.6'},
        {'issuer_id': 'fictional-01', 'exposure_weight': '0.4'}]
    inputs['strategy'].update({
        'manifest_ids': ['history-synthetic-2020'],
        'candidates': [{'id': 'synthetic-a', 'weights': {security: '1'}},
                       {'id': 'synthetic-b', 'weights': {security: '0.5', 'CASH': '0.5'}}],
        'history': {security: [{'date': '2020-01-02', 'total_return_index': '100'},
                              {'date': '2020-01-03', 'total_return_index': '105'},
                              {'date': '2020-01-06', 'total_return_index': '110'}]},
        'history_provenance': {'kind': 'DIVIDEND_ADJUSTED_TOTAL_RETURN_INDEX',
                               'frequency': 'DAILY_TRADING_SESSION',
                               'expected_sessions': ['2020-01-02', '2020-01-03', '2020-01-06'],
                               'source_id': 'fictional-history', 'data_environment': 'SYNTHETIC'},
        'cash_return': '0', 'fees': '0', 'starting_value': '1000',
        'rebalancing': 'NONE', 'mode': 'HYPOTHETICAL_CURRENT_ALLOCATION',
    })
    research_ctx['file'].write_text(json.dumps(inputs.get(workflow, {})))
    initial_market = write_input(research_ctx, 'initial-market.json', {
        'data_environment': 'SYNTHETIC',
        'screen': [{'symbol': 'FUND-A', 'isEtf': True, 'isFund': False}],
        'metadata': {'FUND-A': [{'symbol': 'FUND-A', 'isEtf': True,
                                'issuer': 'Fictional fund issuer'}]},
    })
    monkeypatch.setenv('INVEST_FIXTURES', initial_market)


@when('its installed skill is followed by a scripted CLI driver')
def scripted(research_ctx):
    from invest.research_skills import install_skills

    workflow = research_ctx['workflow']
    name, tool, args, boundary = WORKFLOWS[workflow]
    install_skills('codex', research_ctx['tmp'])
    skill_path = research_ctx['tmp'] / '.agents' / 'skills' / name / 'SKILL.md'
    assert skill_path.is_file(), f'{name} must be distributed and installable'
    text = skill_path.read_text()
    assert 'invest tools describe' in text
    assert boundary in text.lower()
    research_ctx['descriptor'] = invoke(research_ctx, ['tools', 'describe', tool])
    if workflow in {'monthly', 'strategy'}:
        accepted_household(research_ctx)
        approve_policy(research_ctx)
    if workflow in {'sync', 'screening'}:
        args = [*args, str(research_ctx['file'])]
    elif workflow == 'research':
        manifest = invoke(research_ctx, ['data', 'snapshot', '--file', str(research_ctx['file'])])
        args = [*args, '--universe-manifest', manifest['manifest_id']]
    elif workflow == 'monthly':
        args = [*args, '--file', str(research_ctx['file'])]
    elif workflow == 'strategy':
        args = [*args, str(research_ctx['file'])]
    research_ctx['result'] = invoke(research_ctx, args)


@then(parsers.parse('the {workflow} workflow obeys its boundary and reports its outcome'))
def workflow_outcome(research_ctx, workflow):
    result = research_ctx['result']
    if workflow in {'monthly', 'research', 'strategy'}:
        assert result['status'] in {'AVAILABLE', 'READY_FOR_HUMAN_REVIEW', 'PARTIAL'}
    else:
        assert result['status'] in {'UNAVAILABLE', 'BLOCKED', 'REVIEW_REQUIRED', 'PARTIAL'}
    assert all(isinstance(i['blocks_execution_review'], bool)
                                    for i in result['issues'])
    assert all('--yes' not in step['argv'] and '--confirm' not in step['argv']
               for step in research_ctx['trace'])
    if workflow == 'performance':
        assert result['mode'] == 'ACTUAL'
        assert result['twr']['return'] is None
        assert result['xirr']['annualized_return'] is None
    elif workflow == 'monthly':
        assert result['executed'] is False
        assert result['id']
        assert result['policy_id'] == 'approved-synthetic'
        assert result['manifest_ids'] == ['price-synthetic-2026-10-10']
        assert result['proposed_actions'] == [{'type': 'BUY', 'account_id': 'synthetic',
                                              'security': research_ctx['security'],
                                              'quantity': '20', 'notional': '2000'}]
        assert result['estimated_tax_budget_consumption'] == '0'
    elif workflow == 'harvest':
        assert result['wash_sale_certified'] is False
    elif workflow == 'screening':
        assert result['coverage']['missing_characteristics']
    elif workflow == 'research':
        assert result['coverage']['researched_issuers'] == 0
        assert [row['issuer_id'] for row in result['queue']] == ['fictional-00', 'fictional-01']
        assert all(row['status'] == 'NOT_RESEARCHED' for row in result['queue'])
        assert result['id'] and result['universe_manifest_id']
    elif workflow == 'strategy':
        assert result['classification'] == 'HYPOTHETICAL'
        assert result['comparable'] is True
        assert result['manifest_ids'] == ['history-synthetic-2020']
        assert result['period'] == {'start': '2020-01-02', 'end': '2020-01-06'}
        assert [row['total_return'] for row in result['candidates']] == ['0.1', '0.05']
        assert len(result['transition_plans']) == 2
        assert all(plan['executed'] is False for plan in result['transition_plans'])


@given('a registered portfolio performance command')
def registered(research_ctx):
    research_ctx['tool'] = 'portfolio.performance'


@when('its descriptor and executable help are read')
def metadata(research_ctx):
    research_ctx['descriptor'] = invoke(research_ctx, ['tools', 'describe', research_ctx['tool']])
    research_ctx['help'] = research_ctx['runner'].invoke(app, ['portfolio', 'performance', '--help'])
    research_ctx['result'] = invoke(research_ctx, ['portfolio', 'performance',
                                                '--as-of', '2026-10-10'])


@then('flags schema mutation scope and structured result agree')
def authoritative(research_ctx):
    descriptor = research_ctx['descriptor']
    assert descriptor['mutation_scope'] == 'read'
    assert descriptor['mutates_persistent_state'] is False
    assert descriptor['json_input_schema']['additionalProperties'] is False
    assert '--as-of' in research_ctx['help'].stdout
    assert any('--as-of' in flag['flags'] for flag in descriptor['parameters'])
    assert research_ctx['result']['status'] == 'UNAVAILABLE'
    assert research_ctx['result']['as_of'] == '2026-10-10'


@given('a synthetic SQLite corpus with permitted and forbidden passages')
def corpus(research_ctx, monkeypatch):
    def offline(*args, **kwargs):
        raise AssertionError('Search must not make an external network request')

    monkeypatch.setattr(socket.socket, 'connect', offline)
    accepted_household(research_ctx)
    research_ctx['documents'] = [
        {'chunk_id': 'permitted', 'document_id': 'public-doc', 'issuer_id': 'fictional-00',
         'source_url': 'https://example.invalid/public', 'source_date': '2026-10-01',
         'permission': 'PERMITTED', 'text': 'Copper factory output increased.',
         'model_id': 'synthetic-model-a', 'vector': [1.0, 0.0], 'data_environment': 'SYNTHETIC',
         'content_hash': hashlib.sha256(b'Copper factory output increased.').hexdigest(),
         'offset_start': 0, 'offset_end': 32, 'license': 'FICTIONAL_TEST_PERMISSION'},
        {'chunk_id': 'forbidden', 'document_id': 'restricted-doc', 'issuer_id': 'fictional-00',
         'source_url': 'https://example.invalid/restricted', 'source_date': '2026-10-01',
         'permission': 'DENIED', 'text': 'Copper factory confidential output increased.',
         'model_id': 'synthetic-model-a', 'vector': [1.0, 0.0], 'data_environment': 'SYNTHETIC',
         'content_hash': hashlib.sha256(b'Copper factory confidential output increased.').hexdigest(),
         'offset_start': 0, 'offset_end': 45, 'license': 'FICTIONAL_RESTRICTED'}]
    for document in research_ctx['documents']:
        document['offset_end'] = len(document['text'])


def search_module(ctx):
    module = required_module('invest.search')
    module.store_chunks(ctx['path'], ctx['documents'], confirmed=True)
    return module


@when('keyword research retrieval runs without embeddings')
def lexical(research_ctx):
    module = search_module(research_ctx)
    research_ctx['result'] = module.search(research_ctx['path'], query='Copper', top_k=10)


@then('cited permitted matching passages are returned without network access')
def cited(research_ctx):
    result = research_ctx['result']
    assert result['method'] == 'FTS5'
    assert [row['chunk_id'] for row in result['results']] == ['permitted']
    row = result['results'][0]
    assert row['source_url'] == 'https://example.invalid/public'
    assert row['source_date'] == '2026-10-01'
    assert row['permission'] == 'PERMITTED'
    assert row['passage'] == 'Copper factory output increased.'
    assert result['external_calls'] == 0


@when('incompatible semantic queries are submitted')
def mismatches(research_ctx):
    module = search_module(research_ctx)
    research_ctx['model_mismatch'] = module.search(
        research_ctx['path'], query='Copper', vector=[1.0, 0.0], model_id='synthetic-model-b')
    research_ctx['dimension_mismatch'] = module.search(
        research_ctx['path'], query='Copper', vector=[1.0, 0.0, 0.0],
        model_id='synthetic-model-a')
    research_ctx['result'] = module.search(research_ctx['path'], query='Copper')


@then('both model and dimension mismatches are explicit and text retrieval still works')
def rejects(research_ctx):
    for key, code in [('model_mismatch', 'EMBEDDING_MODEL_MISMATCH'),
                      ('dimension_mismatch', 'EMBEDDING_DIMENSION_MISMATCH')]:
        result = research_ctx[key]
        assert result['status'] == 'BLOCKED'
        assert result['results'] == []
        assert any(issue['code'] == code for issue in result['issues'])
    cited(research_ctx)


@when('the derived vector index is dropped rebuilt and searched')
def rebuild(research_ctx):
    module = search_module(research_ctx)
    connection = module.open_search_connection(research_ctx['path'])
    research_ctx['before'] = list(connection.execute('SELECT * FROM document_chunks ORDER BY 1'))
    research_ctx['vectors'] = list(connection.execute('SELECT * FROM embeddings ORDER BY 1'))
    indexes = list(connection.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='table' AND sql LIKE '%USING vec0%'") )
    assert indexes, 'Semantic retrieval must use a real sqlite-vec virtual table'
    for name, sql in indexes:
        assert 'USING vec0' in sql
        connection.execute('DROP TABLE "' + name.replace('"', '""') + '"')
    connection.commit()
    connection.close()
    module.rebuild_index(research_ctx['path'])
    research_ctx['result'] = module.search(research_ctx['path'], query='Copper',
                                           vector=[1.0, 0.0], model_id='synthetic-model-a')


@then('canonical vectors documents and financial rows stay identical and retrieval returns')
def preserved(research_ctx):
    with sqlite3.connect(research_ctx['path']) as connection:
        assert list(connection.execute('SELECT * FROM document_chunks ORDER BY 1')) == research_ctx['before']
        assert list(connection.execute('SELECT * FROM embeddings ORDER BY 1')) == research_ctx['vectors']
    assert_financial_unchanged(research_ctx)
    assert [row['chunk_id'] for row in research_ctx['result']['results']] == ['permitted']
    assert research_ctx['result']['method'] in {'VECTOR', 'HYBRID'}


@when('matching text and compatible vectors are queried')
def both(research_ctx):
    module = search_module(research_ctx)
    research_ctx['results'] = [module.search(research_ctx['path'], query='Copper'),
                               module.search(research_ctx['path'], query='Copper',
                                             vector=[1.0, 0.0], model_id='synthetic-model-a')]


@then('forbidden evidence is absent from both retrieval methods')
def permitted_only(research_ctx):
    for result in research_ctx['results']:
        assert [row['chunk_id'] for row in result['results']] == ['permitted']
        assert all(row['permission'] == 'PERMITTED' for row in result['results'])
        assert result['coverage']['excluded_permission_chunks'] == 1


@given('a real accepted synthetic household and a cited research envelope')
def research_envelope(research_ctx):
    accepted_household(research_ctx)
    research_ctx['envelope'] = {
        'kind': 'NEWS', 'issuer_id': 'fictional-00', 'as_of': '2026-10-10',
        'data_environment': 'SYNTHETIC', 'skill_name': 'investobot-news',
        'package': fictional_news_package(),
    }


def research_rows(ctx):
    with sqlite3.connect(ctx['path']) as connection:
        return {table: list(connection.execute(f'SELECT * FROM {table} ORDER BY 1'))
                for table in ['research_runs', 'research_artifacts']}


@when('research is previewed and explicitly accepted twice')
def persistence(research_ctx):
    module = required_module('invest.research_storage')
    ledger = Ledger(research_ctx['path'])
    try:
        research_ctx['before_research'] = research_rows(research_ctx)
        research_ctx['preview'] = module.import_run(ledger, research_ctx['envelope'], confirmed=False)
        assert research_rows(research_ctx) == research_ctx['before_research']
        research_ctx['accepted'] = module.import_run(ledger, research_ctx['envelope'], confirmed=True)
        research_ctx['accepted_rows'] = research_rows(research_ctx)
        research_ctx['repeat'] = module.import_run(ledger, research_ctx['envelope'], confirmed=True)
        research_ctx['retrieved'] = module.show(ledger, research_ctx['accepted']['run_id'])
    finally:
        ledger.connection.close()


@then('preview writes nothing repeat is a no-op and financial state is identical')
def persistence_invariants(research_ctx):
    assert research_ctx['preview']['committed'] is False
    assert research_ctx['accepted']['committed'] is True
    assert research_ctx['repeat']['committed'] is False
    assert research_ctx['repeat']['run_id'] == research_ctx['accepted']['run_id']
    assert research_rows(research_ctx) == research_ctx['accepted_rows']
    assert research_ctx['retrieved']['package'] == research_ctx['envelope']['package']
    assert research_ctx['retrieved']['skill_version']
    assert_financial_unchanged(research_ctx)


@when('a batch contains a conflicting evidence identity')
def atomic_research(research_ctx):
    module = required_module('invest.research_storage')
    second = copy.deepcopy(research_ctx['envelope'])
    second['package']['sources'].append(dict(second['package']['sources'][0],
                                              url='https://example.invalid/conflicting-release'))
    ledger = Ledger(research_ctx['path'])
    try:
        research_ctx['before_research'] = research_rows(research_ctx)
        with pytest.raises(DomainError) as error:
            module.import_batch(ledger, [research_ctx['envelope'], second], confirmed=True)
        research_ctx['error'] = str(error.value)
    finally:
        ledger.connection.close()


@then('the batch is rejected without partial research or financial changes')
def atomic_invariants(research_ctx):
    assert 'identity' in research_ctx['error'].lower() or 'conflict' in research_ctx['error'].lower()
    assert research_rows(research_ctx) == research_ctx['before_research']
    assert_financial_unchanged(research_ctx)


@given('the issuer PAC relationship is unverified')
def pac_unknown(research_ctx):
    research_ctx['batch']['research'][0]['political'][1]['relationship_verified'] = False


@then('only executive contributions are counted and PAC relationship is unresolved')
def pac_excluded(research_ctx):
    result = research_ctx['result']
    assert result['companies'][0]['political_totals'] == {'EXECUTIVE_PERSONAL': '100'}
    assert any(issue['code'] == 'ISSUER_PAC_RELATIONSHIP_UNVERIFIED' for issue in result['issues'])
    assert result['coverage']['excluded_contributions'] == 1


@given('dated research with disputed and not reobserved developments')
def disputed(research_ctx):
    twenty(research_ctx)
    research_ctx['batch']['research'][0]['events'] = [
        {'event_key': 'factory-opened', 'event_date': '2026-09-29',
         'published_at': '2026-10-02', 'event_status': 'DISPUTED',
         'source_id': 'fictional-release', 'fact': 'Opening is disputed.'},
        {'event_key': 'old-expansion', 'event_date': '2026-08-01',
         'published_at': '2026-08-02', 'event_status': 'NOT_REOBSERVED',
         'source_id': 'fictional-old-release', 'fact': 'Prior expansion remains unobserved.'}]


@then('occurrence publication dates and unresolved event statuses remain distinct')
def distinct_dates(research_ctx):
    events = research_ctx['result']['companies'][0]['events']
    rows = {row['event_key']: row for row in events}
    assert rows['factory-opened']['event_date'] == '2026-09-29'
    assert rows['factory-opened']['published_at'] == '2026-10-02'
    assert rows['factory-opened']['event_status'] == 'DISPUTED'
    assert rows['factory-opened']['predates_window'] is True
    assert rows['old-expansion']['event_status'] == 'NOT_REOBSERVED'
    assert all(row.get('resolved') is not True for row in rows.values())


def canonical_corpus(ctx):
    with sqlite3.connect(ctx['path']) as connection:
        return {table: list(connection.execute(f'SELECT * FROM {table} ORDER BY 1'))
                for table in ['document_chunks', 'embeddings']}


@when('source text and embedding model are explicitly revised')
def revise(research_ctx):
    module = search_module(research_ctx)
    research_ctx['original'] = canonical_corpus(research_ctx)
    revised = copy.deepcopy(research_ctx['documents'][0])
    revised.update(chunk_id='permitted-revision', text='Copper factory output fell.',
                   model_id='synthetic-model-b', vector=[0.0, 1.0], supersedes_chunk_id='permitted',
                   content_hash=hashlib.sha256(b'Copper factory output fell.').hexdigest(),
                   offset_end=len('Copper factory output fell.'))
    module.store_chunks(research_ctx['path'], [revised], confirmed=True)
    research_ctx['revision_result'] = module.search(research_ctx['path'], query='Copper',
                                                   vector=[0.0, 1.0], model_id='synthetic-model-b')


@then('prior chunks and vectors remain unchanged with distinct revision provenance')
def immutable_versions(research_ctx):
    current = canonical_corpus(research_ctx)
    for table, rows in research_ctx['original'].items():
        assert all(row in current[table] for row in rows)
    assert len(current['document_chunks']) == len(research_ctx['original']['document_chunks']) + 1
    row = research_ctx['revision_result']['results'][0]
    assert row['chunk_id'] == 'permitted-revision'
    assert row['model_id'] == 'synthetic-model-b'
    assert row['supersedes_chunk_id'] == 'permitted'
    assert row['content_hash'] == hashlib.sha256(b'Copper factory output fell.').hexdigest()
    assert row['offset_start'] == 0
    assert row['offset_end'] == len('Copper factory output fell.')
    assert_financial_unchanged(research_ctx)


@when(parsers.parse('a {kind} vector is submitted'))
def invalid_vector(research_ctx, kind):
    module = search_module(research_ctx)
    research_ctx['original'] = canonical_corpus(research_ctx)
    vectors = {'zero': [0.0, 0.0], 'nonfinite': [float('nan'), 0.0],
               'nonunit': [2.0, 0.0], 'empty': []}
    revised = dict(research_ctx['documents'][0], chunk_id='invalid-vector', vector=vectors[kind])
    with pytest.raises(DomainError) as error:
        module.store_chunks(research_ctx['path'], [revised], confirmed=True)
    research_ctx['error'] = str(error.value)


@then('invalid vectors cannot mutate canonical corpus or financial state')
def reject_vectors(research_ctx):
    assert 'vector' in research_ctx['error'].lower() or 'embedding' in research_ctx['error'].lower()
    assert canonical_corpus(research_ctx) == research_ctx['original']
    assert_financial_unchanged(research_ctx)


@when('issuer date and top-k constrained searches are repeated')
def filtering(research_ctx):
    module = search_module(research_ctx)
    other = dict(research_ctx['documents'][0], chunk_id='other-issuer', issuer_id='fictional-99')
    earlier = dict(research_ctx['documents'][0], chunk_id='old-observation', source_date='2025-01-01')
    tied = dict(research_ctx['documents'][0], chunk_id='permitted-tie')
    module.store_chunks(research_ctx['path'], [other, earlier, tied], confirmed=True)
    options = {'query': 'Copper', 'issuer_id': 'fictional-00', 'date_from': '2026-10-01',
               'date_to': '2026-10-10', 'top_k': 1, 'vector': [1.0, 0.0],
               'model_id': 'synthetic-model-a'}
    research_ctx['results'] = [module.search(research_ctx['path'], **options) for _ in range(2)]


@then('filters apply before ranking and hybrid components have stable ties')
def stable_filters(research_ctx):
    first, second = research_ctx['results']
    assert first == second
    assert first['method'] == 'HYBRID'
    assert [row['chunk_id'] for row in first['results']] == ['permitted']
    row = first['results'][0]
    assert row['issuer_id'] == 'fictional-00'
    assert row['source_date'] == '2026-10-01'
    assert row['cosine_score'] == 1.0
    assert isinstance(row['term_score'], (int, float))
    assert row['license'] == 'FICTIONAL_TEST_PERMISSION'
    assert_financial_unchanged(research_ctx)


@when('the real derived vector index is removed without rebuilding')
def unavailable_vectors(research_ctx):
    module = search_module(research_ctx)
    connection = module.open_search_connection(research_ctx['path'])
    try:
        names = [row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND sql LIKE '%USING vec0%'")]
        assert names, 'Real sqlite-vec index must exist before exercising index loss'
        for name in names:
            connection.execute('DROP TABLE "' + name.replace('"', '""') + '"')
        connection.commit()
    finally:
        connection.close()
    research_ctx['semantic'] = module.search(research_ctx['path'], query='Copper',
                                             vector=[1.0, 0.0], model_id='synthetic-model-a')
    research_ctx['result'] = module.search(research_ctx['path'], query='Copper')


@then('semantic availability is explicit and keyword retrieval remains cited')
def lexical_fallback(research_ctx):
    assert research_ctx['semantic']['status'] == 'UNAVAILABLE'
    assert any(issue['code'] == 'VECTOR_INDEX_UNAVAILABLE'
               for issue in research_ctx['semantic']['issues'])
    cited(research_ctx)
    assert_financial_unchanged(research_ctx)


@when('an unapproved embedding operation names an adapter')
def unauthorized_embedding(research_ctx):
    module = search_module(research_ctx)
    embedding = required_module('invest.embedding')
    research_ctx['original'] = canonical_corpus(research_ctx)
    calls = []

    def external_adapter(texts):
        calls.append(texts)
        return [[1.0, 0.0] for _ in texts]

    research_ctx['calls'] = calls
    with pytest.raises(DomainError):
        embedding.generate(module, research_ctx['path'], ['permitted'],
                           model_id='synthetic-model-a', adapter=external_adapter,
                           user_authorized=False)


@then('adapter is never invoked and no vectors or financial facts change')
def no_adapter(research_ctx):
    assert research_ctx['calls'] == []
    assert canonical_corpus(research_ctx) == research_ctx['original']
    assert_financial_unchanged(research_ctx)


@when('private broker and named contributor documents are submitted without indexing rights')
def sensitive_corpus(research_ctx):
    module = search_module(research_ctx)
    research_ctx['original'] = canonical_corpus(research_ctx)
    private = dict(research_ctx['documents'][0], chunk_id='private-broker',
                   document_kind='BROKER_ACCOUNT_HTML', permission='UNKNOWN')
    named = dict(research_ctx['documents'][0], chunk_id='private-contributor',
                 document_kind='NAMED_PERSONAL_CONTRIBUTION', permission='UNKNOWN')
    with pytest.raises(DomainError):
        module.store_chunks(research_ctx['path'], [private, named], confirmed=True)
    research_ctx['result'] = module.search(research_ctx['path'], query='Copper')


@then('private chunks are rejected atomically and absent from retrieval')
def privacy_corpus(research_ctx):
    assert canonical_corpus(research_ctx) == research_ctx['original']
    assert [row['chunk_id'] for row in research_ctx['result']['results']] == ['permitted']
    assert_financial_unchanged(research_ctx)


def write_input(ctx, filename, data):
    path = ctx['tmp'] / filename
    path.write_text(json.dumps(data))
    return str(path)


@given(parsers.parse('the complete synthetic {workflow} walkthrough with {mode} inputs'))
def full_intent(research_ctx, workflow, mode, monkeypatch):
    intent(research_ctx, workflow, monkeypatch)
    if workflow == 'performance' and mode == 'success':
        accepted_household(research_ctx, source_date='2025-10-10', cash='0', history_complete=True)
        closing = copy.deepcopy(research_ctx['accepted_snapshot'])
        closing.update(source_timestamp='2026-10-10', source_hash='fictional-closing-performance')
        closing['positions'][0].update(price='110', market_value='1100', as_of='2026-10-10')
        ledger = Ledger(research_ctx['path'])
        ledger.apply(closing)
        research_ctx['financial_before'] = copy.deepcopy(ledger.planning_state())
        ledger.connection.close()
    else:
        accepted_household(research_ctx, history_complete=workflow == 'harvest' and mode == 'success')
    research_ctx['mode'] = mode
    research_ctx['report_path'] = research_ctx['tmp'] / 'immutable-report.md'
    market_data = {
        'data_environment': 'SYNTHETIC',
        'screen': [{'symbol': 'FUND-A', 'isEtf': True, 'isFund': False}],
        'metadata': {'FUND-A': [{'symbol': 'FUND-A', 'expenseRatio': '0.001',
                                'issuer': 'Fictional issuer', 'aum': '1000000', 'isEtf': True}]},
        'holdings': {'FUND-A': [{'asset': 'FICT-A', 'name': 'Fictional Operating Company',
                                'weightPercentage': '100', 'updated': '2026-10-01',
                                'isin': 'USFICT000001', 'cusip': 'FICT00001',
                                'assetType': 'STOCK', 'cik': '0000123456',
                                }]},
        'history': {'FUND-A': [{'date': '2020-01-02', 'total_return_index': '100'},
                              {'date': '2020-01-03', 'total_return_index': '105'},
                              {'date': '2020-01-06', 'total_return_index': '110'}]},
        'history_provenance': {'kind': 'DIVIDEND_ADJUSTED_TOTAL_RETURN_INDEX',
                               'frequency': 'DAILY_TRADING_SESSION',
                               'source_id': 'fictional-history'},
    }
    if mode == 'blocked':
        market_data['metadata']['FUND-A'][0].pop('expenseRatio')
        market_data['history']['FUND-A'] = []
    fixture = write_input(research_ctx, 'market.json', market_data)
    monkeypatch.setenv('INVEST_FIXTURES', fixture)
    research_ctx['html'] = research_ctx['tmp'] / 'synthetic-statement.html'
    research_ctx['html'].write_text(
        '<table><tr><th>Symbol</th><th>Quantity</th><th>Price</th><th>Market Value</th>'
        '<th>Cost Basis</th><th>Acquisition Date</th><th>Lot ID</th>'
        '<th>Lot Identity Source</th></tr>'
        '<tr><td>FUND-A</td><td>10.000</td><td>100.00</td><td>1000.00</td><td>800.00</td>'
        '<td>2024-01-01</td><td>fictional-lot</td>'
        '<td>Reviewed fictional immutable broker lot reference</td></tr></table>')
    research_ctx['target_file'] = write_input(research_ctx, 'target.json', {
        'name': 'Synthetic allocation', 'data_environment': 'SYNTHETIC',
        'target_allocations': {research_ctx['security']: '1', 'CASH': '0'},
        'planning_constraints': {'eligible_accounts': ['synthetic'],
                                 'permitted_securities': {'synthetic': [research_ctx['security']]}}})
    payload = json.loads(research_ctx['file'].read_text())
    if workflow == 'monthly' and mode == 'blocked':
        research_ctx['policy']['permissions']['synthetic'].pop(research_ctx['security'])
    if workflow == 'strategy' and mode == 'blocked':
        payload['history'][research_ctx['security']] = []
    research_ctx['file'].write_text(json.dumps(payload))
    research_ctx['screen_file'] = write_input(research_ctx, 'screen.json', {
        'expense_ratio_max': '0.002', 'fund_type': 'ETF'})
    research_ctx['harvest_file'] = write_input(research_ctx, 'harvest.json', {
        'loss_sale_date': '2026-10-10', 'security': research_ctx['security'],
        'data_environment': 'SYNTHETIC',
        'spouse_history_complete': False,
        'outside_account_history_complete': False,
        'dividend_reinvestment_history_complete': None,
        'replacement': {'security': 'FUND-A', 'security_id': research_ctx['security'],
                        'substantially_identical': None, 'approved_for_purchase': False,
                        'source': 'Fictional candidate only; no replacement permission or legal conclusion'},
        'scheduled_acquisitions': [],
    })
    if workflow == 'harvest':
        ledger = Ledger(research_ctx['path'])
        try:
            ledger.apply({
                'account': {'id': 'fictional-ira', 'name': 'Fictional household IRA',
                            'tax_status': 'TAX_DEFERRED', 'currency': 'USD',
                            'history_complete': mode == 'success'},
                'positions': [], 'lots': [], 'cash': '100', 'cash_known': True,
                'positions_complete': True, 'lots_complete': True,
                'source_timestamp': '2026-09-19T16:00:00Z',
                'source_hash': 'fictional-ira-opening-observation',
                'data_environment': 'SYNTHETIC'})
            purchase = ledger.record_activity({
                'activity_id': 'fictional-ira-purchase-2026-09-20',
                'account_id': 'fictional-ira', 'type': 'BUY',
                'date': '2026-09-20', 'event_timestamp': '2026-09-20T15:00:00Z',
                'security': research_ctx['security'], 'quantity': '1', 'price': '100',
                'fee': '0',
                'source': 'Explicit fictional human confirmation of IRA broker purchase record'}, yes=True)
            assert purchase['committed'] is True
            research_ctx['financial_before'] = copy.deepcopy(ledger.planning_state())
        finally:
            ledger.connection.close()
    research_ctx['news_file'] = write_input(research_ctx, 'news.json', fictional_news_package())
    if workflow == 'research':
        ledger = Ledger(research_ctx['path'])
        try:
            stock = ledger.register_security({
                'ticker': 'FICT-A', 'name': 'Fictional Operating Company',
                'asset_type': 'STOCK', 'currency': 'USD',
                'isin': 'USFICT000001', 'cusip': 'FICT00001',
                'cik': '0000123456', 'issuer_id': '0000123456',
                'data_environment': 'SYNTHETIC',
                'issuer_identity_evidence': {
                    'source_locator': 'https://example.invalid/fictional-issuer-register',
                    'source': 'Explicit fictional human review of original issuer registration',
                    'reviewed': True, 'cik': '0000123456'},
                'source': 'Explicit fictional human review of original issuer registration; '
                          'CIK 0000123456, ISIN USFICT000001, CUSIP FICT00001'})
            research_ctx['research_security'] = stock['id']
            research_ctx['financial_before'] = copy.deepcopy(ledger.planning_state())
        finally:
            ledger.connection.close()
        package = fictional_news_package()
        package['company'].update(cik='0000123456', security_id=stock['id'])
        research_ctx['news_file'] = write_input(research_ctx, 'news.json', package)


def workflow_step(ctx, args):
    """Capture only real CLI behavior; never execute skill Markdown."""
    family = 'invest ' + ' '.join(args[:2])
    assert family in ctx['skill_text'], f'Skill walkthrough must document {family}'
    return invoke(ctx, args)


@when('the portable skill documented command sequence is scripted')
def full_driver(research_ctx):
    from invest.research_skills import install_skills

    ctx = research_ctx
    workflow, mode = ctx['workflow'], ctx['mode']
    name = WORKFLOWS[workflow][0]
    for agent, directory in [('codex', '.agents'), ('claude-code', '.claude')]:
        install_skills(agent, ctx['tmp'])
        path = ctx['tmp'] / directory / 'skills' / name / 'SKILL.md'
        assert path.is_file(), f'{name} must be installable for {agent}'
        text = path.read_text()
        for required in ['prerequisites', 'blocked', 'success', 'manifest', 'batch', 'approval']:
            assert required in text.lower(), f'{name} omits its {required} contract'
        ctx['skill_text'] = text
    invoke(ctx, ['tools', 'describe', WORKFLOWS[workflow][1]])
    invoke(ctx, ['schema'])
    if workflow in {'monthly', 'harvest', 'strategy'}:
        approve_policy(ctx)
    if workflow == 'sync':
        args = ['portfolio', 'import', str(ctx['html']), '--account', 'synthetic',
                '--positions-complete', '--lots-complete', '--data-environment', 'SYNTHETIC']
        if mode == 'success':
            args.extend(['--as-of', '2026-10-11'])
        candidate = workflow_step(ctx, args)
        candidate_file = write_input(ctx, 'candidate.json', candidate)
        ctx['reconciliation'] = workflow_step(ctx, ['portfolio', 'reconcile', candidate_file])
        if mode == 'success':
            ctx['authorization_granted'] = True
            workflow_step(ctx, ['portfolio', 'apply', candidate_file, '--confirm'])
        ctx['result'] = workflow_step(ctx, ['portfolio', 'check', '--as-of', '2026-10-11'])
    elif workflow == 'performance':
        workflow_step(ctx, ['portfolio', 'check', '--as-of', '2026-10-10'])
        ctx['result'] = workflow_step(ctx, ['portfolio', 'performance', '--as-of', '2026-10-10',
                                             '--from', '2025-10-10', '--to', '2026-10-10'])
    elif workflow == 'monthly':
        workflow_step(ctx, ['target', 'save', ctx['target_file']])
        workflow_step(ctx, ['portfolio', 'check', '--as-of', '2026-10-10'])
        ctx['result'] = workflow_step(ctx, ['plan', 'propose', '--file', str(ctx['file']),
                                             '--policy', 'approved-synthetic',
                                             '--mode', 'contributions-only',
                                             '--as-of', '2026-10-10'])
        workflow_step(ctx, ['tax', 'budget', '--year', '2026', '--as-of', '2026-10-10'])
        if mode == 'success':
            saved = workflow_step(ctx, ['plan', 'show', ctx['result']['id']])
            assert saved['id'] == ctx['result']['id']
            workflow_step(ctx, ['report', 'export', ctx['result']['id'],
                               '--output', str(ctx['report_path'])])
    elif workflow == 'harvest':
        workflow_step(ctx, ['tax', 'lots', '--as-of', '2026-10-10'])
        workflow_step(ctx, ['tax', 'harvest-candidates', '--as-of', '2026-10-10'])
        workflow_step(ctx, ['fund', 'replacements', 'FUND-A', 'FUND-A'])
        ctx['result'] = workflow_step(ctx, ['tax', 'harvest-plan', '--file', ctx['harvest_file'],
                                             '--as-of', '2026-10-10'])
    elif workflow == 'screening':
        ctx['result'] = workflow_step(ctx, ['fund', 'search', ctx['screen_file']])
        ctx['comparison'] = workflow_step(ctx, ['fund', 'compare', 'FUND-A', 'FUND-A'])
        # This fixture lacks original-source identity permission: never register automatically.
    elif workflow == 'research':
        workflow_step(ctx, ['portfolio', 'exposure', '--as-of', '2026-10-10'])
        universe = workflow_step(ctx, ['portfolio', 'research-universe', '--as-of', '2026-10-10',
                                      '--top', '20', '--min-exposure', '0'])
        portfolio_research = required_module('invest.research_portfolio')
        frozen = portfolio_research.freeze_universe(universe, requested_top=20,
                                                    as_of='2026-10-10')
        assert [row['issuer_id'] for row in frozen['issuers']] == [
            row['issuer_id'] for row in universe['companies']]
        assert frozen['coverage']['unknown_exposure_value'] == universe['unknown_exposure_value']
        assert frozen['coverage']['filtered_exposure_value'] == universe['filtered_exposure_value']
        manifest = workflow_step(ctx, ['data', 'snapshot', '--file',
                                      write_input(ctx, 'research-universe.json', frozen)])
        plan = workflow_step(ctx, ['research', 'portfolio', 'plan', '--universe-manifest',
                                  manifest['manifest_id']])
        if mode == 'success':
            workflow_step(ctx, ['research', 'news', 'validate', ctx['news_file']])
            preview = workflow_step(ctx, ['research', 'news', 'import', ctx['news_file']])
            assert preview['committed'] is False
            ctx['authorization_granted'] = True
            workflow_step(ctx, ['research', 'news', 'import', ctx['news_file'], '--yes'])
        ctx['result'] = workflow_step(ctx, ['research', 'portfolio', 'report', '--plan', plan['id']])
    else:
        workflow_step(ctx, ['target', 'save', ctx['target_file']])
        workflow_step(ctx, ['backtest', 'run', str(ctx['file'])])
        ctx['result'] = workflow_step(ctx, ['backtest', 'compare', str(ctx['file'])])
        for candidate in json.loads(ctx['file'].read_text())['candidates']:
            transition = write_input(ctx, candidate['id'] + '-transition.json', {
                'target': candidate, 'data_environment': 'SYNTHETIC',
                'as_of': '2026-10-10', 'mode': 'rebalance'})
            workflow_step(ctx, ['plan', 'propose', '--file', transition,
                               '--policy', 'approved-synthetic', '--mode', 'rebalance',
                               '--as-of', '2026-10-10'])


@then(parsers.parse('the complete {workflow} sequence preserves its {mode} authorization boundary'))
def full_boundary(research_ctx, workflow, mode):
    ctx, result = research_ctx, research_ctx['result']
    for step in ctx['trace']:
        if '--yes' in step['argv'] or '--confirm' in step['argv']:
            assert mode == 'success' and ctx.get('authorization_granted') is True
            assert workflow in {'sync', 'research'}
    if workflow != 'sync' or mode == 'blocked':
        assert_financial_unchanged(ctx)
    if mode == 'blocked':
        assert result['status'] in {'UNAVAILABLE', 'BLOCKED', 'REVIEW_REQUIRED', 'PARTIAL'}
        assert result['issues']
        assert not ctx.get('authorization_granted', False)
    if workflow == 'sync':
        if mode == 'blocked':
            assert any(issue['code'] == 'UNKNOWN_SOURCE_DATE'
                       for issue in ctx['reconciliation']['issues'])
        else:
            ledger = Ledger(ctx['path'])
            try:
                assert ledger.state()['positions'][0]['quantity'] == '10'
                assert ledger.state()['lots'][0]['remaining_quantity'] == '10'
            finally:
                ledger.connection.close()
    elif workflow == 'performance':
        if mode == 'blocked':
            assert result['twr']['return'] is None and result['xirr']['annualized_return'] is None
        else:
            assert result['twr']['return'] == '0.1'
            assert result['mode'] == 'ACTUAL'
    elif workflow == 'monthly':
        assert result['executed'] is False
        assert all(action['type'] == 'BUY' for action in result['proposed_actions'])
        if mode == 'success':
            assert result['estimated_tax_budget_consumption'] == '0'
            assert ctx['report_path'].is_file()
            assert result['id'] in ctx['report_path'].read_text()
    elif workflow == 'harvest':
        assert result['wash_sale_certified'] is False
        assert any(issue['code'] in {'HOUSEHOLD_PURCHASE_CONFLICT', 'HOUSEHOLD_HISTORY_INCOMPLETE'}
                   for issue in result['issues'])
    elif workflow == 'screening':
        assert 'score' not in json.dumps(result)
        if mode == 'success':
            assert result['criteria']['expense_ratio_max'] == '0.002'
            assert result['candidates'][0]['source_ids']
        else:
            assert result['coverage']['missing_characteristics']
    elif workflow == 'research':
        assert result['coverage']['requested_issuers'] == 1
        if mode == 'success':
            assert result['coverage']['researched_issuers'] == 1
            assert result['companies'][0]['run_hashes']
            assert result['companies'][0]['events'][0]['source_ids'] == ['fictional-release']
        else:
            assert result['coverage']['researched_issuers'] == 0
            assert result['companies'][0]['status'] == 'NOT_RESEARCHED'
    else:
        assert result['classification'] == 'HYPOTHETICAL'
        assert result['comparable'] is (mode == 'success')
        if mode == 'success':
            assert [row['total_return'] for row in result['candidates']] == ['0.1', '0.05']


def fictional_news_package():
    """Valid existing specialist schema; the common envelope never replaces it."""
    return {
        'schema_version': '1.0', 'research_type': 'NEWS_CATALYSTS_THESIS_CHANGES',
        'company': {'name': 'Fictional Operating Company', 'ticker': 'FICT-A', 'cik': None,
                    'security_id': None},
        'scope': {'window_start': '2026-10-01', 'window_end': '2026-10-10',
                  'researched_as_of': '2026-10-10', 'coverage_status': 'PARTIAL',
                  'searched_source_types': ['ISSUER_RELEASE'],
                  'coverage_notes': 'Fictional offline source only.'},
        'sources': [{'id': 'fictional-release', 'source_type': 'ISSUER_RELEASE',
                     'publisher': 'Fictional Operating Company',
                     'url': 'https://example.invalid/release', 'published_at': '2026-10-06',
                     'accessed_at': '2026-10-10', 'source_locator': 'Opening paragraph'}],
        'events': [{'event_key': 'factory-opened', 'title': 'Fictional factory',
                    'category': 'OPERATIONS', 'event_date': '2026-10-06',
                    'date_status': 'CONFIRMED', 'event_status': 'ANNOUNCED',
                    'affected_segments': [], 'primary_source_id': 'fictional-release',
                    'source_ids': ['fictional-release'],
                    'facts': [{'fact_key': 'opened', 'statement': 'Fictional factory opened.',
                               'source_id': 'fictional-release', 'source_locator': 'Opening paragraph',
                               'verification_status': 'VERIFIED'}],
                    'implications': [], 'follow_up_questions': []}],
        'catalysts': [], 'theses': [], 'limitations': ['Entirely fictional test evidence.']}


def approve_policy(ctx):
    """Explicit immutable policy approval precedes every hypothetical calculation."""
    planning = required_module('invest.planning')
    ledger = Ledger(ctx['path'])
    try:
        saved = planning.save_policy(ledger, ctx['policy'], confirm=True)
        assert saved['id'] == 'approved-synthetic'
        ctx['financial_before'] = copy.deepcopy(ledger.planning_state())
    finally:
        ledger.connection.close()


@given('a sourced single currency lookthrough universe with unresolved exposure')
def sourced_universe(research_ctx):
    research_ctx['universe'] = {
        'as_of': '2026-10-10', 'data_environment': 'SYNTHETIC', 'currency': 'USD',
        'manifest_id': 'fictional-lookthrough-manifest', 'household_total_value': '4000',
        'unknown_exposure_value': '500', 'filtered_exposure_value': '500',
        'companies': [
            {'issuer_id': 'CIK:0000123456', 'total_value': '1000',
             'identity': {'cik': '0000123456', 'name': 'Fictional First Company'},
             'contributions': [{'security_id': 'fictional-fund', 'value': '1000',
                                'source_id': 'fictional-fund-holdings', 'as_of': '2026-10-01'}]},
            {'issuer_id': 'CIK:0000123457', 'total_value': '500',
             'identity': {'cik': '0000123457', 'name': 'Fictional Second Company'},
             'contributions': [{'security_id': 'fictional-fund', 'value': '500',
                                'source_id': 'fictional-fund-holdings', 'as_of': '2026-10-01'}]}],
        'issues': [{'code': 'UNRESOLVED_ISSUER_MAPPING', 'severity': 'WARNING',
                    'affected_ids': ['fictional-unresolved'], 'blocks_calculation': False,
                    'blocks_proposal': True, 'blocks_execution_review': True,
                    'message': 'Fictional incomplete underlying issuer coverage.'}],
    }


@when('the company universe is frozen into an issuer research manifest')
def freeze_issuer_manifest(research_ctx):
    module = required_module('invest.research_portfolio')
    research_ctx['universe_before'] = copy.deepcopy(research_ctx['universe'])
    research_ctx['result'] = module.freeze_universe(research_ctx['universe'], requested_top=20,
                                                  as_of='2026-10-10')


@then('issuer weights use whole household value and keep identity source and missing coverage')
def universe_provenance(research_ctx):
    result = research_ctx['result']
    assert research_ctx['universe'] == research_ctx['universe_before']
    assert result['requested_top'] == 20
    assert result['data_environment'] == 'SYNTHETIC'
    assert result['as_of'] == '2026-10-10'
    assert result['source_manifest_ids'] == ['fictional-lookthrough-manifest']
    assert [row['exposure_weight'] for row in result['issuers']] == ['0.25', '0.125']
    assert result['coverage']['unknown_exposure_value'] == '500'
    assert result['coverage']['filtered_exposure_value'] == '500'
    for issuer, company in zip(result['issuers'], research_ctx['universe']['companies'], strict=True):
        assert issuer['issuer_id'] == company['issuer_id']
        assert issuer['identity'] == company['identity']
        assert issuer['contributions'] == company['contributions']
    assert result['issues'] == research_ctx['universe']['issues']
