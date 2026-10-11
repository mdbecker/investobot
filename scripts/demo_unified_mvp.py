"""Disposable offline release demonstration through the installed public CLI."""

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from decimal import Decimal
from pathlib import Path

import duckdb

from invest.ledger import Ledger
from invest.research_portfolio import freeze_universe
from invest.search import store_chunks, store_embeddings

AS_OF = '2026-10-10'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class Demo:
    def __init__(self, root):
        self.root = root
        self.path = root / 'portfolio.db'
        self.steps = []
        self.baseline = None
        self.env = dict(os.environ, INVEST_DB=str(self.path), INVEST_CONFIG=str(root / 'config.toml'),
                        INVEST_PROMPTS=str(root / 'prompts'))
        self.env.pop('FMP_API_KEY', None)
        self.env.pop('INVEST_FIXTURES', None)
        (root / 'config.toml').write_text('')

    def file(self, name, payload):
        path = self.root / name
        path.write_text(json.dumps(payload))
        return str(path)

    def state(self):
        ledger = Ledger(self.path)
        try:
            return ledger.planning_state()
        finally:
            ledger.connection.close()

    def cli(self, name, args, exit_code=0):
        result = subprocess.run(['invest', *map(str, args)], env=self.env,
                                capture_output=True, text=True, check=False, timeout=30)
        try:
            output = json.loads(result.stdout if result.returncode == 0 else result.stderr)
        except ValueError as error:
            raise RuntimeError(f'{name} returned non-JSON: {result.stdout} {result.stderr}') from error
        self.steps.append({'name': name, 'argv': ['invest', *map(str, args)],
                           'exit_code': result.returncode, 'output': output})
        if result.returncode != exit_code:
            raise RuntimeError(f'{name}: expected {exit_code}, got {result.returncode}: {output}')
        if name.startswith('data.') and output['status'] != 'AVAILABLE':
            raise RuntimeError(f'{name} did not accept its original immutable sources: {output}')
        if self.baseline is not None and self.state() != self.baseline:
            raise RuntimeError(f'{name} changed accepted financial facts')
        return output

    def apply(self, name, payload):
        path = self.file(name + '.json', payload)
        return self.cli(name, ['portfolio', 'apply', path, '--confirm'])

    def activity(self, name, payload):
        return self.cli(name, ['portfolio', 'record-activity', self.file(name + '.json', payload), '--yes'])

    def parquet(self, name, rows):
        path = self.root / name
        connection = duckdb.connect(':memory:')
        try:
            keys = list(rows[0])
            connection.execute('CREATE TABLE evidence (' + ','.join(f'"{key}" VARCHAR' for key in keys) + ')')
            connection.executemany('INSERT INTO evidence VALUES (' + ','.join('?' for _ in keys) + ')',
                                   [[row[key] for key in keys] for row in rows])
            connection.execute('COPY evidence TO ? (FORMAT PARQUET)', [str(path)])
        finally:
            connection.close()
        return hashlib.sha256(path.read_bytes()).hexdigest()


def observation(account, tax_status, quantity, value, cash, *, date, lot_id, basis):
    positions, lots = [], []
    if quantity != '0':
        positions = [{'security': 'DEMO-WRAP', 'asset_type': 'ETF', 'quantity': quantity,
            'price': '90', 'market_value': value, 'cost_basis': basis, 'as_of': date,
            'displayed_price_precision': 2, 'displayed_market_value_precision': 2}]
        lots = [{'id': lot_id, 'security': 'DEMO-WRAP', 'quantity': quantity,
            'remaining_quantity': quantity, 'cost_basis': basis, 'remaining_adjusted_basis': basis,
            'source_lot_id': 'demo-tax-lot' if account == 'taxable' else 'demo-ira-lot',
            'identity_status': 'VERIFIED', 'saleable': True,
            'identity_source': 'Reviewed original fictional broker lot reference',
            'acquisition_date': '2024-01-01' if account == 'taxable' else '2026-09-20'}]
    return {'account': {'id': account, 'name': 'Fictional ' + account, 'tax_status': tax_status,
                'currency': 'USD', 'history_complete': True}, 'positions': positions, 'lots': lots,
            'cash': cash, 'cash_known': True, 'source_timestamp': date,
            'source_hash': 'fictional-' + account + '-' + date, 'positions_complete': True,
            'lots_complete': True, 'data_environment': 'SYNTHETIC'}


