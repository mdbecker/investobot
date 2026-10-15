"""Saved plan inspection retains compact summaries and full downloadable evidence."""

import json
from pathlib import Path

from planning_fixtures import saved_proposal

from invest import plans, targets
from invest.ledger import Ledger
from invest.market import MarketClient
from invest.web import _get_api


def test_saved_plan_gets_preserve_compact_summary_and_full_report(tmp_path):
    ledger = Ledger(tmp_path / 'ledger.db')
    try:
        ledger.apply({'data_environment': 'SYNTHETIC', 'account': {'id': 'ira', 'name': 'IRA',
            'tax_status': 'TAX_FREE'}, 'positions': [{'security': 'AAA', 'asset_type': 'STOCK',
            'quantity': '10', 'price': '100', 'market_value': '1000', 'as_of': '2026-10-08',
            'displayed_price_precision': 0, 'displayed_market_value_precision': 0}],
            'cash_known': True, 'cash': '0', 'source_timestamp': '2026-10-08', 'source_hash': 'compact-web'})
        sid = ledger.resolve('AAA')['id']
        target = targets.save(ledger, {'name': 'Hold shares', 'target_allocations': {sid: '1'},
            'planning_constraints': {'eligible_accounts': ['ira']}})
        saved = saved_proposal(ledger, MarketClient(ledger, fixture_path=Path(
            'tests/fixtures/fmp-synthetic.json')), target['id'], as_of='2026-10-08')
        before = list(ledger.connection.iterdump())
        summary = _get_api(ledger, '/api/plans', {})['plans'][0]
        assert summary == plans.plan_summary(saved)
        assert 'source_state' not in summary and 'proposed_actions' not in summary
        assert _get_api(ledger, '/api/plans/' + saved['id'], {}) == saved
        report, _, _ = _get_api(ledger, '/api/plans/' + saved['id'] + '/report',
                                {'format': ['json']})
        assert json.loads(report) == saved
        assert list(ledger.connection.iterdump()) == before
    finally:
        ledger.connection.close()
