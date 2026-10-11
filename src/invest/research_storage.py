"""Small reusable immutable research foundation, separate from portfolio state."""

import hashlib
import importlib
import json
import uuid
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from invest.models import DomainError
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
        original_accession_number TEXT, published_at TEXT, source_locator TEXT,
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


def canonical_json_hash(data, identity):
    """Serialize an already domain-normalized package and trusted identity."""
    package = json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    hashed = json.dumps(dict(identity, package=data), sort_keys=True,
                        separators=(',', ':'), ensure_ascii=False)
    return package, hashlib.sha256(hashed.encode()).hexdigest()


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


SPECIALTIES = {
    'NEWS': ('news', 'investobot-news'),
    'POLITICAL': ('political', 'investobot-political-contributions'),
    'EARNINGS': ('earnings', 'investobot-earnings'),
    'COMPETITIVE': ('competitive', 'investobot-competitive'),
    'INSIDERS': ('insiders', 'investobot-management-insiders'),
    'FUND_DILIGENCE': ('fund_diligence', 'investobot-fund-diligence'),
}


class ResearchEnvelope(BaseModel):
    """Routing/provenance only; specialist models own all financial evidence."""
    model_config = ConfigDict(extra='forbid', strict=True)
    kind: Literal['NEWS', 'POLITICAL', 'EARNINGS', 'COMPETITIVE', 'INSIDERS', 'FUND_DILIGENCE']
    issuer_id: str = Field(min_length=1, max_length=200)
    as_of: str
    data_environment: Literal['REAL', 'SYNTHETIC']
    skill_name: str
    package: dict[str, Any]

    @field_validator('as_of')
    @classmethod
    def source_date(cls, value):
        if date.fromisoformat(value).isoformat() != value:
            raise ValueError('Research as_of must be an ISO calendar date')
        return value


class _BatchConnection:
    """Keep existing specialist context managers within the outer acceptance."""
    def __init__(self, connection):
        self.connection = connection

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class _BatchLedger:
    def __init__(self, ledger):
        self.ledger = ledger
        self.connection = _BatchConnection(ledger.connection)

    def __getattr__(self, name):
        return getattr(self.ledger, name)


def _json(data):
    return json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False)


def _record(cursor):
    row = cursor.fetchone()
    return None if row is None else dict(zip(
        [column[0] for column in cursor.description], row, strict=True))


def _prepare(ledger, payload, policy_path):
    try:
        envelope = ResearchEnvelope.model_validate(payload).model_dump()
        module_name, skill_name = SPECIALTIES[envelope['kind']]
        if envelope['skill_name'] != skill_name:
            raise DomainError('Research skill identity contradicts its specialist kind')
        module = importlib.import_module('invest.' + module_name)
        kwargs = {'policy_path': policy_path} if envelope['kind'] == 'POLITICAL' else {}
        preview = module.import_research(ledger, envelope['package'], yes=False, **kwargs)
        run_id = preview['research_run_id']
        package = envelope['package']
        company = package.get('company', {})
        canonical = next((row for row in ledger.rows('securities')
                          if row['id'] == company.get('security_id')), {})
        sourced_issuer = canonical.get('issuer_id') or canonical.get('cik')
        if sourced_issuer and envelope['issuer_id'] != sourced_issuer:
            raise DomainError('Envelope issuer contradicts sourced canonical issuer identity', 3)
        scoped_date = package.get('researched_as_of') or package.get('scope', {}).get('researched_as_of')
        if scoped_date != envelope['as_of']:
            raise DomainError('Envelope date contradicts specialist source scope')
        trusted = SUPPORTED_SKILLS[skill_name]
        identity = {'skill_name': skill_name,
                    'skill_version': trusted.get('skill_version', SKILL_VERSION),
                    'schema_version': trusted['schema_version']}
        if package.get('schema_version') != identity['schema_version']:
            raise DomainError('Research schema identity differs from bundled specialist')
        accepted_identity = ledger.connection.execute(
            'SELECT skill_name,skill_version,schema_version FROM research_runs WHERE id=?',
            (run_id,)).fetchone()
        if accepted_identity is not None:
            identity = dict(zip(('skill_name', 'skill_version', 'schema_version'),
                                accepted_identity, strict=True))
        # The specialist's canonical run hash already includes trusted identity.
        # Keep provenance separate: environment/issuer changes cannot reuse it.
        fingerprint = hashlib.sha256(_json(dict(
            run_id=run_id, kind=envelope['kind'], issuer_id=envelope['issuer_id'],
            as_of=envelope['as_of'], data_environment=envelope['data_environment'],
            **identity)).encode()).hexdigest()
        existing = ledger.connection.execute(
            "SELECT metadata_json FROM research_artifacts WHERE run_id=? AND id='envelope'",
            (run_id,)).fetchone()
        if existing is not None and json.loads(existing[0])['identity_fingerprint'] != fingerprint:
            raise DomainError('Immutable research evidence identity conflicts with accepted provenance', 3)
        return envelope, module, preview, identity, fingerprint, kwargs
    except (ValidationError, ValueError, TypeError, KeyError) as error:
        raise DomainError(f'Research evidence identity or contract invalid: {error}') from error


