"""Immutable dated public datasets and disposable, offline analytical readers.

SQLite owns manifests; on-disk batches are content checked before use. DuckDB
connections and consistent SQLite exports are temporary, never authoritative.
"""

import contextlib
import copy
import hashlib
import importlib
import json
import os
import sqlite3
import tempfile
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from invest.models import DomainError

FINANCIAL_COLUMNS = {'adjusted_close', 'adjClose', 'close', 'price', 'quantity', 'shares',
                     'weight', 'weight_percentage', 'market_value', 'value', 'amount',
                     'cost_basis', 'total_return_index', 'expense_ratio', 'aum'}
RUNTIME_MANIFEST = '/opt/investobot/analytics-runtime.json'


class ArtifactInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str | None = None
    kind: str
    sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    path: str | None = None
    relative_path: str | None = None
    rows: list[dict[str, Any]] | None = None
    provider: str | None = None
    security_id: str | None = None
    observed_at: str | None = None
    published_at: str | None = None
    as_of: str | None = None
    effective_from: str | None = None
    effective_to: str | None = None
    data_environment: Literal['REAL', 'SYNTHETIC'] | None = None
    schema_version: str = '1'
    byte_size: int | None = Field(default=None, ge=0)
    coverage: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    replaces_artifact_id: str | None = None
    lineage_id: str | None = None

    @model_validator(mode='after')
    def one_storage(self):
        if sum(value is not None for value in (self.path, self.relative_path, self.rows)) != 1:
            raise ValueError('Artifact must specify exactly one path, relative_path or rows')
        return self


class ManifestInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str | None = None
    data_environment: Literal['REAL', 'SYNTHETIC']
    artifacts: list[ArtifactInput] = Field(default_factory=list)
    as_of: str | None = None
    observed_at: str | None = None
    provider: str | None = None
    purpose: Literal['PUBLIC_DATASET', 'RESEARCH_UNIVERSE'] = 'PUBLIC_DATASET'
    coverage: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


def _issue(code, message, *ids, blocking=True):
    return {'code': code, 'severity': 'ERROR' if blocking else 'WARNING',
            'affected_ids': list(ids), 'blocks_calculation': blocking,
            'blocks_proposal': True, 'blocks_execution_review': True, 'message': message}


def _result(status='AVAILABLE', issues=(), **values):
    return {'status': status, 'issues': list(issues), 'coverage': {}, 'as_of': None,
            'sources': [], 'manifest_ids': [], 'assumptions': {},
            'environment': None, **values}


def _plain(value):
    if not value.is_finite():
        raise DomainError('Dataset financial value is nonfinite')
    text = format(value, 'f')
    if '.' in text:
        text = text.rstrip('0').rstrip('.')
    return '0' if text in {'', '-0'} else text


