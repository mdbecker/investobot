"""Validate and atomically accept reported earnings, without financial mutations."""

import json
from datetime import datetime, timezone

from invest.earnings_models import EarningsResearchInput
from invest.research_identity import verify_company
from invest.research_storage import canonical_package, insert_record

DDL = [
    """CREATE TABLE research_earnings_metrics (
        run_id TEXT NOT NULL, metric_id TEXT NOT NULL, metric_code TEXT NOT NULL,
        metric_label TEXT NOT NULL, metric_definition TEXT NOT NULL, value_text TEXT NOT NULL,
        unit TEXT NOT NULL, accounting_basis TEXT NOT NULL,
        period_type TEXT NOT NULL CHECK(period_type IN ('INSTANT','DURATION')),
        period_length TEXT, period_start TEXT, period_end TEXT NOT NULL,
        fiscal_year INTEGER NOT NULL, fiscal_period TEXT NOT NULL,
        measurement_type TEXT NOT NULL CHECK(measurement_type='REPORTED'),
        scope TEXT NOT NULL, segment_name TEXT, source_id TEXT NOT NULL,
        source_locator TEXT NOT NULL, xbrl_taxonomy TEXT, xbrl_concept TEXT,
        source_value TEXT, source_unit TEXT, source_scale TEXT, reconciliation_disclosed INTEGER,
        PRIMARY KEY(run_id,metric_id), FOREIGN KEY(run_id) REFERENCES research_runs(id),
        FOREIGN KEY(run_id,source_id) REFERENCES research_sources(run_id,source_id),
        CHECK((period_type='INSTANT' AND period_start IS NULL)
           OR (period_type='DURATION' AND period_start IS NOT NULL)))""",
    """CREATE INDEX earnings_metric_lookup_idx ON research_earnings_metrics
        (metric_code,fiscal_year,fiscal_period)""",
    """CREATE TABLE research_earnings_guidance (
        run_id TEXT NOT NULL, guidance_id TEXT NOT NULL, metric_code TEXT NOT NULL,
        period_start TEXT NOT NULL, period_end TEXT NOT NULL, lower_value TEXT, upper_value TEXT,
        unit TEXT NOT NULL, accounting_basis TEXT NOT NULL, guidance_status TEXT NOT NULL,
        source_id TEXT NOT NULL, source_locator TEXT NOT NULL, qualifiers TEXT NOT NULL,
        issued_at TEXT, prior_guidance_id TEXT,
        PRIMARY KEY(run_id,guidance_id), FOREIGN KEY(run_id) REFERENCES research_runs(id),
        FOREIGN KEY(run_id,source_id) REFERENCES research_sources(run_id,source_id))""",
    """CREATE TABLE research_earnings_findings (
        run_id TEXT NOT NULL, finding_id TEXT NOT NULL, category TEXT NOT NULL,
        statement TEXT NOT NULL, source_id TEXT, source_locator TEXT,
        limitations_json TEXT NOT NULL,
        PRIMARY KEY(run_id,finding_id), FOREIGN KEY(run_id) REFERENCES research_runs(id),
        FOREIGN KEY(run_id,source_id) REFERENCES research_sources(run_id,source_id))""",
]


def create_tables(connection):
    for statement in DDL:
        connection.execute(statement)


def validation_warnings(data):
    warnings = list(data['limitations'])
    if data['coverage_status'] != 'COMPLETE_WITHIN_DECLARED_SCOPE':
        warnings.append('Research coverage is incomplete; absent metrics remain unknown.')
    if not data['company'].get('cik'):
        warnings.append('Company CIK is unknown; reporting-entity verification is limited.')
    for metric in data['metrics']:
        if metric['accounting_basis'] == 'NON_GAAP' and not metric.get('reconciliation_disclosed'):
            warnings.append(f"Non-GAAP reconciliation is unavailable for {metric['id']}.")
    for source in data['sources']:
        if source.get('is_amendment') or source.get('is_restatement'):
            warnings.append(f"Amended/restated source {source['id']} preserves original accession "
                            f"{source.get('original_accession_number')}.")
    for guidance in data['guidance']:
        if not guidance.get('issued_at'):
            warnings.append(f"Guidance issue date is unknown for {guidance['id']}.")
    return warnings


def import_research(ledger, payload, yes=False):
    model = EarningsResearchInput.model_validate(payload)
    data, package, run_id, identity = canonical_package(model, 'investobot-earnings')
    verify_company(ledger, data['company'])
    warnings = validation_warnings(data)
    compact = {'metric_count': len(data['metrics']), 'guidance_count': len(data['guidance']),
               'finding_count': len(data['findings']), 'warning_count': len(warnings),
               'warnings': warnings}
    exists = ledger.connection.execute('SELECT 1 FROM research_runs WHERE id=?', (run_id,)).fetchone()
    result = {'status': 'UNCHANGED' if exists else 'PREVIEW', 'committed': False,
              'research_run_id': run_id, 'company': data['company']['name'],
              'reporting_period': f"{data['reporting_period']['fiscal_year']}-{data['reporting_period']['fiscal_period']}",
              'metric_count': compact['metric_count'], 'guidance_count': compact['guidance_count'],
              'finding_count': compact['finding_count'], 'warning_count': len(warnings),
              'warnings': warnings, 'mutation_scope': 'research'}
    if not yes or exists:
        return result
    run = dict(id=run_id, **identity, company_name=data['company']['name'],
               ticker=data['company'].get('ticker'), security_id=data['company'].get('security_id'),
               cik=data['company'].get('cik'), **data['reporting_period'],
               researched_as_of=data['researched_as_of'],
               imported_at=datetime.now(timezone.utc).isoformat(),
               coverage_status=data['coverage_status'], summary_json=json.dumps(compact),
               package_json=package)
    with ledger.connection:
        insert_record(ledger.connection, 'research_runs', run)
        for source in data['sources']:
            row = dict(source, run_id=run_id, source_id=source['id'])
            row.pop('id')
            insert_record(ledger.connection, 'research_sources', row)
        for metric in data['metrics']:
            row = dict(metric, run_id=run_id, metric_id=metric['id'], value_text=metric['value'])
            row.pop('id')
            row.pop('value')
            insert_record(ledger.connection, 'research_earnings_metrics', row)
        for guidance in data['guidance']:
            row = dict(guidance, run_id=run_id, guidance_id=guidance['id'])
            row.pop('id')
            insert_record(ledger.connection, 'research_earnings_guidance', row)
        for finding in data['findings']:
            row = dict(finding, run_id=run_id, finding_id=finding['id'],
                       limitations_json=json.dumps(finding['limitations']))
            row.pop('id')
            row.pop('limitations')
            insert_record(ledger.connection, 'research_earnings_findings', row)
    return dict(result, status='IMPORTED', committed=True)