def news(stock):
    return {'schema_version': '1.0', 'research_type': 'NEWS_CATALYSTS_THESIS_CHANGES',
        'company': {'name': 'Fictional Demo Company', 'ticker': 'DEMO-CO',
                    'cik': '0000123456', 'security_id': stock},
        'scope': {'window_start': '2026-10-01', 'window_end': AS_OF, 'researched_as_of': AS_OF,
            'coverage_status': 'PARTIAL', 'searched_source_types': ['ISSUER_RELEASE'],
            'coverage_notes': 'Only one fictional issuer release was reviewed.'},
        'sources': [{'id': 'release', 'source_type': 'ISSUER_RELEASE',
            'publisher': 'Fictional Demo Company', 'url': 'https://example.invalid/demo-release',
            'published_at': '2026-10-06', 'accessed_at': AS_OF, 'source_locator': 'Opening paragraph'}],
        'events': [{'event_key': 'fictional-demo-factory', 'title': 'Fictional factory opened',
            'category': 'OPERATIONS', 'event_date': '2026-10-06', 'date_status': 'CONFIRMED',
            'event_status': 'CONFIRMED', 'affected_segments': [], 'primary_source_id': 'release',
            'source_ids': ['release'], 'facts': [{'fact_key': 'opened',
                'statement': 'The fictional factory opened.', 'source_id': 'release',
                'source_locator': 'Opening paragraph', 'verification_status': 'VERIFIED'}],
            'implications': [], 'follow_up_questions': []}], 'catalysts': [], 'theses': [],
        'limitations': ['Entirely fictional evidence; other specialties not researched.']}


