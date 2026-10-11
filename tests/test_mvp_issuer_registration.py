"""Reviewed fictional operating-issuer links use the public registration boundary."""

import copy

import pytest
from pydantic import ValidationError

from invest.ledger import Ledger
from invest.models import DomainError


@pytest.fixture
def ledger(tmp_path):
    selected = Ledger(tmp_path / 'fictional-issuers.db')
    yield selected
    selected.connection.close()


def reviewed_issuer():
    return {
        'ticker': 'FICT', 'name': 'Fictional Operating Issuer', 'asset_type': 'STOCK',
        'currency': 'USD', 'source': 'Reviewed fictional original issuer identity record',
        'cik': '0000123456', 'lei': '00000000000000000001',
        'issuer_id': '0000123456', 'data_environment': 'SYNTHETIC',
        'issuer_identity_evidence': {
            'source_locator': 'https://fictional-issuer.example/identity',
            'source': 'Reviewed fictional original issuer identity record',
            'reviewed': True, 'cik': '0000123456', 'lei': '00000000000000000001',
        },
    }


def test_reviewed_strong_issuer_identifiers_persist_exactly(ledger):
    payload = reviewed_issuer()
    registered = ledger.register_security(payload)
    accepted = ledger.resolve(registered['id'])
    for field in ('cik', 'lei', 'issuer_id', 'issuer_identity_evidence', 'data_environment'):
        assert accepted[field] == payload[field]
    assert isinstance(accepted['cik'], str)
    assert isinstance(accepted['lei'], str)
    repeated = ledger.register_security(payload)
    assert repeated['id'] == registered['id']
    assert len(ledger.rows('securities')) == 1


@pytest.mark.parametrize('missing', ['cik', 'issuer_identity_evidence', 'data_environment'])
def test_incomplete_issuer_mapping_is_rejected_atomically(ledger, missing):
    payload = reviewed_issuer()
    payload.pop(missing)
    before = copy.deepcopy(ledger.state())
    with pytest.raises((DomainError, ValidationError)):
        ledger.register_security(payload)
    assert ledger.state() == before


@pytest.mark.parametrize('change', ['unreviewed', 'credentialed', 'conflicting_cik',
                                   'unknown_environment', 'opaque_issuer'])
def test_unverified_or_conflicting_link_cannot_mutate_existing_identity(ledger, change):
    accepted = ledger.register_security(reviewed_issuer())
    before = copy.deepcopy(ledger.state())
    payload = reviewed_issuer()
    if change == 'unreviewed':
        payload['issuer_identity_evidence']['reviewed'] = False
    elif change == 'credentialed':
        payload['issuer_identity_evidence']['source_locator'] = (
            'https://user:secret@fictional-issuer.example/identity')
    elif change == 'conflicting_cik':
        payload['issuer_identity_evidence']['cik'] = '0000999999'
    elif change == 'unknown_environment':
        payload['data_environment'] = None
    else:
        payload['issuer_id'] = 'unreviewed-opaque-link'
    with pytest.raises((DomainError, ValidationError)):
        ledger.register_security(payload)
    assert ledger.state() == before
    assert ledger.resolve(accepted['id'])['cik'] == '0000123456'


def test_registration_of_issuer_mapping_cannot_reclassify_existing_other(ledger):
    base = reviewed_issuer()
    base['asset_type'] = 'OTHER'
    ledger.register_security(base)
    before = copy.deepcopy(ledger.state())
    with pytest.raises(DomainError, match='classification'):
        ledger.register_security(reviewed_issuer())
    assert ledger.state() == before
