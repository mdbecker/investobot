"""Immutable share-class evidence imports, isolated from financial state and caches."""

import json
from datetime import datetime, timezone
from decimal import Decimal

from invest.fund_diligence_models import FundDiligenceInput
from invest.research_identity import verify_company
from invest.research_skills import SUPPORTED_SKILLS
from invest.research_storage import canonical_json_hash, decimal_text, insert_record

DDL = [
    """CREATE TABLE research_fund_profiles (
        run_id TEXT PRIMARY KEY,
        registrant_cik TEXT NOT NULL, series_id TEXT NOT NULL, class_id TEXT NOT NULL,
        fund_type TEXT NOT NULL CHECK(fund_type IN ('ETF','MUTUAL_FUND')),
        strategy_type TEXT NOT NULL CHECK(strategy_type IN ('INDEX','ACTIVE')),
        share_class_name TEXT NOT NULL, adviser TEXT, isin TEXT, exchange TEXT,
        methodology_json TEXT NOT NULL, snapshot_json TEXT NOT NULL,
        FOREIGN KEY(run_id) REFERENCES research_runs(id))""",
    """CREATE TABLE research_fund_holdings (
        run_id TEXT NOT NULL, holding_id TEXT NOT NULL, name TEXT NOT NULL,
        security_identifier TEXT, asset_class TEXT NOT NULL,
        weight_pct_text TEXT NOT NULL, source_id TEXT NOT NULL, source_locator TEXT NOT NULL,
        PRIMARY KEY(run_id,holding_id),
        FOREIGN KEY(run_id) REFERENCES research_fund_profiles(run_id),
        FOREIGN KEY(run_id,source_id) REFERENCES research_sources(run_id,source_id))""",
    """CREATE TABLE research_fund_metrics (
        run_id TEXT NOT NULL, metric_id TEXT NOT NULL,
        code TEXT NOT NULL, value_text TEXT NOT NULL, unit TEXT NOT NULL,
        scope TEXT NOT NULL, period_start TEXT, period_end TEXT,
        observed_as_of TEXT, waiver_end_date TEXT,
        source_id TEXT NOT NULL, source_locator TEXT NOT NULL, notes TEXT NOT NULL,
        PRIMARY KEY(run_id,metric_id),
        FOREIGN KEY(run_id) REFERENCES research_fund_profiles(run_id),
        FOREIGN KEY(run_id,source_id) REFERENCES research_sources(run_id,source_id))""",
    """CREATE TABLE research_fund_findings (
        run_id TEXT NOT NULL, finding_id TEXT NOT NULL,
        category TEXT NOT NULL, fact TEXT NOT NULL,
        interpretation TEXT, uncertainty TEXT NOT NULL,
        source_ids_json TEXT NOT NULL, source_locator TEXT NOT NULL,
        PRIMARY KEY(run_id,finding_id),
        FOREIGN KEY(run_id) REFERENCES research_fund_profiles(run_id))""",
    'CREATE INDEX research_fund_metric_code_idx ON research_fund_metrics(run_id,code)',
]


def create_tables(connection):
    for statement in DDL:
        connection.execute(statement)


def canonical_package(payload):
    model = FundDiligenceInput.model_validate(payload)
    data = model.model_dump(mode='json')
    for name in ('sources', 'holdings', 'metrics', 'findings'):
        data[name].sort(key=lambda item: item['id'])
    data['limitations'].sort()
    data['methodology']['source_ids'].sort()
    for row in data['holdings']:
        row['weight_pct'] = decimal_text(row['weight_pct'])
    for row in data['metrics']:
        row['value'] = decimal_text(row['value'])
    for row in data['findings']:
        row['source_ids'].sort()
    name = 'investobot-fund-diligence'
    entry = SUPPORTED_SKILLS[name]
    identity = dict(skill_name=name, skill_version=entry['skill_version'],
                    schema_version=entry['schema_version'], research_type=data['research_type'])
    package, run_id = canonical_json_hash(data, identity)
    if data['holdings_snapshot']['coverage'] == 'TOP_N':
        # Hash identified collections by stable ID, but keep serialized TOP_N
        # evidence valid under its descending-weight input contract. Ties retain
        # the stable ID order established above; original weights never change.
        data['holdings'].sort(key=lambda item: Decimal(item['weight_pct']), reverse=True)
        package = json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return data, package, run_id, identity


def verify_fund(ledger, fund):
    """Reuse canonical security linkage; series/class provenance stays fund-specific."""
    verify_company(ledger, dict(fund, cik=fund['registrant_cik']))
    if fund.get('security_id') and fund.get('isin'):
        from invest.models import DomainError

        row = ledger.connection.execute('SELECT data FROM securities WHERE id=?',
                                        (fund['security_id'],)).fetchone()
        security = json.loads(row[0])
        if security.get('isin') and security['isin'] != fund['isin']:
            raise DomainError('Research ISIN contradicts the canonical security identity', 3)


