"""Portfolio reports preserve original political category and native provenance."""

import copy
import json

import pytest
from test_political_models import package, reviewed_policy

from invest.analytics_store import snapshot
from invest.ledger import Ledger
from invest.political import import_research
from invest.research_portfolio import plan, report
from invest.research_storage import import_run, show


@pytest.fixture
def research(tmp_path):
    ledger = Ledger(tmp_path / 'fictional-reporting.db')
    rights = tmp_path / 'reviewed-fictional-rights.json'
    rights.write_text(json.dumps(reviewed_policy()))
    universe = {'manifest_id': 'fictional-political-universe', 'as_of': '2026-10-10',
                'data_environment': 'SYNTHETIC', 'requested_top': 1,
                'issuers': [{'issuer_id': 'fictional-corporation', 'exposure_weight': '1',
                            'identity': {'ticker': 'FAKE', 'name': 'Fictional Corporation'}}],
                'coverage': {'household_total_value': '1000', 'unknown_exposure_value': '0',
                             'filtered_exposure_value': '0', 'unresolved_issuer_value': '0'}}
    accepted = snapshot(ledger, {'id': universe['manifest_id'], 'purpose': 'RESEARCH_UNIVERSE',
                                'data_environment': 'SYNTHETIC', 'artifacts': [],
                                'metadata': {'universe': universe}}, confirm=True)
    assert accepted['committed'] is True
    frozen = plan(ledger, universe['manifest_id'], window_start='2026-01-01', window_end='2026-10-10')
    yield {'ledger': ledger, 'rights': rights, 'plan': frozen['id']}
    ledger.connection.close()


def political(category):
    value = package()
    value['research_type'] = {'EMPLOYEE_PERSONAL': 'EMPLOYEE_POLITICAL_CONTRIBUTIONS',
                              'CORPORATE_PAC': 'CORPORATE_PAC_POLITICAL_CONTRIBUTIONS',
                              'EXECUTIVE_PERSONAL': 'EXECUTIVE_POLITICAL_CONTRIBUTIONS'}[category]
    value['contributions'][0]['contributor_category'] = category
    if category == 'EMPLOYEE_PERSONAL':
        value['executives'][0].update(role='Employee', full_name='Fictional Employee')
    elif category == 'CORPORATE_PAC':
        value['executives'][0].update(role='Corporate PAC', full_name='Fictional Corporate PAC')
        value['sources'][0].update(source_type='CORPORATE_PAC_REGISTRATION',
                                   url='https://company.example/pac-registration')
        value['sources'][1]['individual_contributor_data'] = False
        value['contributions'][0]['corporate_pac_identity_evidence'] = {
            'committee_id': 'C00999999', 'company_source_id': 'role',
            'registration_source_id': 'record', 'source_locator': 'Fictional original PAC registration',
            'reviewed': True}
    return value


@pytest.mark.parametrize('category', ['EMPLOYEE_PERSONAL', 'CORPORATE_PAC'])
def test_portfolio_report_preserves_reviewed_political_category(research, category):
    ledger = research['ledger']
    source = political(category)
    accepted = import_run(ledger, {'kind': 'POLITICAL', 'issuer_id': 'fictional-corporation',
                                  'as_of': source['scope']['researched_as_of'],
                                  'data_environment': 'SYNTHETIC',
                                  'skill_name': 'investobot-political-contributions', 'package': source},
                          confirmed=True, policy_path=research['rights'])
    run_id = accepted['run_id']
    assert show(ledger, run_id)['package']['contributions'][0]['contributor_category'] == category
    before = copy.deepcopy(ledger.planning_state())
    result = report(ledger, research['plan'])
    assert ledger.planning_state() == before
    company = result['companies'][0]
    assert run_id in company['run_ids']
    assert company['political_totals'] == {category: '1000'}
    assert 'EXECUTIVE_PERSONAL' not in company['political_totals']


def test_original_native_political_run_remains_visible_with_reviewed_unknown_provenance(research):
    ledger = research['ledger']
    accepted = import_research(ledger, political('EXECUTIVE_PERSONAL'), yes=True,
                               policy_path=research['rights'])
    run_id = accepted['research_run_id']
    assert ledger.connection.execute('SELECT count(*) FROM research_runs WHERE id=?', (run_id,)).fetchone()[0] == 0
    original = show(ledger, run_id)
    before = copy.deepcopy(ledger.planning_state())
    result = report(ledger, research['plan'])
    assert ledger.planning_state() == before
    company = result['companies'][0]
    assert run_id in company['run_ids'], 'Native accepted evidence must remain available as historical review context'
    assert company['specialty_statuses']['investobot-political-contributions'] == 'REVIEW_REQUIRED'
    assert original['package']['sources']


def test_native_consolidated_retrieval_preserves_saved_trusted_skill_identity(research):
    ledger = research['ledger']
    accepted = import_research(ledger, political('EXECUTIVE_PERSONAL'), yes=True,
                               policy_path=research['rights'])
    result = show(ledger, accepted['research_run_id'])
    saved = json.loads(ledger.connection.execute('SELECT package_json FROM research_political_runs WHERE id=?',
                                               (accepted['research_run_id'],)).fetchone()[0])
    assert result['skill_name'] == saved['skill_name']
    assert result['skill_version'] == saved['skill_version']
    assert result['schema_version'] == saved['schema_version']