def _json_value(value, field=None, *, financial=False):
    if isinstance(value, dict):
        return {key: _json_value(cell, key, financial=financial) for key, cell in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(cell, field, financial=financial) for cell in value]
    if isinstance(value, Decimal):
        return _plain(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if financial and field in FINANCIAL_COLUMNS and value is not None:
        if isinstance(value, (float, bool)):
            raise DomainError(f'Financial dataset field {field} needs exact text or Decimal')
        try:
            return _plain(Decimal(str(value)))
        except ArithmeticError as error:
            raise DomainError(f'Invalid financial dataset field {field}') from error
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise DomainError(f'Unsupported dataset value type: {type(value).__name__}')


def _json(value):
    return json.dumps(_json_value(value), sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False)


def _digest(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _hash_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _local_file(path):
    path = Path(path).absolute()
    for component in [path, *path.parents]:
        if component.is_symlink():
            raise DomainError(f'Dataset symlink is not permitted: {component}')
    if not path.is_file():
        raise DomainError(f'Dataset file is unavailable or nonregular: {path}', 2)
    return path


def _relative_path(value):
    if (not isinstance(value, str) or not value or '\\' in value or ':' in value
            or '\x00' in value or value.startswith('/')
            or any(part in {'', '.', '..'} for part in value.split('/'))
            or str(PurePosixPath(value)) != value):
        raise DomainError('Dataset relative path must not escape its artifact root')
    return value


def _model(payload):
    try:
        parsed = ManifestInput.model_validate(payload)
    except ValidationError as error:
        raise DomainError(str(error)) from error
    result = parsed.model_dump(exclude_none=True)
    for artifact in result['artifacts']:
        if artifact.get('data_environment', result['data_environment']) != result['data_environment']:
            raise DomainError('MIXED_DATA_ENVIRONMENT: manifest and artifact environments differ', 3)
        if artifact.get('relative_path'):
            _relative_path(artifact['relative_path'])
        for key in ('observed_at', 'published_at', 'as_of', 'effective_from', 'effective_to'):
            if artifact.get(key):
                _moment(artifact[key])
    for key in ('as_of', 'observed_at'):
        if result.get(key):
            _moment(result[key])
    identifiers = [artifact['id'] for artifact in result['artifacts'] if artifact.get('id')]
    if len(identifiers) != len(set(identifiers)):
        raise DomainError('Artifact IDs must be unique inside a manifest')
    identities = [artifact.get('id') or _digest(artifact) for artifact in result['artifacts']]
    if len(identities) != len(set(identities)):
        raise DomainError('Artifact records must be unique inside a manifest')
    result['artifacts'].sort(key=lambda item: (item.get('id', ''), item['kind'], item['sha256']))
    return result


def _moment(value):
    try:
        if len(value) == 10:
            return datetime.combine(date.fromisoformat(value), datetime.min.time(), UTC)
        stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if stamp.tzinfo is None:
            raise ValueError('Timestamp requires an explicit timezone')
        return stamp.astimezone(UTC)
    except (TypeError, ValueError) as error:
        raise DomainError(f'Invalid source date or timestamp: {value}') from error


def _eligible_date(value, cutoff):
    # Date-only public vintages are observations at calendar-date granularity;
    # date-only cutoffs include that day's observations, without inventing times.
    if len(cutoff) == 10:
        return _moment(value).date() <= date.fromisoformat(cutoff)
    if len(value) == 10:
        return _moment(value).date() < _moment(cutoff).date()
    return _moment(value) <= _moment(cutoff)


def select_vintage(vintages, *, security_id, as_of, artifact_id=None, max_age_days=120):
    """Select known-at-the-time evidence; never use a later-published vintage."""
    _moment(as_of)
    eligible, issues = [], []
    for vintage in vintages:
        if vintage.get('security_id') != security_id:
            continue
        if artifact_id is not None and vintage.get('id') != artifact_id:
            continue
        effective, observed = vintage.get('as_of'), vintage.get('observed_at')
        if effective is None or observed is None:
            issues.append(_issue('UNKNOWN_SOURCE_DATE', 'Vintage chronology is unknown',
                                 str(vintage.get('id'))))
            continue
        if not _eligible_date(effective, as_of) or not _eligible_date(observed, as_of):
            continue
        if vintage.get('published_at') and not _eligible_date(vintage['published_at'], as_of):
            continue
        if vintage.get('effective_from') and not _eligible_date(vintage['effective_from'], as_of):
            continue
        if vintage.get('effective_to') and _moment(vintage['effective_to']).date() < _moment(as_of).date():
            continue
        if vintage.get('data_environment') not in {'REAL', 'SYNTHETIC'}:
            issues.append(_issue('UNKNOWN_DATA_ENVIRONMENT', 'Vintage environment is unverified',
                                 str(vintage.get('id'))))
            continue
        eligible.append(vintage)
    if not eligible:
        return _result('UNAVAILABLE', [*issues, _issue('POINT_IN_TIME_HOLDINGS_UNAVAILABLE',
            'No source-dated holdings vintage was available by the requested date', security_id)],
            rows=None, security_id=security_id, as_of=as_of)
    environments = {item['data_environment'] for item in eligible}
    if len(environments) > 1:
        return _result('BLOCKED', [_issue('MIXED_DATA_ENVIRONMENT',
            'Select a pinned environment instead of mixing vintages', security_id)], rows=None)
    chosen = max(eligible, key=lambda item: (_moment(item['as_of']), _moment(item['observed_at']),
                                            item.get('sha256', ''), item['id']))
    result = copy.deepcopy(chosen)
    result.update(status='AVAILABLE', issues=[], requested_as_of=as_of,
                  manifest_ids=[chosen['id']], environment=chosen['data_environment'])
    if max_age_days is not None and (_moment(as_of).date() - _moment(chosen['as_of']).date()).days > max_age_days:
        result['status'] = 'REVIEW_REQUIRED'
        result['issues'] = [_issue('STALE_HOLDINGS', 'Selected holdings exceed the age policy',
                                    chosen['id'], blocking=False)]
    return result


def _runtime_metadata():
    path = Path(os.environ.get('INVEST_ANALYTICS_RUNTIME', RUNTIME_MANIFEST))
    try:
        data = json.loads(_local_file(path).read_text())
        if not isinstance(data, dict):
            raise DomainError('Runtime manifest must be an object')
        return data
    except (OSError, ValueError, DomainError):
        return {}


def _binary(runtime, key):
    record = runtime.get(key)
    if not isinstance(record, dict) or not record.get('version') or not record.get('sha256'):
        raise DomainError(f'Pinned {key} runtime metadata is unavailable', 2)
    path = _local_file(record['path'])
    if _hash_file(path) != record['sha256']:
        raise DomainError(f'Pinned {key} binary checksum differs', 2)
    return path, record


def _duckdb():
    try:
        return importlib.import_module('duckdb')
    except ModuleNotFoundError as error:
        raise DomainError('Pinned DuckDB analytical runtime is unavailable', 2) from error


def _duck_connection():
    return _duckdb().connect(database=':memory:', config={
        'autoinstall_known_extensions': False, 'autoload_known_extensions': False})


def _load_sqlite_extension(connection, runtime):
    path, _ = _binary(runtime, 'duckdb_sqlite_extension')
    connection.execute("LOAD '" + str(path).replace("'", "''") + "'")


def capabilities():
    """Report verified installed binaries, never install/download anything."""
    runtime = _runtime_metadata()
    result = {'duckdb': {'available': False, 'implicit_download': False, 'version': None},
              'duckdb_sqlite_extension': {'available': False, 'version': None, 'sha256': None},
              'sqlite_vec': {'available': False, 'version': None, 'sha256': None}, 'issues': []}
    try:
        module = _duckdb()
        with contextlib.closing(_duck_connection()) as connection:
            result['duckdb'].update(available=True, version=module.__version__)
            path, record = _binary(runtime, 'duckdb_sqlite_extension')
            _load_sqlite_extension(connection, runtime)
            result['duckdb_sqlite_extension'].update(available=True, version=record['version'],
                                                    sha256=_hash_file(path))
    except Exception as error:
        # Capabilities is diagnostic: unavailable optional facilities remain typed.
        result['issues'].append(_issue('DUCKDB_RUNTIME_UNAVAILABLE', str(error)))
    try:
        path, record = _binary(runtime, 'sqlite_vec')
        with contextlib.closing(sqlite3.connect(':memory:')) as connection:
            connection.enable_load_extension(True)
            try:
                # sqlite-vec's public loader passes its basename; SQLite adds
                # the platform suffix when finding the pinned shared library.
                connection.load_extension(str(path.with_suffix('')))
            finally:
                connection.enable_load_extension(False)
            version = connection.execute('SELECT vec_version()').fetchone()[0]
        if version.lstrip('v') != record['version'].lstrip('v'):
            raise DomainError('sqlite-vec loaded version differs from its runtime pin', 2)
        result['sqlite_vec'].update(available=True, version=record['version'], sha256=_hash_file(path))
    except (DomainError, OSError, KeyError, sqlite3.DatabaseError) as error:
        result['issues'].append(_issue('VECTOR_RUNTIME_UNAVAILABLE', str(error)))
    return result


def _root(ledger, artifact_root=None):
    return Path(artifact_root) if artifact_root is not None else Path(ledger.path).parent


def _artifact_file(artifact, root):
    if artifact.get('relative_path'):
        return _local_file(root / _relative_path(artifact['relative_path']))
    return _local_file(artifact['path'])


def _verify_artifacts(manifest, root):
    issues = []
    for artifact in manifest['artifacts']:
        label = artifact.get('path') or artifact.get('relative_path') or artifact.get('id', artifact['sha256'])
        try:
            if artifact.get('rows') is not None:
                actual = _digest(artifact['rows'])
            else:
                path = _artifact_file(artifact, root)
                actual = _hash_file(path)
                if artifact.get('byte_size') is not None and path.stat().st_size != artifact['byte_size']:
                    issues.append(_issue('ARTIFACT_SIZE_MISMATCH', 'Immutable artifact size differs', label))
            if actual != artifact['sha256']:
                issues.append(_issue('ARTIFACT_HASH_MISMATCH', 'Immutable artifact checksum differs', label))
        except (DomainError, OSError) as error:
            issues.append(_issue('ARTIFACT_UNAVAILABLE', str(error), label))
    return issues


def _manifest(ledger, manifest):
    if isinstance(manifest, str):
        record = ledger.connection.execute('SELECT manifest_json FROM data_snapshots WHERE id=?',
                                            (manifest,)).fetchone()
        if record is None:
            raise DomainError('Frozen dataset manifest does not exist')
        manifest = json.loads(record[0])
    return _model(manifest)


def verify_snapshot(ledger, manifest, *, artifact_root=None):
    manifest = _manifest(ledger, manifest)
    issues = _verify_artifacts(manifest, _root(ledger, artifact_root))
    return _result('BLOCKED' if issues else 'AVAILABLE', issues,
                   manifest_ids=[manifest['id']] if manifest.get('id') else [],
                   source_fingerprint=_digest(manifest),
                   data_environment=manifest['data_environment'],
                   environment=manifest['data_environment'], as_of=manifest.get('as_of'))


def _read_parquet(connection, path):
    cursor = connection.execute('SELECT * FROM read_parquet(?) ORDER BY ALL', [str(path)])
    names = [column[0] for column in cursor.description]
    if len(names) != len(set(names)):
        raise DomainError('Parquet field names must be unique')
    return [_json_value(dict(zip(names, row, strict=True)), financial=True)
            for row in cursor.fetchall()]


def read_snapshot(ledger, manifest, *, artifact_root=None):
    """Read exactly pinned immutable rows; repeat reads never write caches/manifests."""
    manifest = _manifest(ledger, manifest)
    root = _root(ledger, artifact_root)
    verified = verify_snapshot(ledger, manifest, artifact_root=root)
    if verified['status'] != 'AVAILABLE':
        return dict(verified, rows=None)
    rows = []
    connection = None
    try:
        for artifact in manifest['artifacts']:
            if artifact.get('rows') is not None:
                rows.extend(_json_value(artifact['rows'], financial=True))
            else:
                if connection is None:
                    connection = _duck_connection()
                rows.extend(_read_parquet(connection, _artifact_file(artifact, root)))
        # A changing supposedly immutable file cannot sneak through a pre-read check.
        after = _verify_artifacts(manifest, root)
        if after:
            return dict(_result('BLOCKED', after, **{key: verified[key] for key in (
                'manifest_ids', 'source_fingerprint', 'data_environment', 'environment')}), rows=None)
        return dict(verified, rows=sorted(rows, key=_json))
    except (DomainError, OSError) as error:
        return dict(verified, status='UNAVAILABLE', rows=None,
                    issues=[_issue('ANALYTICAL_DATA_UNAVAILABLE', str(error))])
    except Exception as error:
        return dict(verified, status='UNAVAILABLE', rows=None,
                    issues=[_issue('PARQUET_READ_FAILED', str(error))])
    finally:
        if connection is not None:
            connection.close()


@contextlib.contextmanager
def analytical_connection(ledger, manifest, *, artifact_root=None):
    """Temporary DuckDB with a read-only consistent SQLite export and pinned views.

    Domain consumers own fixed SQL. This function never accepts user SQL, and
    does not attach the authoritative ledger to DuckDB.
    """
    from invest.db import connect

    manifest = _manifest(ledger, manifest)
    root = _root(ledger, artifact_root)
    verification = verify_snapshot(ledger, manifest, artifact_root=root)
    if verification['status'] != 'AVAILABLE':
        raise DomainError('Pinned artifacts failed verification', 2)
    with tempfile.TemporaryDirectory(prefix='investobot-analysis-') as temporary:
        exported = Path(temporary) / 'consistent.sqlite'
        with contextlib.closing(connect(ledger.path, readonly=True, initialize=False)) as source:
            source.execute('BEGIN')
            source.execute('SELECT count(*) FROM sqlite_master').fetchone()
            with contextlib.closing(sqlite3.connect(exported)) as destination:
                source.backup(destination)
        with contextlib.closing(_duck_connection()) as connection:
            _load_sqlite_extension(connection, _runtime_metadata())
            connection.execute("ATTACH '" + str(exported).replace("'", "''")
                               + "' AS ledger (TYPE SQLITE, READ_ONLY)")
            for index, artifact in enumerate(manifest['artifacts']):
                if artifact.get('rows') is not None:
                    continue
                path = _artifact_file(artifact, root)
                connection.execute(f'CREATE VIEW artifact_{index} AS SELECT * FROM read_parquet('
                                   + "'" + str(path).replace("'", "''") + "')")
            yield connection
            if _verify_artifacts(manifest, root):
                raise DomainError('Immutable artifacts changed during analysis', 2)


def snapshot(ledger, payload, *, confirm=False, artifact_root=None):
    """Preview or explicitly pin an immutable source manifest in one transaction."""
    manifest = _model(payload)
    verification = verify_snapshot(ledger, manifest, artifact_root=artifact_root)
    if verification['status'] != 'AVAILABLE':
        return dict(verification, committed=False)
    fingerprint = _digest({key: value for key, value in manifest.items() if key != 'id'})
    identifier = manifest.get('id') or 'data-' + fingerprint
    manifest['id'] = identifier
    result = dict(verification, manifest_id=identifier, manifest_ids=[identifier], committed=False,
                  manifest=manifest)
    if not confirm:
        return result
    origin = ledger.connection.execute('SELECT id,manifest_hash FROM data_snapshots '
                                       'WHERE id=? OR manifest_hash=?', (identifier, fingerprint)).fetchone()
    if origin is not None:
        if origin[1] != fingerprint:
            raise DomainError('Immutable dataset manifest ID conflicts with accepted content', 3)
        return dict(result, manifest_id=origin[0], manifest_ids=[origin[0]], unchanged=True)
    artifacts = []
    for artifact in manifest['artifacts']:
        record = copy.deepcopy(artifact)
        record['id'] = artifact.get('id') or 'artifact-' + _digest(artifact)
        record['data_environment'] = artifact.get('data_environment', manifest['data_environment'])
        record['provider'] = artifact.get('provider', manifest.get('provider'))
        record['observed_at'] = artifact.get('observed_at', manifest.get('observed_at'))
        if record['provider'] is None or record['observed_at'] is None:
            return dict(result, status='BLOCKED', issues=[_issue('ARTIFACT_PROVENANCE_INCOMPLETE',
                'Acceptance needs explicit provider and observation date', record['id'])])
        if record.get('path'):
            path = _artifact_file(record, _root(ledger, artifact_root))
            try:
                record['relative_path'] = str(path.relative_to(_root(ledger, artifact_root).absolute()))
            except ValueError as error:
                raise DomainError('Accepted artifacts must reside under their configured artifact root') from error
        artifacts.append(record)
    stamp = datetime.now(UTC).isoformat()
    with ledger.connection:
        if _verify_artifacts(manifest, _root(ledger, artifact_root)):
            raise DomainError('Immutable artifacts changed before acceptance', 3)
        ledger.connection.execute('INSERT INTO data_snapshots VALUES (?,?,?,?,?)',
                                   (identifier, fingerprint, manifest['data_environment'], stamp, _json(manifest)))
        for record in artifacts:
            columns = ('kind','provider','security_id','observed_at','published_at','as_of',
                       'effective_from','effective_to','coverage_json','schema_version','sha256',
                       'relative_path','byte_size','data_environment','replaces_artifact_id','lineage_id')
            identity = tuple(_json({'coverage': record['coverage'], 'metadata': record['metadata']})
                             if column == 'coverage_json' else record.get(column)
                             for column in columns)
            existing = ledger.connection.execute('SELECT ' + ','.join(columns)
                + ' FROM dataset_artifacts WHERE id=?', (record['id'],)).fetchone()
            if existing is not None and tuple(existing) != identity:
                raise DomainError('Immutable artifact ID conflicts with accepted content', 3)
            if existing is None:
                ledger.connection.execute('''INSERT INTO dataset_artifacts
                    (id,kind,provider,security_id,observed_at,published_at,as_of,effective_from,
                     effective_to,coverage_json,schema_version,sha256,relative_path,byte_size,
                     data_environment,replaces_artifact_id,lineage_id,manifest_hash)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
                    record['id'],record['kind'],record['provider'],record.get('security_id'),
                    record['observed_at'],record.get('published_at'),record.get('as_of'),
                    record.get('effective_from'),record.get('effective_to'),
                    _json({'coverage': record['coverage'], 'metadata': record['metadata']}),
                    record['schema_version'],record['sha256'],record.get('relative_path'),
                    record.get('byte_size'),record['data_environment'],
                    record.get('replaces_artifact_id'),record.get('lineage_id'),fingerprint))
            ledger.connection.execute('INSERT INTO data_snapshot_artifacts VALUES (?,?)',
                                       (identifier, record['id']))
    return dict(result, committed=True)


def list_snapshots(ledger):
    records = ledger.connection.execute('SELECT id,manifest_hash,data_environment,observed_at '
                                       'FROM data_snapshots ORDER BY observed_at DESC,id')
    return _result(snapshots=[dict(id=row[0], manifest_hash=row[1], data_environment=row[2],
                                  observed_at=row[3]) for row in records])


def publish_artifact(ledger, source, payload, *, confirm=False, artifact_root=None):
    """Publish one verified batch before pinning it; never replace immutable bytes."""
    manifest = _model(payload)
    if len(manifest['artifacts']) != 1:
        raise DomainError('Publication requires exactly one artifact')
    artifact = manifest['artifacts'][0]
    relative = _relative_path(artifact.get('relative_path'))
    source = _local_file(source)
    if _hash_file(source) != artifact['sha256']:
        return _result('BLOCKED', [_issue('ARTIFACT_HASH_MISMATCH',
            'Publication source checksum differs', str(source))], committed=False)
    if artifact.get('byte_size') is not None and source.stat().st_size != artifact['byte_size']:
        return _result('BLOCKED', [_issue('ARTIFACT_SIZE_MISMATCH',
            'Publication source size differs', str(source))], committed=False)
    if not confirm:
        return _result(manifest=manifest, committed=False)
    root = _root(ledger, artifact_root).absolute()
    target = root / relative
    for component in [target, *target.parents]:
        if component.is_symlink():
            raise DomainError('Artifact publication rejects symlink destinations')
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if _hash_file(_local_file(target)) != artifact['sha256']:
            raise DomainError('Immutable publication destination already differs', 3)
    else:
        descriptor, temporary = tempfile.mkstemp(prefix='.artifact-', dir=target.parent)
        try:
            with os.fdopen(descriptor, 'wb') as destination, source.open('rb') as original:
                for block in iter(lambda: original.read(1024 * 1024), b''):
                    destination.write(block)
                destination.flush()
                os.fsync(destination.fileno())
            if _hash_file(Path(temporary)) != artifact['sha256']:
                raise DomainError('Publication source changed during copying', 3)
            # Hard-link publication is atomic and refuses a concurrent overwrite.
            os.link(temporary, target)
            directory = os.open(target.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            Path(temporary).unlink(missing_ok=True)
    return snapshot(ledger, manifest, confirm=True, artifact_root=root)
