"""Small reusable immutable research foundation, separate from portfolio state."""

import hashlib
import json

from invest.research_skills import SKILL_VERSION, SUPPORTED_SKILLS

DDL = [
    """CREATE TABLE research_runs (
        id TEXT PRIMARY KEY, research_type TEXT NOT NULL, skill_name TEXT NOT NULL,
        skill_version TEXT NOT NULL, schema_version TEXT NOT NULL,
        company_name TEXT NOT NULL, ticker TEXT, security_id TEXT, cik TEXT,
        fiscal_year INTEGER, fiscal_period TEXT, period_end TEXT,
        researched_as_of TEXT NOT NULL, imported_at TEXT NOT NULL,
        coverage_status TEXT NOT NULL, summary_json TEXT NOT NULL, package_json TEXT NOT NULL,
        FOREIGN KEY(security_id) REFERENCES securities(id))""",
    """CREATE INDEX research_runs_lookup_idx ON research_runs
        (research_type,ticker,researched_as_of DESC)""",
    """CREATE TABLE research_sources (
        run_id TEXT NOT NULL, source_id TEXT NOT NULL, source_type TEXT NOT NULL,
        publisher TEXT NOT NULL, url TEXT NOT NULL, accession_number TEXT,
        filed_at TEXT, accessed_at TEXT NOT NULL, cik TEXT, accepted_at TEXT,
        is_amendment INTEGER NOT NULL CHECK(is_amendment IN (0,1)),
        is_restatement INTEGER NOT NULL CHECK(is_restatement IN (0,1)),
        original_accession_number TEXT,
        PRIMARY KEY(run_id,source_id),
        FOREIGN KEY(run_id) REFERENCES research_runs(id))""",
]


def create_tables(connection):
    for statement in DDL:
        connection.execute(statement)


def decimal_text(value):
    if value is None:
        return value
    result = value.rstrip('0').rstrip('.') if '.' in value else value
    return '0' if result in {'-0', '0'} else result


def canonical_package(model, skill_name):
    """Normalize financial strings only; identifiers retain their exact spelling."""
    data = model.model_dump(mode='json')
    for collection in ('sources', 'metrics', 'guidance', 'findings'):
        data[collection].sort(key=lambda item: item['id'])
    for metric in data['metrics']:
        for field in ('value', 'source_value', 'source_scale'):
            metric[field] = decimal_text(metric.get(field))
    for guidance in data['guidance']:
        for field in ('lower_value', 'upper_value'):
            guidance[field] = decimal_text(guidance.get(field))
    identity = {'skill_name': skill_name, 'skill_version': SKILL_VERSION,
                'schema_version': SUPPORTED_SKILLS[skill_name]['schema_version'],
                'research_type': data['research_type']}
    if data['schema_version'] != identity['schema_version']:
        raise ValueError('Research contract does not match bundled skill')
    package = json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    hashed = json.dumps(dict(identity, package=data), sort_keys=True,
                        separators=(',', ':'), ensure_ascii=False)
    return data, package, hashlib.sha256(hashed.encode()).hexdigest(), identity


def insert_record(connection, table, record):
    """Only internal table/column constants reach this explicit SQLite helper."""
    columns = ','.join(record)
    placeholders = ','.join('?' for _ in record)
    connection.execute(f'INSERT INTO {table} ({columns}) VALUES ({placeholders})',
                       tuple(record.values()))