def run_demo(root):
    d = Demo(root)
    html = ('<table><tr><th>Symbol</th><th>Quantity</th><th>Price</th><th>Market Value</th>'
            '<th>Cost Basis</th><th>Acquisition Date</th><th>Lot ID</th><th>Asset Type</th></tr>'
            '<tr><td>DEMO-WRAP</td><td>10.000</td><td>100.00</td><td>1000.00</td>'
            '<td>800.00</td><td>2024-01-01</td><td>demo-tax-lot</td>'
            '<td>ETF</td></tr>'
            '<tr><td>CASH</td><td></td><td></td><td>2000.00</td><td></td><td></td><td></td><td></td></tr></table>')
    source = root / 'fictional-statement.html'
    source.write_text(html)
    args = ['portfolio', 'import', source, '--account', 'taxable', '--tax-status', 'TAXABLE',
            '--as-of', '2026-09-19', '--positions-complete', '--lots-complete',
            '--data-environment', 'SYNTHETIC']
    source.write_text(html.replace('1000.00', '1200.00'))
    bad = d.cli('import.preview_inconsistent', args)
    d.cli('import.reject_inconsistent', ['portfolio', 'apply', d.file('bad.json', bad), '--confirm'], 3)
    source.write_text(html)
    parsed = d.cli('import.preview_taxable', args)
    parsed['account'].update(name='Fictional taxable', history_complete=True)
    # Human review of this explicitly fictional original confirms the printed
    # stable lot reference and that 800 is remaining adjusted basis, not a guess
    # inferred by the provisional institution parser.
    for lot in parsed['lots']:
        lot.update(identity_status='VERIFIED', saleable=True, basis_state='OBSERVED',
                   identity_source='Human reviewed fictional demo-tax-lot printed original reference',
                   remaining_adjusted_basis='800')
    d.apply('import.accept_taxable', parsed)
    d.apply('import.accept_ira', observation('ira', 'TAX_DEFERRED', '0', '0', '1000',
                                           date='2026-09-19', lot_id='unused', basis='0'))
    fund = next(row['id'] for row in d.state()['securities'] if row['ticker'] == 'DEMO-WRAP')
    original_lot = next(row for row in d.state()['lots'] if row['account_id'] == 'taxable')
    tax_lot = original_lot['id']
    d.activity('activity.deposit', {'activity_id': 'fictional-deposit', 'account_id': 'taxable',
        'type': 'CASH_DEPOSIT', 'date': '2026-09-21', 'amount': '200',
        'event_timestamp': '2026-09-21T10:00:00Z', 'source': 'Confirmed fictional deposit record'})
    d.activity('activity.partial_sale', {'activity_id': 'fictional-partial-sale', 'account_id': 'taxable',
        'type': 'SELL', 'security': fund, 'quantity': '2', 'price': '100', 'fee': '0',
        'date': '2026-09-22', 'event_timestamp': '2026-09-22T10:00:00Z',
        'lot_allocations': [{'lot_id': tax_lot, 'quantity': '2'}],
        'source': 'Confirmed fictional sale and executed lot selection'})
    d.activity('activity.ira_purchase', {'activity_id': 'fictional-ira-buy', 'account_id': 'ira',
        'type': 'BUY', 'security': fund, 'quantity': '1', 'price': '100', 'fee': '0',
        'date': '2026-09-20', 'event_timestamp': '2026-09-20T11:00:00Z',
        'source': 'Confirmed fictional household IRA purchase'})
    ira_lot = next(row['id'] for row in d.state()['lots'] if row['account_id'] == 'ira')
    d.apply('import.closing_taxable', observation('taxable', 'TAXABLE', '8', '720', '2400',
                                                date=AS_OF, lot_id=tax_lot, basis='640'))
    d.apply('import.closing_ira', observation('ira', 'TAX_DEFERRED', '1', '90', '900',
                                            date=AS_OF, lot_id=ira_lot, basis='100'))
    d.cli('performance.actual', ['portfolio', 'performance', '--from', '2026-09-19', '--to', AS_OF])
    stock = d.cli('identity.register_company', ['security', 'register', d.file('company.json', {
        'ticker': 'DEMO-CO', 'name': 'Fictional Demo Company', 'asset_type': 'STOCK', 'currency': 'USD',
        'cik': '0000123456', 'issuer_id': '0000123456', 'data_environment': 'SYNTHETIC',
        'source': 'Reviewed fictional original company registration',
        'issuer_identity_evidence': {'source_locator': 'https://example.invalid/demo-registration',
            'source': 'Reviewed fictional original registration', 'reviewed': True, 'cik': '0000123456'}})])['id']
    child = d.cli('identity.register_child_fund', ['security', 'register', d.file('child.json', {
        'ticker': 'DEMO-CHILD', 'name': 'Fictional nested fund', 'asset_type': 'ETF',
        'currency': 'USD', 'source': 'Reviewed fictional original nested fund record'})])['id']
    policy = {'id': 'fictional-demo-policy', 'version': '1', 'data_environment': 'SYNTHETIC',
        'source': 'Explicit fictional human policy approval', 'fee_per_trade': '0',
        'minimum_notional': '25', 'cash_floors': {'taxable': '100'},
        'permissions': {'taxable': {fund: {'can_buy': True, 'can_sell': False,
            'can_hold': True, 'share_increment': '0.001'}}},
        'annual_tax_budget': {'year': 2026, 'annual_allowance': '100', 'short_term_rate': '0.4',
            'long_term_rate': '0.2', 'currency': 'USD', 'taxable_history_complete': True,
            'covered_account_ids': ['taxable'], 'data_environment': 'SYNTHETIC',
            'source': 'Reviewed fictional complete taxable history', 'as_of': '2026-10-10T12:00:00Z'}}
    d.cli('policy.approve', ['policy', 'approve', '--file', d.file('policy.json', policy), '--confirm'])
    d.baseline = d.state()
    fingerprint = digest(d.baseline)
    d.cli('tax.budget', ['tax', 'budget', '--year', '2026', '--as-of', AS_OF, '--policy', policy['id']])
    target = d.cli('target.save', ['target', 'save', d.file('target.json', {
        'name': 'Fictional contribution target', 'data_environment': 'SYNTHETIC',
        'target_allocations': {fund: '1'}, 'planning_constraints': {'eligible_accounts': ['taxable'],
            'permitted_securities': {'taxable': [fund]}}})])
    proposal = d.cli('plan.october_contribution', ['plan', 'propose', '--file', d.file('proposal.json', {
        'target_id': target['id'], 'prices': {fund: {'price': '90', 'as_of': AS_OF,
            'currency': 'USD', 'source': 'Reviewed fictional current quote',
            'data_environment': 'SYNTHETIC', 'manifest_id': 'fictional-current-quote'}}}),
        '--policy', policy['id'], '--mode', 'contributions-only', '--as-of', AS_OF])
    if not proposal['proposed_actions']:
        raise RuntimeError('October proposal did not produce a cash-funded purchase: ' +
                           json.dumps({key: proposal.get(key) for key in ('status', 'issues', 'warnings')}))
    d.cli('tax.harvest_review', ['tax', 'harvest-plan', '--file', d.file('harvest.json', {
        'loss_sale_date': AS_OF, 'security': fund, 'data_environment': 'SYNTHETIC',
        'spouse_history_complete': False, 'outside_account_history_complete': False,
        'dividend_reinvestment_history_complete': None, 'scheduled_acquisitions': []}), '--as-of', AS_OF])
    artifacts = []
    for name, security, holding in [('wrap.parquet', fund, child), ('child.parquet', child, stock)]:
        sha = d.parquet(name, [{'security_id': holding, 'weight': '1'}])
        artifacts.append({'id': 'fictional-' + name, 'kind': 'FUND_HOLDINGS', 'provider': 'FICTIONAL',
            'security_id': security, 'relative_path': name,
            'sha256': sha, 'as_of': '2026-10-01', 'observed_at': '2026-10-01',
            'published_at': '2026-10-01', 'data_environment': 'SYNTHETIC'})
    d.cli('data.nested_holdings', ['data', 'snapshot', '--file', d.file('holdings.json', {
        'data_environment': 'SYNTHETIC', 'artifacts': artifacts})])
    universe = d.cli('portfolio.nested_exposure', ['portfolio', 'research-universe',
        '--as-of', AS_OF, '--top', '20', '--min-exposure', '0'])
    frozen = freeze_universe(universe, requested_top=20, as_of=AS_OF)
    manifest = d.cli('data.freeze_universe', ['data', 'snapshot', '--file', d.file('universe.json', frozen)])
    research_plan = d.cli('research.plan', ['research', 'portfolio', 'plan',
        '--universe-manifest', manifest['manifest_id'], '--window-start', '2026-10-01', '--window-end', AS_OF])
    envelope = {'kind': 'NEWS', 'issuer_id': '0000123456', 'as_of': AS_OF,
        'data_environment': 'SYNTHETIC', 'skill_name': 'investobot-news', 'package': news(stock)}
    d.cli('research.accept_news', ['research', 'news', 'import', d.file('news.json', envelope), '--yes'])
    d.cli('research.partial', ['research', 'portfolio', 'report', '--plan', research_plan['id']])
    sessions = ['2020-01-02', '2020-01-03', '2020-01-06']
    history = [{'date': day, 'total_return_index': value}
               for day, value in zip(sessions, ['100', '105', '110'], strict=True)]
    sha = d.parquet('history.parquet', history)
    history_manifest = d.cli('data.history', ['data', 'snapshot', '--file', d.file('history-manifest.json', {
        'data_environment': 'SYNTHETIC', 'artifacts': [{'id': 'fictional-history',
            'kind': 'DIVIDEND_ADJUSTED_PRICES', 'provider': 'FICTIONAL',
            'relative_path': 'history.parquet', 'sha256': sha, 'as_of': sessions[-1],
            'observed_at': sessions[-1], 'data_environment': 'SYNTHETIC'}]})])
    d.cli('backtest.compare', ['backtest', 'compare', d.file('backtest.json', {
        'start': sessions[0], 'end': sessions[-1], 'manifest_ids': [history_manifest['manifest_id']],
        'data_environment': 'SYNTHETIC', 'mode': 'HYPOTHETICAL_CURRENT_ALLOCATION',
        'candidates': [{'id': 'all-fund', 'weights': {fund: '1'}},
                       {'id': 'half-cash', 'weights': {fund: '0.5', 'CASH': '0.5'}}],
        'history': {fund: history}, 'history_provenance': {'kind': 'DIVIDEND_ADJUSTED_TOTAL_RETURN_INDEX',
            'frequency': 'DAILY_TRADING_SESSION', 'expected_sessions': sessions,
            'source_id': 'reviewed-fictional-history', 'data_environment': 'SYNTHETIC'},
        'cash_return': '0', 'fees': '0', 'starting_value': '1000', 'rebalancing': 'NONE'})])
    text = 'Fictional Demo Company opened a fictional factory.'
    store_chunks(d.path, [{'chunk_id': 'demo-public', 'document_id': 'demo-release', 'text': text,
        'source_url': 'https://example.invalid/demo-release', 'source_date': AS_OF, 'permission': 'PERMITTED',
        'content_hash': hashlib.sha256(text.encode()).hexdigest(), 'offset_start': 0, 'offset_end': len(text),
        'license': 'Explicit reviewed fictional source reuse permission', 'data_environment': 'SYNTHETIC'}], confirmed=True)
    store_embeddings(d.path, ['demo-public'], [[1.0, 0.0]], model_id='fictional-demo-model', user_authorized=True)
    assert d.state() == d.baseline
    d.cli('research.text_search', ['research', 'search', '--query', 'factory'])
    d.cli('research.semantic_search', ['research', 'search', '--query', 'factory', '--semantic',
        '--embedding-file', d.file('vector.json', [1.0, 0.0]), '--model-id', 'fictional-demo-model'])
    export = root / 'immutable-plan.md'
    d.cli('report.export', ['report', 'export', proposal['id'], '--output', export])
    content = export.read_text()
    archive = root / 'verified.tar.gz'
    archived = d.cli('db.backup', ['db', 'backup', '--output', archive])
    if archived['status'] != 'AVAILABLE':
        raise RuntimeError('Archive creation failed: ' + json.dumps(archived))
    verified = d.cli('db.verify', ['db', 'verify', archive])
    if verified['status'] != 'AVAILABLE':
        raise RuntimeError('Archive verification failed: ' + json.dumps(verified))
    restored = root / 'restored' / 'portfolio.db'
    original = d.path
    d.baseline_before_restore = d.baseline
    d.baseline = None
    d.env['INVEST_DB'] = str(restored)
    restored_result = d.cli('db.restore', ['db', 'restore', archive, '--confirm'])
    if restored_result.get('committed') is not True:
        raise RuntimeError('Archive restoration failed: ' + json.dumps(restored_result))
    d.path = restored
    restored_state = d.state()
    restored_search = d.cli('recovery.search', ['research', 'search', '--query', 'factory'])
    d.cli('recovery.verify_database', ['db', 'verify', restored])
    if digest(restored_state) != fingerprint:
        raise RuntimeError('Restored financial state differs: ' + json.dumps({
            key: {'before': d.baseline_before_restore[key], 'after': restored_state[key]}
            for key in restored_state if restored_state[key] != d.baseline_before_restore[key]}))
    for artifact in artifacts + [{'relative_path': 'history.parquet', 'sha256': sha}]:
        assert hashlib.sha256((restored.parent / artifact['relative_path']).read_bytes()).hexdigest() == artifact['sha256']
    tax_remaining = next(lot for lot in restored_state['lots'] if lot['account_id'] == 'taxable')
    sale = next(row for row in restored_state['activities'] if row['activity_id'] == 'fictional-partial-sale')
    allocation = sale['lot_allocations'][0]
    assert Decimal(original_lot['remaining_quantity']) == (
        Decimal(allocation['quantity']) + Decimal(tax_remaining['remaining_quantity']))
    assert Decimal(original_lot['remaining_adjusted_basis']) == (
        Decimal(allocation['basis_removed']) + Decimal(tax_remaining['remaining_adjusted_basis']))
    assert original.exists()
    return {'data_environment': 'SYNTHETIC', 'workspace_path': str(root), 'external_calls': 0,
        'financial_state_unchanged_by_hypotheticals': True, 'accepted_financial_fingerprint': fingerprint,
        'restored_financial_fingerprint': digest(restored_state),
        'accounts': {row['id']: row for row in restored_state['accounts']}, 'steps': d.steps,
        'nested_exposure_path_depth': max(len(path['path']) for company in universe['companies']
            for path in company['contributions']),
        'exported_report': {'plan_id': proposal['id'], 'sha256': hashlib.sha256(content.encode()).hexdigest(),
                            'content': content},
        'partial_lot_conservation': {'original_quantity': original_lot['remaining_quantity'],
            'sold_quantity': allocation['quantity'], 'remaining_quantity': tax_remaining['remaining_quantity'],
            'original_adjusted_basis': original_lot['remaining_adjusted_basis'],
            'sold_adjusted_basis': allocation['basis_removed'],
            'remaining_adjusted_basis': tax_remaining['remaining_adjusted_basis']},
        'recovery': {'archive_verified': True, 'restored_artifact_hashes_verified': True,
                     'restored_corpus_retrievable': bool(restored_search['results'])}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='investobot-fictional-demo-') as temporary:
        report = run_demo(Path(temporary))
    report['disposable_workspace_removed'] = not Path(temporary).exists()
    rendered = json.dumps(report, sort_keys=True)
    if args.output:
        args.output.write_text(rendered + '\n')
    print(rendered)


if __name__ == '__main__':
    main()
