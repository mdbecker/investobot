"""Public acceptance for remaining research identity, provenance and permission gates."""

import copy
import hashlib
import json
from pathlib import Path

import pytest
from test_earnings_models import package as earnings_package
from test_mvp_research_completeness_bdd import news_package
from test_political_models import package as political_package
from test_political_models import reviewed_policy
from typer.testing import CliRunner

from invest.cli import app
from invest.ledger import Ledger
from invest.models import DomainError
from invest.research_storage import SPECIALTIES, import_batch, show
from invest.search import store_chunks


def envelope(kind, package, issuer='0000000001'):
    as_of = package.get('researched_as_of') or package['scope']['researched_as_of']
    return {'kind': kind, 'issuer_id': issuer, 'as_of': as_of,
            'data_environment': 'SYNTHETIC', 'skill_name': SPECIALTIES[kind][1],
            'package': package}


def register(ledger, cik, ticker):
    return ledger.register_security({'ticker': ticker, 'name': 'Fictional ' + ticker,
        'asset_type': 'STOCK', 'currency': 'USD', 'cik': cik, 'issuer_id': cik,
        'data_environment': 'SYNTHETIC', 'source': 'Reviewed fictional original issuer registry',
        'issuer_identity_evidence': {'source_locator': 'https://example.invalid/issuer/' + cik,
            'source': 'Reviewed fictional original issuer registry', 'reviewed': True, 'cik': cik}})


def test_envelope_cannot_redirect_sourced_registered_issuer_atomic_batch(tmp_path):
    ledger = Ledger(tmp_path / 'ledger.db')
    try:
        first = register(ledger, '0000000001', 'FAKE')
        register(ledger, '0000000002', 'OTHER')
        package = earnings_package()
        package['company']['security_id'] = first['id']
        before = ledger.planning_state()
        redirected = copy.deepcopy(package)
        redirected['metrics'][0]['value'] = '1250000001.00'
        redirected['limitations'].append('Separate fictional revised disclosure; original issuer unchanged.')
        with pytest.raises((DomainError, ValueError), match='(?i)issuer|identity|CIK'):
            import_batch(ledger, [envelope('EARNINGS', package),
                envelope('EARNINGS', redirected, '0000000002')], confirmed=True)
        assert ledger.connection.execute('SELECT count(*) FROM research_runs').fetchone()[0] == 0
        assert ledger.connection.execute('SELECT count(*) FROM research_artifacts').fetchone()[0] == 0
        assert ledger.planning_state() == before
    finally:
        ledger.connection.close()


@pytest.mark.parametrize('source_kind', ['BROKERAGE', 'PERSONAL_CONTRIBUTION'])
def test_source_kind_cannot_bypass_private_corpus_exclusion(tmp_path, source_kind):
    path = tmp_path / 'ledger.db'
    ledger = Ledger(path)
    before = ledger.planning_state()
    ledger.connection.close()
    text = 'Entirely fictional private account or named contribution evidence.'
    chunk = {'chunk_id': 'private', 'document_id': 'private-document', 'text': text,
        'source_kind': source_kind, 'source_url': 'https://example.invalid/private',
        'source_date': '2026-10-10', 'permission': 'PERMITTED',
        'content_hash': hashlib.sha256(text.encode()).hexdigest(),
        'offset_start': 0, 'offset_end': len(text), 'license': 'Fictional owner permission',
        'data_environment': 'SYNTHETIC'}
    with pytest.raises(DomainError, match='(?i)private|broker|personal|source.kind'):
        store_chunks(path, [chunk], confirmed=True)
    ledger = Ledger(path)
    try:
        assert ledger.connection.execute('SELECT count(*) FROM document_chunks').fetchone()[0] == 0
        assert ledger.planning_state() == before
    finally:
        ledger.connection.close()


def specialty_package(kind):
    if kind == 'EARNINGS':
        return earnings_package()
    if kind == 'POLITICAL':
        return political_package()
    if kind == 'NEWS':
        return news_package(cik='0000000001', name='Fictional Corporation',
            researched_as_of='2026-10-10', window_start='2026-10-01', event_date='2026-10-06')
    fixture = 'insiders' if kind == 'INSIDERS' else 'competitive'
    return json.loads((Path(__file__).parent / 'fixtures' / (fixture + '.json')).read_text())


