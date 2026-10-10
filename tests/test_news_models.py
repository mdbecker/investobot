"""Fictional source-backed news contract scenarios."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from invest.news_models import NewsResearchInput


def news_package():
    return {
        'schema_version': '1.0', 'research_type': 'NEWS_CATALYSTS_THESIS_CHANGES',
        'company': {'name': 'Fictional Technology Corporation', 'ticker': 'FAKE', 'cik': None, 'security_id': None},
        'scope': {'window_start': '2026-10-01', 'window_end': '2026-10-10', 'researched_as_of': '2026-10-10',
                  'coverage_status': 'PARTIAL', 'searched_source_types': ['ISSUER_RELEASE'],
                  'coverage_notes': 'Selected fictional disclosures only.'},
        'sources': [{'id': 'release', 'source_type': 'ISSUER_RELEASE', 'publisher': 'Fictional Corporation',
                     'url': 'https://example.invalid/release', 'published_at': '2026-10-06',
                     'accessed_at': '2026-10-10', 'source_locator': 'Opening paragraph'}],
        'theses': [{'thesis_id': 'demand', 'statement': 'Enterprise adoption supports growth.',
                    'assessment': 'INSUFFICIENT_EVIDENCE', 'rationale': 'Adoption remains unknown.',
                    'related_event_keys': ['launch'], 'uncertainty': 'No adoption figures.'}],
        'events': [{'event_key': 'launch', 'title': 'Fictional product announcement', 'category': 'PRODUCT',
                    'event_date': '2026-10-06', 'date_status': 'CONFIRMED', 'event_status': 'ANNOUNCED',
                    'affected_segments': ['Enterprise'], 'primary_source_id': 'release', 'source_ids': ['release'],
                    'facts': [{'fact_key': 'announced', 'statement': 'The company announced a product.',
                               'source_id': 'release', 'source_locator': 'Opening paragraph',
                               'verification_status': 'VERIFIED'}],
                    'implications': [{'id': 'possible-demand', 'area': 'DEMAND', 'statement': 'Demand could grow.',
                                      'assumptions': 'Customer uptake.', 'uncertainty': 'Uptake is unknown.'}],
                    'follow_up_questions': [{'id': 'uptake', 'question': 'Has uptake been disclosed?', 'status': 'OPEN'}]}],
        'catalysts': [{'catalyst_id': 'availability', 'title': 'Product availability', 'related_event_key': 'launch',
                       'scheduled_date': None, 'date_status': 'UNKNOWN', 'status': 'EXPECTED',
                       'source_id': 'release', 'source_locator': 'Availability section', 'qualifiers': 'No firm date.'}],
        'limitations': ['Entirely fictional evidence.'],
    }


def test_source_backed_fictional_package_and_future_catalyst():
    payload = news_package()
    payload['catalysts'][0].update(scheduled_date='2027-01-10', date_status='EXPECTED', status='SCHEDULED')
    model = NewsResearchInput.model_validate(payload)
    assert model.events[0].facts[0].verification_status == 'VERIFIED'
    assert model.model_dump(mode='json')['catalysts'][0]['scheduled_date'] == '2027-01-10'


@pytest.mark.parametrize('collection,key', [('sources', 'id'), ('events', 'event_key'),
                                            ('catalysts', 'catalyst_id'), ('theses', 'thesis_id')])
def test_duplicate_run_identifiers_rejected(collection, key):
    payload = news_package()
    payload[collection].append(deepcopy(payload[collection][0]))
    with pytest.raises(ValidationError, match='duplicate'):
        NewsResearchInput.model_validate(payload)


@pytest.mark.parametrize('field', ['facts', 'implications', 'follow_up_questions'])
def test_duplicate_event_record_identifiers_rejected(field):
    payload = news_package()
    payload['events'][0][field].append(deepcopy(payload['events'][0][field][0]))
    with pytest.raises(ValidationError, match='duplicate'):
        NewsResearchInput.model_validate(payload)


@pytest.mark.parametrize('change', [
    lambda p: p.update(untrusted_skill_version='9'),
    lambda p: p['scope'].update(window_start='2026-10-11'),
    lambda p: p['scope'].update(researched_as_of='2099-01-01'),
    lambda p: p['sources'][0].update(published_at='2026-10-11'),
    lambda p: p['sources'][0].update(accessed_at='2026-10-11'),
    lambda p: p['events'][0].update(event_date=None),
    lambda p: p['events'][0].update(event_date='2027-01-01'),
    lambda p: p['events'][0].update(primary_source_id='missing'),
    lambda p: p['events'][0].update(source_ids=['missing']),
    lambda p: p['events'][0]['facts'][0].update(source_id='missing'),
    lambda p: p['events'][0]['facts'][0].update(source_locator=''),
    lambda p: p['theses'][0].update(related_event_keys=['missing']),
    lambda p: p['catalysts'][0].update(related_event_key='missing'),
    lambda p: p['catalysts'][0].update(source_id='missing'),
    lambda p: p['catalysts'][0].update(date_status='CONFIRMED'),
    lambda p: p['events'][0].update(event_status='RESOLVED'),
    lambda p: p['events'][0]['follow_up_questions'][0].update(status='ANSWERED'),
])
def test_invalid_evidence_dates_links_and_extra_fields_rejected(change):
    payload = news_package()
    change(payload)
    with pytest.raises(ValidationError):
        NewsResearchInput.model_validate(payload)


def test_unknown_dates_disputed_claims_and_empty_partial_coverage_preserved():
    payload = news_package()
    payload['events'][0].update(event_date=None, date_status='UNKNOWN')
    payload['sources'][0]['published_at'] = None
    payload['events'][0]['facts'][0]['verification_status'] = 'DISPUTED'
    assert NewsResearchInput.model_validate(payload).events[0].event_date is None
    payload.update(events=[], catalysts=[], theses=[])
    assert NewsResearchInput.model_validate(payload).events == []


def test_answer_requires_verified_same_event_fact_or_explicit_limitation():
    payload = news_package()
    question = payload['events'][0]['follow_up_questions'][0]
    question.update(status='ANSWERED', answered_fact_key='announced')
    NewsResearchInput.model_validate(payload)
    payload['events'][0]['facts'][0]['verification_status'] = 'DISPUTED'
    with pytest.raises(ValidationError):
        NewsResearchInput.model_validate(payload)
    question.update(answered_fact_key=None, closure_limitation='No uptake data; closed as unanswerable.')
    NewsResearchInput.model_validate(payload)


def test_explicit_resolution_evidence_and_safe_public_locator():
    payload = news_package()
    payload['events'][0].update(event_status='RESOLVED', status_source_id='release', status_source_locator='Outcome')
    payload['sources'][0]['url'] = 'https://user:secret@example.invalid/release?token=private&record_id=public#secret'
    result = NewsResearchInput.model_validate(payload)
    assert result.sources[0].url == 'https://example.invalid/release?record_id=public'


def test_source_sec_identity_cannot_contradict_company():
    payload = news_package()
    payload['company']['cik'] = '123'
    payload['sources'][0]['url'] = 'https://www.sec.gov/Archives/edgar/data/456/document.htm'
    with pytest.raises(ValidationError, match='CIK'):
        NewsResearchInput.model_validate(payload)
