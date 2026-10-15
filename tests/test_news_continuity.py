import json

import pytest
from pytest_bdd import given, scenarios, then, when
from test_news_queries import ledger as ledger
from test_news_queries import save

from invest import news_queries as queries
from invest.models import DomainError

scenarios('features/news_continuity.feature')


@pytest.fixture
def ctx(ledger):
    return {'ledger': ledger}


@given('an older fictional event and a later omitted observation')
def omitted(ctx):
    save(ctx['ledger'], 'A', '2026-10-01', status='DEVELOPING')
    save(ctx['ledger'], 'B', '2026-10-02', event=False)


@when('effective context is requested')
def context(ctx):
    ctx['context'] = queries.context(ctx['ledger'], 'FAKE')


@then('the event and unanswered question retain their older provenance')
def inherited(ctx):
    result = ctx['context']
    assert result['research_run_id'] == 'B'
    event = result['events'][0]
    assert event['event_status'] == 'DEVELOPING'
    assert event['last_observed_run_id'] == 'A'
    assert event['observation_status'] == 'NOT_REOBSERVED'
    assert event['last_observed_as_of'] == '2026-10-01'
    assert result['open_follow_up_questions'][0]['last_observed_run_id'] == 'A'
    assert result['catalysts'][0]['last_observed_run_id'] == 'A'
    assert result['theses'][0]['observation_status'] == 'NOT_REOBSERVED'
    assert result['theses'][0]['reassessment_status'] == 'NOT_REASSESSED'
    assert any('older' in warning.lower() for warning in result['warnings'])


@when('the event returns in a third run with new verified evidence')
def returns(ctx):
    save(ctx['ledger'], 'C', '2026-10-03', sources=('s2',),
         facts=[('announced', 'Launch announced.', 'VERIFIED'),
                ('available', 'Availability confirmed.', 'VERIFIED')])
    ctx['delta'] = queries.compare(ctx['ledger'], 'B', 'C')


@then('the delta shows reobservation with prior evidence and new facts')
def reobserved(ctx):
    delta = ctx['delta']
    assert delta['new_events'] == []
    row = delta['reobserved_events'][0]
    assert row['last_observed_run_id'] == 'A'
    assert row['to_run_id'] == 'C'
    assert 'FACT_ADDED' in row['change_types']
    assert row['before_sources'][0]['run_id'] == 'A'
    assert row['after_sources'][0]['run_id'] == 'C'
    assert delta['counts']['reobserved_events'] == 1
    assert queries.changes(ctx['ledger'], 'FAKE')['reobserved_events']


@given('a fictional event explicitly resolved before a later omitted run')
def resolved(ctx):
    save(ctx['ledger'], 'A', '2026-10-01')
    save(ctx['ledger'], 'B', '2026-10-02', status='RESOLVED', catalyst='OCCURRED',
         question='ANSWERED')
    ctx['ledger'].connection.execute(
        "UPDATE research_news_events SET status_source_id='s1',status_source_locator='Explicit outcome' WHERE run_id='B'")
    save(ctx['ledger'], 'C', '2026-10-03', event=False)


@then('the resolved event remains historical rather than active')
def terminal(ctx):
    assert ctx['context']['events'] == []
    assert ctx['context']['catalysts'] == []
    assert ctx['context']['open_follow_up_questions'] == []
    assert queries.summary(ctx['ledger'], 'B')['events'][0]['event_status'] == 'RESOLVED'


@given('two fictional runs with a newly disputed allegation')
def dispute(ctx):
    save(ctx['ledger'], 'A', '2026-10-01')
    save(ctx['ledger'], 'B', '2026-10-02', facts=[
        ('announced', 'Launch announced.', 'VERIFIED'),
        ('allegation', 'Third party alleges an issue; issuer disputes it.', 'DISPUTED')])


@given('two fictional runs withdrawing a fact verification')
def withdrawn(ctx):
    save(ctx['ledger'], 'A', '2026-10-01')
    save(ctx['ledger'], 'B', '2026-10-02', facts=[('announced', 'Launch announced.', 'DISPUTED')])


@when('the selected runs are compared')
def compare(ctx):
    ctx['delta'] = queries.compare(ctx['ledger'], 'A', 'B')


@then('the disputed addition has citations and no verified fact update')
def addition(ctx):
    assert ctx['delta']['updated_events'] == []
    row = ctx['delta']['disputed_claim_changes'][0]
    assert row['change_type'] == 'DISPUTED_ADDED'
    assert row['after']['source_locator'] == 'Paragraph one'
    assert row['sources'][0]['url'].startswith('https://example.invalid/')
    assert row['warning']


@then('the claim is explicitly disputed rather than disproven')
def verification_withdrawn(ctx):
    row = ctx['delta']['disputed_claim_changes'][0]
    assert row['change_type'] == 'VERIFIED_TO_DISPUTED'
    assert row['before']['verification_status'] == 'VERIFIED'
    assert row['after']['verification_status'] == 'DISPUTED'
    assert queries.summary(ctx['ledger'], 'B')['events'][0]['verified_facts'] == []
    assert 'not' in row['warning'].lower()


