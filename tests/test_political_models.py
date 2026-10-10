import copy
import json

import pytest
from pytest_bdd import given, scenarios, then, when

from invest.political_models import PoliticalResearchInput, enforce_policy, load_research

scenarios('features/political_models.feature')


def package():
    source = {'id': 'role', 'url': 'https://company.example/leadership',
              'publisher': 'Fictional Corporation', 'source_type': 'EXECUTIVE_BIOGRAPHY',
              'published_at': None, 'accessed_at': '2026-10-09',
              'individual_contributor_data': False, 'rights_basis': 'Public biography'}
    disclosure = {**source, 'id': 'record', 'url': 'https://records.example/statement',
                  'source_type': 'INDEPENDENT_DISCLOSURE',
                  'individual_contributor_data': True, 'rights_basis': 'Agent says allowed'}
    return {'schema_version': '1.0', 'research_type': 'EXECUTIVE_POLITICAL_CONTRIBUTIONS',
            'company': {'name': 'Fictional Corporation', 'ticker': 'FAKE', 'security_id': None},
            'scope': {'jurisdiction': 'US_FEDERAL', 'period_start': '2024-01-01',
                      'period_end': '2026-10-09', 'researched_as_of': '2026-10-09',
                      'coverage_status': 'PARTIAL', 'rights_status': 'APPROVED'},
            'sources': [source, disclosure],
            'executives': [{'id': 'exec', 'full_name': 'Fictional Officer', 'role': 'CEO',
                            'role_start': None, 'role_end': None, 'role_source_id': 'role',
                            'identity_status': 'VERIFIED'}],
            'recipients': [{'id': 'pac', 'name': 'Fictional Committee', 'recipient_type': 'PAC',
                            'committee_id': None, 'candidate_id': None, 'candidate_name': None,
                            'recipient_party': 'UNKNOWN', 'party_basis': 'UNKNOWN',
                            'election_cycle': 2026, 'party_source_id': 'record'}],
            'contributions': [{'id': 'gift', 'executive_id': 'exec', 'recipient_id': 'pac',
                               'date': '2026-01-15', 'amount_usd': '1000.00',
                               'transaction_kind': 'CONTRIBUTION', 'channel': 'DIRECT',
                               'source_system': 'SYNTHETIC', 'source_record_id': 'r1',
                               'underlying_transaction_key': 'underlying-1',
                               'identity_status': 'VERIFIED', 'countable': True,
                               'source_ids': ['role', 'record'], 'notes': 'Synthetic evidence'}],
            'unresolved_matches': [], 'limitations': ['Synthetic partial research']}


def reviewed_policy():
    return {'intended_use': 'INVESTMENT_RESEARCH', 'review_reference': 'Synthetic review',
            'sources': [{'origin': 'https://records.example',
                         'allow_individual_contributor_data': True,
                         'fec_derived': False, 'allow_fec_derived': False}]}


@pytest.fixture
def ctx():
    return {}


@given('a fictional political research package')
def fictional(ctx):
    ctx['package'] = package()


@when('only the public role biography supports its contribution')
def name_only(ctx):
    ctx['package']['contributions'][0]['source_ids'] = ['role']
    try:
        PoliticalResearchInput.model_validate(ctx['package'])
    except ValueError as error:
        ctx['error'] = error


@when('contribution permission is checked without a reviewed policy')
def permission(ctx, monkeypatch):
    monkeypatch.delenv('INVEST_RESEARCH_POLICY', raising=False)
    try:
        enforce_policy(PoliticalResearchInput.model_validate(ctx['package']))
    except ValueError as error:
        ctx['error'] = error


@then('political validation rejects the package')
def rejected(ctx):
    assert isinstance(ctx.get('error'), ValueError)


@pytest.mark.parametrize('mutation', [
    lambda p: p['company'].update(address='private address'),
    lambda p: p['scope'].update(period_end='2023-01-01'),
    lambda p: p['sources'].append(copy.deepcopy(p['sources'][0])),
    lambda p: p['executives'][0].update(role_source_id='missing'),
    lambda p: p['executives'].append({**p['executives'][0], 'id': 'another'}),
    lambda p: p['contributions'][0].update(amount_usd=1000),
    lambda p: p['contributions'][0].update(amount_usd='NaN'),
    lambda p: p['contributions'][0].update(amount_usd='1e3'),
    lambda p: p['contributions'][0].update(date='2023-01-01'),
    lambda p: p['contributions'][0].update(identity_status='POSSIBLE_MATCH'),
    lambda p: p['contributions'][0].update(countable='true'),
    lambda p: p['contributions'][0].update(underlying_transaction_key=None),
    lambda p: p['contributions'][0].update(transaction_kind='MEMO'),
    lambda p: p['contributions'][0].update(transaction_kind='REFUND', amount_usd='-1.00'),
    lambda p: p['recipients'][0].update(recipient_party='DEMOCRATIC', party_basis='UNKNOWN'),
    lambda p: p['recipients'][0].update(candidate_id='candidate', candidate_name='Candidate'),
    lambda p: p['contributions'].append({**p['contributions'][0], 'id': 'duplicate'}),
    lambda p: p['contributions'].append({**p['contributions'][0], 'id': 'duplicate',
                                         'source_record_id': 'r2'}),
])
def test_reject_inconsistent_or_private_inputs(mutation):
    incoming = package()
    mutation(incoming)
    with pytest.raises(ValueError):
        PoliticalResearchInput.model_validate(incoming)


def test_permitted_input_sanitizes_urls_and_preserves_exact_decimal(tmp_path):
    incoming = package()
    incoming['sources'][1]['url'] = 'https://user:secret@records.example/statement?api_key=SECRET#token'
    incoming['contributions'][0]['amount_usd'] = '1000.000000000000000000000000001'
    data = tmp_path / 'research.json'
    policy = tmp_path / 'policy.json'
    data.write_text(json.dumps(incoming))
    policy.write_text(json.dumps(reviewed_policy()))
    model = load_research(data, policy_path=policy)
    exported = model.model_dump(mode='json')
    assert exported['sources'][1]['url'] == 'https://records.example/statement'
    assert exported['contributions'][0]['amount_usd'] == '1000.000000000000000000000000001'


def test_metadata_only_research_needs_no_personal_policy(monkeypatch):
    monkeypatch.delenv('INVEST_RESEARCH_POLICY', raising=False)
    incoming = package()
    incoming['contributions'] = []
    incoming['sources'] = incoming['sources'][:1]
    incoming['recipients'] = []
    incoming['scope']['rights_status'] = 'PENDING_REVIEW'
    enforce_policy(PoliticalResearchInput.model_validate(incoming))


def test_fec_mirror_requires_separate_review(tmp_path):
    policy = reviewed_policy()
    policy['sources'][0]['fec_derived'] = True
    path = tmp_path / 'policy.json'
    path.write_text(json.dumps(policy))
    with pytest.raises(ValueError):
        enforce_policy(PoliticalResearchInput.model_validate(package()), policy_path=path)


def test_invalid_json(tmp_path):
    path = tmp_path / 'invalid.json'
    path.write_text('{')
    with pytest.raises(ValueError):
        load_research(path)