def import_run(ledger, envelope, *, confirmed=False, policy_path=None):
    return import_batch(ledger, [envelope], confirmed=confirmed, policy_path=policy_path)['runs'][0]


def _political_projection(ledger, run_id, identity):
    record = _record(ledger.connection.execute(
        'SELECT * FROM research_political_runs WHERE id=?', (run_id,)))
    if record is None:
        raise DomainError('Accepted political research identity is unavailable', 3)
    data = json.loads(record['package_json'])
    company, scope = data['company'], data['scope']
    insert_record(ledger.connection, 'research_runs', dict(
        id=run_id, research_type=data['research_type'], **identity,
        company_name=company['name'], ticker=company.get('ticker'),
        security_id=company.get('security_id'), cik=None, fiscal_year=None,
        fiscal_period=None, period_end=scope['period_end'],
        researched_as_of=scope['researched_as_of'], imported_at=record['imported_at'],
        coverage_status=scope['coverage_status'],
        summary_json=_json({'rights_status': scope['rights_status'],
                            'coverage_status': scope['coverage_status']}),
        package_json=record['package_json']))


def import_batch(ledger, envelopes, *, confirmed=False, policy_path=None):
    """Validate all evidence, then explicitly accept the entire batch atomically."""
    if not isinstance(envelopes, list) or not envelopes:
        raise DomainError('Research batch must be a nonempty list')
    prepared = [_prepare(ledger, payload, policy_path) for payload in envelopes]
    identities = {}
    for envelope, _, preview, _, fingerprint, _ in prepared:
        identifier = preview['research_run_id']
        if identifier in identities and identities[identifier] != fingerprint:
            raise DomainError('Research batch contains conflicting evidence identities', 3)
        identities[identifier] = fingerprint
    results = []
    if not confirmed:
        for _, _, preview, identity, _, _ in prepared:
            results.append(dict(preview, run_id=preview['research_run_id'], **identity))
        return {'status': 'PREVIEW', 'committed': False, 'runs': results,
                'mutation_scope': 'research'}
    connection = ledger.connection
    savepoint = 'research_batch_' + uuid.uuid4().hex
    connection.execute('SAVEPOINT ' + savepoint)
    try:
        adapter = _BatchLedger(ledger)
        for envelope, module, preview, identity, fingerprint, kwargs in prepared:
            imported = module.import_research(adapter, envelope['package'], yes=True, **kwargs)
            run_id = imported['research_run_id']
            existing = connection.execute(
                "SELECT metadata_json FROM research_artifacts WHERE run_id=? AND id='envelope'",
                (run_id,)).fetchone()
            added = existing is None
            if existing is not None and json.loads(existing[0])['identity_fingerprint'] != fingerprint:
                raise DomainError('Immutable research evidence identity conflicts during acceptance', 3)
            if added:
                if envelope['kind'] == 'POLITICAL' and connection.execute(
                    'SELECT 1 FROM research_runs WHERE id=?', (run_id,)).fetchone() is None:
                    _political_projection(adapter, run_id, identity)
                metadata = _json(dict(envelope=envelope, trusted_identity=identity,
                                      identity_fingerprint=fingerprint))
                insert_record(connection, 'research_artifacts', dict(
                    run_id=run_id, id='envelope', kind=envelope['kind'],
                    sha256=hashlib.sha256(metadata.encode()).hexdigest(), metadata_json=metadata))
                compact = _json({key: value for key, value in envelope.items() if key != 'package'})
                insert_record(connection, 'research_artifacts', dict(
                    run_id=run_id, id='provenance', kind=envelope['kind'],
                    sha256=hashlib.sha256(compact.encode()).hexdigest(), metadata_json=compact))
            results.append(dict(imported, run_id=run_id, committed=bool(imported['committed'] or added),
                                **identity))
        connection.execute('RELEASE ' + savepoint)
    except Exception:
        connection.execute('ROLLBACK TO ' + savepoint)
        connection.execute('RELEASE ' + savepoint)
        raise
    return {'status': 'AVAILABLE', 'committed': any(row['committed'] for row in results),
            'runs': results, 'mutation_scope': 'research'}