@pytest.mark.parametrize('before,after,kind', [
    ([('claim', 'Claim one.', 'DISPUTED')], [('claim', 'Claim two.', 'DISPUTED')], 'DISPUTED_REVISED'),
    ([('claim', 'Claim one.', 'DISPUTED')], [('claim', 'Claim one.', 'VERIFIED')], 'DISPUTED_TO_VERIFIED'),
    ([('claim', 'Claim one.', 'DISPUTED')], [('other', 'Another fact.', 'VERIFIED')], 'DISPUTED_NOT_REOBSERVED'),
])
def test_disputed_transition_matrix(ledger, before, after, kind):
    save(ledger, 'A', '2026-10-01', facts=before)
    save(ledger, 'B', '2026-10-02', facts=after, sources=('s2',))
    row = queries.compare(ledger, 'A', 'B')['disputed_claim_changes'][0]
    assert row['change_type'] == kind
    assert row['before_sources'][0]['run_id'] == 'A'
    if row['after']:
        assert row['after_sources'][0]['run_id'] == 'B'


def test_missing_entire_event_preserves_disputed_uncertainty(ledger):
    save(ledger, 'A', '2026-10-01', facts=[('claim', 'Contested claim.', 'DISPUTED')])
    save(ledger, 'B', '2026-10-02', event=False)
    assert queries.compare(ledger, 'A', 'B')['disputed_claim_changes'][0]['change_type'] == 'DISPUTED_NOT_REOBSERVED'


def test_future_history_never_leaks_into_explicit_comparison(ledger):
    save(ledger, 'future', '2026-10-09')
    save(ledger, 'old', '2026-10-01', event=False)
    save(ledger, 'selected', '2026-10-02')
    result = queries.compare(ledger, 'old', 'selected')
    assert result['new_events'] and result['reobserved_events'] == []


def test_context_recovers_questions_independently_and_is_readonly(ledger):
    save(ledger, 'A', '2026-10-01')
    save(ledger, 'B', '2026-10-02')
    ledger.connection.execute("UPDATE research_news_events SET follow_up_questions_json='[]',event_date=NULL WHERE run_id='B'")
    ledger.connection.commit()
    before = tuple(ledger.connection.iterdump())
    ledger.connection.execute('PRAGMA query_only=ON')
    result = queries.context(ledger, 'FAKE')
    assert result['events'][0]['event_date'] is None
    assert result['open_follow_up_questions'][0]['last_observed_run_id'] == 'A'
    question = result['open_follow_up_questions'][0]
    assert question['last_observed_as_of'] == '2026-10-01'
    assert question['sources'][0]['url'] == 'https://example.invalid/s1'
    assert 'verified_facts' not in result['events'][0]
    assert len(json.dumps(result).encode()) < 128 * 1024
    assert tuple(ledger.connection.iterdump()) == before


def test_context_preserves_ticker_changes_but_rejects_conflicting_entities(ledger):
    save(ledger, 'A', '2026-10-01', ticker='OLD')
    save(ledger, 'conflict', '2026-10-02', ticker='FAKE', cik='0000000002')
    save(ledger, 'B', '2026-10-03', event=False)
    result = queries.context(ledger, 'FAKE')
    assert result['events'][0]['last_observed_run_id'] == 'A'
    with pytest.raises(DomainError):
        queries.compare(ledger, 'conflict', 'B')


def test_missing_baseline_additive_arrays_and_counts(ledger):
    result = queries.changes(ledger, 'ABSENT')
    for key in ('reobserved_events', 'disputed_claim_changes'):
        assert result[key] == [] and result['counts'][key] == 0


def test_disputed_corroboration_and_cosmetics_are_not_new_claims(ledger):
    save(ledger, 'A', '2026-10-01', facts=[('claim', 'Contested claim.', 'DISPUTED')])
    save(ledger, 'B', '2026-10-02', sources=('s2',),
         facts=[('claim', '  Contested   claim. ', 'DISPUTED')], title='Renamed title')
    result = queries.compare(ledger, 'A', 'B')
    assert result['disputed_claim_changes'] == []
    assert result['new_evidence_only'] and result['updated_events'] == []


def test_relabeling_dispute_without_new_citation_is_not_fresh_confirmation(ledger):
    save(ledger, 'A', '2026-10-01', facts=[('claim', 'Contested claim.', 'DISPUTED')])
    save(ledger, 'B', '2026-10-02', sources=('renamed',),
         facts=[('claim', 'Contested claim.', 'VERIFIED')])
    ledger.connection.execute("UPDATE research_sources SET url='https://example.invalid/s1',published_at='2026-10-01' WHERE run_id='B'")
    result = queries.compare(ledger, 'A', 'B')
    assert result['updated_events'] == []
    row = result['disputed_claim_changes'][0]
    assert row['supporting_evidence_status'] == 'UNCHANGED_CITATION_REVIEW_REQUIRED'
    assert any('supporting evidence' in warning.lower() for warning in result['warnings'])


def test_latest_changes_recovers_same_issuer_prior_ticker(ledger):
    save(ledger, 'A', '2026-10-01', ticker='OLD')
    save(ledger, 'B', '2026-10-02', ticker='NEW')
    result = queries.changes(ledger, 'NEW')
    assert result['baseline_available'] and result['from_run_id'] == 'A'


def test_same_day_tie_cutoff_excludes_later_history(ledger):
    save(ledger, 'Z', '2026-10-01')
    save(ledger, 'A', '2026-10-01', event=False)
    save(ledger, 'C', '2026-10-02')
    result = queries.compare(ledger, 'A', 'C')
    assert result['new_events'] and not result['reobserved_events']
