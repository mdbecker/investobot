"""Accepted observations must use reviewed aliases without merging strong conflicts."""

import copy

import pytest
from test_prd_confirmed_accounting_audit import observation

from invest.ledger import Ledger
from invest.models import DomainError


@pytest.fixture
def ledger(tmp_path):
    selected = Ledger(tmp_path / 'fictional-observation-alias.db')
    initial = observation()
    initial['positions'][0]['cusip'] = '111111111'
    selected.apply(initial)
    selected.register_security({
        'ticker': 'FICT', 'name': 'Fictional sourced security', 'asset_type': 'STOCK',
        'currency': 'USD', 'cusip': '111111111',
        'source': 'Human-reviewed fictional original issuer ticker notice',
        'ticker_aliases': [{'ticker': 'FORMER',
                            'source': 'Human-reviewed fictional historical ticker rename notice'}],
    })
    yield selected
    selected.connection.close()


def later_observation(*, complete, ticker='FORMER', cusip=None):
    candidate = observation(day='2026-03-03')
    candidate['positions_complete'] = complete
    candidate['lots_complete'] = complete
    candidate['positions'][0]['security'] = ticker
    candidate['lots'][0]['security'] = ticker
    candidate['source_hash'] = f'fictional-alias-observation:{complete}:{ticker}:{cusip}'
    if cusip is not None:
        candidate['positions'][0]['cusip'] = cusip
    return candidate


@pytest.mark.parametrize('complete', [True, False])
def test_reviewed_alias_observation_reuses_canonical_position_and_lot(ledger, complete):
    canonical = ledger.resolve('FICT')['id']
    assert ledger.resolve('FORMER')['id'] == canonical
    ledger.apply(later_observation(complete=complete))
    assert len(ledger.rows('securities')) == 1
    assert len(ledger.rows('positions')) == 1
    assert ledger.rows('positions')[0]['security_id'] == canonical
    assert ledger.rows('lots')[0]['security_id'] == canonical
    assert ledger.rows('lots')[0]['id'] == 'original-lot'
    assert ledger.rows('lots')[0]['remaining_adjusted_basis'] == '800'
    assert ledger.connection.execute('PRAGMA foreign_key_check').fetchall() == []


@pytest.mark.parametrize('complete', [True, False])
def test_current_ticker_observation_control_preserves_identity(ledger, complete):
    canonical = ledger.resolve('FICT')['id']
    ledger.apply(later_observation(complete=complete, ticker='FICT'))
    assert len(ledger.rows('securities')) == 1
    assert ledger.rows('positions')[0]['security_id'] == canonical
    assert ledger.rows('lots')[0]['security_id'] == canonical


@pytest.mark.parametrize('complete', [True, False])
def test_alias_with_conflicting_sourced_cusip_requires_atomic_review(ledger, complete):
    before = copy.deepcopy(ledger.state())
    with pytest.raises(DomainError) as failure:
        ledger.apply(later_observation(complete=complete, cusip='999999999'))
    assert failure.value.code == 3
    assert getattr(failure.value, 'result', {}).get('issues'), 'Conflict must return typed review issues'
    assert ledger.state() == before