def validation_warnings(data):
    warnings = list(data['limitations'])
    warnings.append('Human review must verify original SEC series/class identity and disclosures; '
                    'structural validation cannot establish source truth or suitability.')
    if data['holdings_snapshot']['coverage'] != 'FULL':
        warnings.append('Observed holdings may be incomplete; weights are never rescaled.')
    codes = {row['code'] for row in data['metrics']}
    for code, label in [('GROSS_EXPENSE_RATIO', 'Gross expense ratio'),
                        ('NET_EXPENSE_RATIO', 'Net expense ratio'),
                        ('PORTFOLIO_TURNOVER', 'Portfolio turnover')]:
        if code not in codes:
            warnings.append(f'{label} unavailable; missing disclosure is unknown, never zero.')
    if not any(code.endswith('_DISTRIBUTION') for code in codes):
        warnings.append('Distribution history unavailable; absence does not establish tax efficiency.')
    cutoff = data['scope']['researched_as_of']
    for row in data['metrics']:
        expiry = row['waiver_end_date']
        if expiry:
            warnings.append(f"Reported waiver for {row['id']} expires {expiry}" +
                            (' (expired at research cutoff).' if expiry < cutoff else '.'))
    warnings.append('Reported fees, distributions and trading observations are not investor costs, '
                    'tax liabilities, liquidity scores or replacement recommendations.')
    return list(dict.fromkeys(warnings))


def import_research(ledger, payload, yes=False):
    data, package, run_id, identity = canonical_package(payload)
    verify_fund(ledger, data['fund'])
    warnings = validation_warnings(data)
    counts = {f'{name}_count': len(data[key]) for name, key in
              [('holding', 'holdings'), ('metric', 'metrics'),
               ('finding', 'findings'), ('source', 'sources')]}
    compact = dict(counts, fund=data['fund'], scope=data['scope'],
                   limitations=data['limitations'], warnings=warnings)
    exists = ledger.connection.execute('SELECT 1 FROM research_runs WHERE id=?', (run_id,)).fetchone()
    result = dict(status='UNCHANGED' if exists else 'PREVIEW', committed=False,
                  run_id=run_id, research_run_id=run_id, mutation_scope='research',
                  fund=data['fund'], **counts,
                  coverage_status=data['scope']['coverage_status'], warnings=warnings)
    if not yes or exists:
        return result
    fund = data['fund']
    run = dict(id=run_id, **identity, company_name=fund['name'], ticker=fund['ticker'],
               security_id=fund['security_id'], cik=fund['registrant_cik'], fiscal_year=None,
               fiscal_period=None, period_end=None, researched_as_of=data['scope']['researched_as_of'],
               imported_at=datetime.now(timezone.utc).isoformat(),
               coverage_status=data['scope']['coverage_status'], summary_json=json.dumps(compact),
               package_json=package)
    # Validation precedes the transaction; every direct citation is a same-run SQL FK.
    with ledger.connection:
        insert_record(ledger.connection, 'research_runs', run)
        for source in data['sources']:
            row = dict(source, run_id=run_id, source_id=source['id'], cik=source['registrant_cik'],
                       accepted_at=None, is_amendment=False, is_restatement=False,
                       original_accession_number=None)
            for key in ('id', 'registrant_cik', 'series_id', 'class_id'):
                row.pop(key)
            insert_record(ledger.connection, 'research_sources', row)
        profile = {key: fund[key] for key in ('registrant_cik', 'series_id', 'class_id',
                                             'fund_type', 'strategy_type', 'adviser', 'isin', 'exchange')}
        profile.update(run_id=run_id, share_class_name=fund['class_name'],
                       methodology_json=json.dumps(data['methodology']),
                       snapshot_json=json.dumps(data['holdings_snapshot']))
        insert_record(ledger.connection, 'research_fund_profiles', profile)
        for item in data['holdings']:
            row = dict(item, run_id=run_id, holding_id=item['id'], weight_pct_text=item['weight_pct'])
            row.pop('id')
            row.pop('weight_pct')
            insert_record(ledger.connection, 'research_fund_holdings', row)
        for item in data['metrics']:
            row = dict(item, run_id=run_id, metric_id=item['id'], value_text=item['value'])
            row.pop('id')
            row.pop('value')
            insert_record(ledger.connection, 'research_fund_metrics', row)
        for item in data['findings']:
            row = dict(item, run_id=run_id, finding_id=item['id'],
                       source_ids_json=json.dumps(item['source_ids']))
            row.pop('id')
            row.pop('source_ids')
            insert_record(ledger.connection, 'research_fund_findings', row)
    return dict(result, status='IMPORTED', committed=True)
