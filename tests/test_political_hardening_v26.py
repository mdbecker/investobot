import json

import pytest
from pytest_bdd import given, scenarios, then, when
from test_political_models import package, reviewed_policy

from invest.ledger import Ledger
from invest.models import DomainError
from invest.political import import_research
from invest.political_models import safe_url
from invest.political_queries import summary

scenarios('features/political_hardening_v26.feature')


@pytest.fixture
def ctx(tmp_path):
    db = Ledger(tmp_path / 'research.db')
    policy = tmp_path / 'policy.json'
    policy.write_text(json.dumps(reviewed_policy()))
    yield {'db': db, 'policy': policy}
    db.connection.close()


@given('a public disclosure URL with a record locator and credential')
def url(ctx):
    ctx['url'] = 'https://user:password@records.example/filing?record_id=PUBLIC-123&api_key=SECRET#token'


@when('the source URL is normalized')
def normalize(ctx):
    ctx['normalized'] = safe_url(ctx['url'])


@then('its record locator is retained and credentials are absent')
def retained(ctx):
    assert ctx['normalized'] == 'https://records.example/filing?record_id=PUBLIC-123'


@given('a registered fictional security')
def security(ctx):
    ctx['security'] = ctx['db'].register_security({'ticker': 'RIGHT', 'name': 'Fictional issuer',
        'asset_type': 'STOCK', 'currency': 'USD', 'source': 'Synthetic public listing'})


@when('research supplies its ID with a contradictory ticker')
def wrong(ctx):
    data = package()
    data['company'].update(security_id=ctx['security']['id'], ticker='WRONG')
    try:
        import_research(ctx['db'], data, yes=True, policy_path=ctx['policy'])
    except DomainError as exc:
        ctx['error'] = exc


@then('import fails without persisting research')
def denied(ctx):
    assert ctx['error'].code == 3
    assert ctx['db'].connection.execute('SELECT COUNT(*) FROM research_political_runs').fetchone()[0] == 0


@given('a fictional contribution to a verified candidate committee')
def candidate(ctx):
    data = package()
    data['recipients'][0].update(recipient_type='CANDIDATE_COMMITTEE', committee_id='COMMITTEE-1',
        candidate_id='CANDIDATE-1', candidate_name='Fictional Candidate',
        recipient_party='DEMOCRATIC', party_basis='Synthetic verified committee relationship')
    ctx['run'] = import_research(ctx['db'], data, yes=True, policy_path=ctx['policy'])


@when('the recipient summary is requested')
def summarize(ctx):
    ctx['summary'] = summary(ctx['db'], ctx['run']['research_run_id'])


@then('candidate and committee identities remain visible without donor affiliation')
def identities(ctx):
    recipient = ctx['summary']['contributions_by_recipient'][0]
    assert recipient['committee_id'] == 'COMMITTEE-1'
    assert recipient['candidate_id'] == 'CANDIDATE-1'
    assert recipient['candidate_name'] == 'Fictional Candidate'
    assert recipient['recipient_name'] == 'Fictional Committee'
    assert 'recipient_party' not in ctx['summary']['contributions_by_executive'][0]


@pytest.mark.parametrize('url', ['https://records.example/?record_id=a&record_id=b',
                                  'https://records.example/?record_id=bad%2Fsecret'])
def test_ambiguous_public_locator_rejected(url):
    with pytest.raises(ValueError):
        safe_url(url)


def test_explicit_sourced_ticker_alias_is_accepted(ctx):
    registered = ctx['db'].register_security({'ticker': 'RIGHT', 'name': 'Fictional issuer',
        'asset_type': 'STOCK', 'currency': 'USD', 'source': 'Synthetic public listing',
        'ticker_aliases': [{'ticker': 'OLD', 'source': 'Synthetic documented ticker rename'}]})
    data = package()
    data['company'].update(security_id=registered['id'], ticker='OLD')
    assert import_research(ctx['db'], data, yes=True, policy_path=ctx['policy'])['committed']