@pytest.mark.parametrize('kind', ['NEWS', 'EARNINGS', 'COMPETITIVE', 'INSIDERS', 'POLITICAL'])
def test_native_specialty_cli_accepts_strict_envelope_preserving_provenance(tmp_path, monkeypatch, kind):
    path = tmp_path / 'ledger.db'
    monkeypatch.setenv('INVEST_DB', str(path))
    policy = tmp_path / 'rights.json'
    policy.write_text(json.dumps(reviewed_policy()))
    monkeypatch.setenv('INVEST_RESEARCH_POLICY', str(policy))
    payload = envelope(kind, specialty_package(kind))
    incoming = tmp_path / 'original-reviewed-fictional.json'
    incoming.write_text(json.dumps(payload))
    family = SPECIALTIES[kind][0].replace('_', '-')
    result = CliRunner().invoke(app, ['research', family, 'import', str(incoming), '--yes'])
    assert result.exit_code == 0, result.output
    accepted = json.loads(result.stdout)
    run_id = accepted.get('run_id') or accepted.get('research_run_id')
    assert run_id, accepted
    ledger = Ledger(path)
    try:
        stored = show(ledger, run_id)
        assert stored['envelope']['issuer_id'] == payload['issuer_id']
        assert stored['envelope']['data_environment'] == 'SYNTHETIC'
        assert stored['envelope']['skill_name'] == SPECIALTIES[kind][1]
        assert stored['envelope']['package']['research_type'] == payload['package']['research_type']
        if kind == 'POLITICAL':
            assert stored['envelope']['package']['contributions'][0]['amount_usd'] == '1000'
    finally:
        ledger.connection.close()


@pytest.mark.parametrize('category,research_type', [
    ('EMPLOYEE_PERSONAL', 'EMPLOYEE_POLITICAL_CONTRIBUTIONS'),
    ('CORPORATE_PAC', 'CORPORATE_PAC_POLITICAL_CONTRIBUTIONS'),
])
def test_reviewed_political_categories_are_accepted_without_executive_relabeling(
        tmp_path, category, research_type):
    """Original fictional linkage and local rights approval accompany each category."""
    ledger = Ledger(tmp_path / 'ledger.db')
    policy = tmp_path / 'reviewed-rights.json'
    policy.write_text(json.dumps(reviewed_policy()))
    package = political_package()
    package['research_type'] = research_type
    package['contributions'][0]['contributor_category'] = category
    if category == 'EMPLOYEE_PERSONAL':
        package['executives'][0].update(role='Employee', full_name='Fictional Employee')
    else:
        package['executives'][0].update(role='Corporate PAC', full_name='Fictional Corporate PAC')
        package['sources'][0]['source_type'] = 'CORPORATE_PAC_REGISTRATION'
        package['sources'][0]['url'] = 'https://company.example/pac-registration'
        package['contributions'][0]['corporate_pac_identity_evidence'] = {
            'committee_id': 'C00999999', 'company_source_id': 'role',
            'registration_source_id': 'record', 'source_locator': 'Fictional PAC sponsor registration',
            'reviewed': True}
        package['sources'][1]['individual_contributor_data'] = False
    before = ledger.planning_state()
    try:
        accepted = import_batch(ledger, [envelope('POLITICAL', package)],
                                confirmed=True, policy_path=policy)
        assert accepted['committed'] is True
        stored = show(ledger, accepted['runs'][0]['run_id'])['package']
        assert stored['research_type'] == research_type
        assert stored['contributions'][0]['contributor_category'] == category
        assert ledger.planning_state() == before
    finally:
        ledger.connection.close()


@pytest.mark.parametrize('kind', ['NEWS', 'EARNINGS', 'COMPETITIVE', 'INSIDERS', 'POLITICAL'])
def test_native_envelope_original_specialty_evidence_is_valid(tmp_path, kind):
    """Precondition: failures cannot be attributed to malformed original specialty facts."""
    ledger = Ledger(tmp_path / 'ledger.db')
    policy = tmp_path / 'rights.json'
    policy.write_text(json.dumps(reviewed_policy()))
    try:
        preview = import_batch(ledger, [envelope(kind, specialty_package(kind))],
                               policy_path=policy)
        assert preview['committed'] is False
        assert len(preview['runs']) == 1
        assert ledger.connection.execute('SELECT count(*) FROM research_runs').fetchone()[0] == 0
    finally:
        ledger.connection.close()
