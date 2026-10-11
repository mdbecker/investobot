"""Historical CLI reads must never fetch or mutate current public caches."""

import json

from typer.testing import CliRunner

from invest.cli import app
from invest.ledger import Ledger


def test_historical_exposure_does_not_fetch_current_holdings(tmp_path, monkeypatch):
    path = tmp_path / 'fictional.db'
    monkeypatch.setenv('INVEST_DB', str(path))
    fixture = tmp_path / 'market.json'
    fixture.write_text(json.dumps({'data_environment': 'SYNTHETIC',
                                  'holdings': {'FUND': []}}))
    monkeypatch.setenv('INVEST_FIXTURES', str(fixture))
    selected = Ledger(path)
    selected.apply({'account': {'id': 'fictional', 'name': 'Fictional IRA', 'tax_status': 'TAX_FREE'},
        'positions': [{'security': 'FUND', 'asset_type': 'ETF', 'quantity': '1',
                       'price': '100', 'market_value': '100',
                       'displayed_price_precision': 0, 'displayed_market_value_precision': 0}],
        'cash': '0', 'positions_complete': True, 'source_timestamp': '2026-09-30',
        'source_hash': 'fictional-source', 'data_environment': 'SYNTHETIC'})
    selected.connection.close()
    result = CliRunner().invoke(app, ['portfolio', 'exposure', '--as-of', '2026-10-01'])
    assert result.exit_code == 0, result.output
    selected = Ledger(path)
    try:
        assert selected.rows('fund_holdings_cache') == []
        assert selected.rows('market_data_cache') == []
    finally:
        selected.connection.close()
