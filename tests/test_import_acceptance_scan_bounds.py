"""Complete and partial imports preserve exact financial inventory."""

import copy
import json
from decimal import Decimal
from pathlib import Path

import pytest

from benchmarks.financial_fixtures import build

ROOT = Path(__file__).resolve().parents[1]
DIMENSIONS = json.loads((ROOT / 'benchmarks/cases.json').read_text())['profiles']['test']


@pytest.mark.parametrize('positions', [4, 16])
@pytest.mark.parametrize('complete', [True, False], ids=['full', 'partial'])
def test_complete_and_partial_imports_preserve_exact_inventory(
        tmp_path, positions, complete):
    fixture = build(tmp_path, dict(DIMENSIONS, accounts=1, positions=positions,
                                  lots=positions*2, accepted_snapshots=1))
    ledger = fixture.ledger
    try:
        before = ledger.planning_state()
        candidate = copy.deepcopy(fixture.snapshots[0])
        candidate.update(source_hash=f'fictional-new-source-{positions}-{complete}',
                         source_timestamp='2026-10-10', positions_complete=complete,
                         lots_complete=complete)
        for position in candidate['positions']:
            position['as_of'] = '2026-10-10'
        if not complete:
            candidate['positions'] = candidate['positions'][:1]
            candidate['positions'][0]['cost_basis'] = None
            candidate['lots'] = []
        result = ledger.apply(candidate)
        assert result['status'] == 'APPLIED'
        after = ledger.planning_state()
        assert len(after['positions']) == positions
        assert len(after['lots']) == positions * 2
        before_lots = {lot['id']: lot for lot in before['lots']}
        for lot in after['lots']:
            previous = before_lots[lot['id']]
            for field in ('security_id', 'account_id', 'source_lot_id', 'quantity',
                          'remaining_quantity', 'cost_basis', 'remaining_adjusted_basis',
                          'identity_status', 'identity_source', 'saleable', 'acquisition_date'):
                assert lot[field] == previous[field]
        assert sum(Decimal(lot['remaining_adjusted_basis']) for lot in after['lots']) == positions * 1200
        assert all(Decimal(position['quantity']) == 10 and
                   Decimal(position['cost_basis']) == 1200 and
                   position['lot_state'] == 'RESOLVED' for position in after['positions'])
        assert after['cash_balances'][0]['amount'] == '10000'
        assert after['activities'] == before['activities'] == []
    finally:
        fixture.close()