def show(ledger, run_id):
    row = _record(ledger.connection.execute('SELECT * FROM research_runs WHERE id=?', (run_id,)))
    if row is None:
        political = ledger.connection.execute(
            'SELECT package_json FROM research_political_runs WHERE id=?', (run_id,)).fetchone()
        if political is None:
            raise DomainError('Research run identity does not exist')
        return {'run_id': run_id, 'package': json.loads(political[0]),
                'skill_name': 'investobot-political-contributions', 'skill_version': SKILL_VERSION,
                'schema_version': '1.0'}
    artifact = ledger.connection.execute(
        "SELECT metadata_json,sha256 FROM research_artifacts WHERE run_id=? AND id='envelope'",
        (run_id,)).fetchone()
    result = {'run_id': run_id, 'package': json.loads(row['package_json']),
              **{key: row[key] for key in ('skill_name', 'skill_version', 'schema_version',
                                           'research_type', 'researched_as_of', 'coverage_status')}}
    if artifact is not None:
        if hashlib.sha256(artifact[0].encode()).hexdigest() != artifact[1]:
            raise DomainError('Immutable research artifact checksum differs', 3)
        metadata = json.loads(artifact[0])
        result.update(envelope=metadata['envelope'], package=metadata['envelope']['package'],
                      envelope_hash=artifact[1])
    return result


def list_runs(ledger, *, kind=None, issuer_id=None, limit=100):
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 1000:
        raise DomainError('Research list limit must be between 1 and 1000')
    if kind is not None and kind not in SPECIALTIES:
        raise DomainError('Unknown research specialist kind')
    # Compact projections; packages are loaded only by explicit show requests.
    cursor = ledger.connection.execute('''WITH compact AS (SELECT r.id,r.research_type,r.skill_name,
        r.skill_version,r.schema_version,r.researched_as_of,r.coverage_status,
        coalesce(a.kind,CASE r.skill_name
          WHEN 'investobot-news' THEN 'NEWS'
          WHEN 'investobot-earnings' THEN 'EARNINGS'
          WHEN 'investobot-competitive' THEN 'COMPETITIVE'
          WHEN 'investobot-management-insiders' THEN 'INSIDERS'
          WHEN 'investobot-fund-diligence' THEN 'FUND_DILIGENCE'
          WHEN 'investobot-political-contributions' THEN 'POLITICAL' END) AS kind,
        json_extract(a.metadata_json,'$.issuer_id') AS issuer_id,
        json_extract(a.metadata_json,'$.data_environment') AS data_environment
        FROM research_runs r LEFT JOIN research_artifacts a
        ON a.run_id=r.id AND a.id='provenance'
        UNION ALL SELECT p.id,'POLITICAL_CONTRIBUTIONS','investobot-political-contributions',
        ?,'1.0',p.researched_as_of,p.coverage_status,'POLITICAL',NULL,NULL
        FROM research_political_runs p WHERE NOT EXISTS
        (SELECT 1 FROM research_runs r WHERE r.id=p.id))
        SELECT * FROM compact WHERE (? IS NULL OR kind=?)
        AND (? IS NULL OR issuer_id=?) ORDER BY researched_as_of DESC,id LIMIT ?''',
        (SKILL_VERSION, kind, kind, issuer_id, issuer_id, limit))
    names = [column[0] for column in cursor.description]
    return {'status': 'AVAILABLE', 'runs': [dict(zip(names, row, strict=True))
                                           for row in cursor.fetchall()]}
