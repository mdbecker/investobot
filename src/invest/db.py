"""One typed SQLite ledger design, initialized only on an empty database.

Public dictionaries are domain values, not persisted JSON financial tables.
A presence bitmap preserves omitted versus explicitly unknown input fields.
"""

import fcntl
import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from invest.models import DomainError

SCHEMA_VERSION = 1

# SQL table names are internal constants; user input never becomes an identifier.
TABLE_NAMES = {'positions': 'position_balances', 'lots': 'tax_lots',
               'snapshots': 'snapshot_observations'}
FIELDS = {
    'accounts': {
        'id': 'TEXT PRIMARY KEY', 'name': 'TEXT', 'institution': 'TEXT',
        'account_type': 'TEXT', 'tax_status': 'TEXT', 'currency': 'TEXT',
        'active': 'INTEGER CHECK(active IN (0,1))',
        'history_complete': 'INTEGER CHECK(history_complete IN (0,1))',
        'data_environment': 'TEXT', 'metadata_history': 'TEXT'},
    'securities': {
        'id': 'TEXT PRIMARY KEY', 'ticker': 'TEXT', 'name': 'TEXT', 'asset_type': 'TEXT',
        'currency': 'TEXT', 'cusip': 'TEXT', 'isin': 'TEXT', 'figi': 'TEXT', 'cik': 'TEXT',
        'lei': 'TEXT', 'issuer_id': 'TEXT', 'source': 'TEXT',
        'ticker_aliases': 'TEXT', 'classification_history': 'TEXT',
        'issuer_identity_evidence': 'TEXT', 'data_environment': 'TEXT'},
    'positions': {
        'id': 'TEXT PRIMARY KEY', 'account_id': 'TEXT NOT NULL REFERENCES accounts(id)',
        'security_id': 'TEXT NOT NULL REFERENCES securities(id)',
        'security': 'TEXT', 'name': 'TEXT', 'asset_type': 'TEXT', 'currency': 'TEXT',
        'quantity': 'TEXT NOT NULL', 'price': 'TEXT', 'market_value': 'TEXT',
        'cost_basis': 'TEXT', 'as_of': 'TEXT', 'source_timestamp': 'TEXT',
        'lot_state': 'TEXT', 'valuation_state': 'TEXT', 'data_environment': 'TEXT',
        'observation_id': 'TEXT REFERENCES snapshot_observations(id) DEFERRABLE INITIALLY DEFERRED',
        'displayed_price_precision': 'INTEGER', 'displayed_market_value_precision': 'INTEGER',
        'cell_provenance': 'TEXT', 'cusip': 'TEXT', 'isin': 'TEXT', 'figi': 'TEXT',
        'sector': 'TEXT', 'country': 'TEXT'},
    'lots': {
        'id': 'TEXT PRIMARY KEY', 'account_id': 'TEXT NOT NULL REFERENCES accounts(id)',
        'security_id': 'TEXT NOT NULL REFERENCES securities(id)', 'security': 'TEXT',
        'acquisition_date': 'TEXT', 'quantity': 'TEXT NOT NULL',
        'remaining_quantity': 'TEXT NOT NULL', 'cost_basis': 'TEXT',
        'remaining_adjusted_basis': 'TEXT', 'wash_adjustment': 'TEXT',
        'source_lot_id': 'TEXT', 'identity_status': 'TEXT', 'identity_source': 'TEXT',
        'acquisition_reference': 'TEXT', 'source_timestamp': 'TEXT', 'basis_state': 'TEXT',
        'data_environment': 'TEXT', 'saleable': 'INTEGER CHECK(saleable IN (0,1))',
        'observation_id': 'TEXT REFERENCES snapshot_observations(id) DEFERRABLE INITIALLY DEFERRED',
        'cell_provenance': 'TEXT'},
    'cash_balances': {
        'id': 'TEXT PRIMARY KEY', 'account_id': 'TEXT NOT NULL UNIQUE REFERENCES accounts(id)',
        'amount': 'TEXT NOT NULL', 'currency': 'TEXT', 'as_of': 'TEXT',
        'source_timestamp': 'TEXT', 'imported_at': 'TEXT', 'data_environment': 'TEXT',
        'observation_id': 'TEXT REFERENCES snapshot_observations(id) DEFERRABLE INITIALLY DEFERRED'},
    'activities': {
        'id': 'TEXT PRIMARY KEY', 'activity_id': 'TEXT NOT NULL UNIQUE',
        'account_id': 'TEXT NOT NULL REFERENCES accounts(id)',
        'security_id': 'TEXT REFERENCES securities(id)', 'security': 'TEXT',
        'type': 'TEXT NOT NULL', 'date': 'TEXT NOT NULL', 'event_timestamp': 'TEXT',
        'quantity': 'TEXT', 'price': 'TEXT', 'fee': 'TEXT', 'amount': 'TEXT',
        'currency': 'TEXT', 'source': 'TEXT', 'classification': 'TEXT',
        'to_account': 'TEXT', 'from_account': 'TEXT', 'transfer_id': 'TEXT',
        'recorded_at': 'TEXT', 'data_environment': 'TEXT'},
    'targets': {
        'id': 'TEXT PRIMARY KEY', 'name': 'TEXT', 'description': 'TEXT', 'status': 'TEXT',
        'version': 'INTEGER', 'created_at': 'TEXT', 'updated_at': 'TEXT',
        'current_version_id': 'TEXT'},
}
JSON_FIELDS = {'metadata_history', 'classification_history', 'ticker_aliases',
               'issuer_identity_evidence', 'cell_provenance'}
BOOL_FIELDS = {'active', 'history_complete', 'saleable'}
DECIMAL_FIELDS = {'quantity', 'remaining_quantity', 'price', 'market_value', 'cost_basis',
                  'remaining_adjusted_basis', 'wash_adjustment', 'amount', 'fee'}
PAYLOAD_TABLES = {'snapshots', 'market_data_cache', 'fund_holdings_cache',
                  'trade_proposals', 'target_versions'}


def text_decimal(value):
    """Plain exact notation, independent of the active Decimal context precision."""
    if value is None:
        return None
    try:
        number = Decimal(str(value))
    except InvalidOperation as error:
        raise DomainError('Invalid persisted decimal') from error
    if not number.is_finite():
        raise DomainError('Nonfinite persisted decimal')
    plain = format(number, 'f')
    if '.' in plain:
        plain = plain.rstrip('0').rstrip('.')
    return '0' if plain in {'-0', ''} else plain


def _ddl():
    statements = []
    for table, fields in FIELDS.items():
        name = TABLE_NAMES.get(table, table)
        columns = ','.join(f'{key} {spec}' for key, spec in fields.items())
        constraints = ',UNIQUE(account_id,security_id)' if table == 'positions' else ''
        statements.append(f'CREATE TABLE {name} ({columns},present INTEGER NOT NULL{constraints})')
    statements.extend([
        '''CREATE TABLE snapshot_observations (
            id TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts(id),
            source_timestamp TEXT,imported_at TEXT NOT NULL,source_hash TEXT NOT NULL,
            fingerprint TEXT NOT NULL UNIQUE,positions_complete INTEGER NOT NULL,
            lots_complete INTEGER NOT NULL,cash_known INTEGER NOT NULL,data_environment TEXT,
            status TEXT NOT NULL,payload_json TEXT NOT NULL)''',
        '''CREATE INDEX observations_account_source_idx ON snapshot_observations
            (account_id,source_timestamp,imported_at,id)''',
        '''CREATE TABLE activity_lot_allocations (
            activity_id TEXT NOT NULL REFERENCES activities(activity_id),
            lot_id TEXT NOT NULL REFERENCES tax_lots(id) DEFERRABLE INITIALLY DEFERRED,
            quantity TEXT NOT NULL,basis_removed TEXT,term TEXT,
            realized_gain TEXT,fee_allocated TEXT,PRIMARY KEY(activity_id,lot_id))''',
        '''CREATE INDEX activities_account_date_idx ON activities(account_id,date,activity_id)''',
        '''CREATE INDEX lots_account_security_idx ON tax_lots(account_id,security_id)''',
        '''CREATE TABLE security_aliases (
            security_id TEXT NOT NULL REFERENCES securities(id),kind TEXT NOT NULL,
            value TEXT NOT NULL,source TEXT,source_locator TEXT,accepted_at TEXT,
            PRIMARY KEY(security_id,kind,value))''',
        '''CREATE INDEX aliases_value_idx ON security_aliases(kind,value)''',
        '''CREATE TABLE valuation_marks (
            id TEXT PRIMARY KEY,account_id TEXT NOT NULL REFERENCES accounts(id),
            security_id TEXT REFERENCES securities(id),effective_at TEXT NOT NULL,
            value TEXT,currency TEXT NOT NULL,coverage_complete INTEGER NOT NULL,
            observation_id TEXT REFERENCES snapshot_observations(id),data_environment TEXT,
            source_hash TEXT,flow_timing TEXT)''',
        '''CREATE INDEX valuations_account_date_idx ON valuation_marks(account_id,effective_at)''',
        '''CREATE TABLE external_cash_flows (
            activity_id TEXT PRIMARY KEY REFERENCES activities(activity_id),
            account_id TEXT NOT NULL REFERENCES accounts(id),effective_date TEXT NOT NULL,
            amount_signed TEXT NOT NULL,currency TEXT NOT NULL,classification TEXT NOT NULL,
            transfer_id TEXT,flow_timing TEXT,data_environment TEXT)''',
        '''CREATE TABLE tax_policy_versions (
            id TEXT PRIMARY KEY,year INTEGER NOT NULL,currency TEXT NOT NULL,
            annual_allowance TEXT NOT NULL,short_term_rate TEXT,long_term_rate TEXT,
            approved_at TEXT NOT NULL,payload_json TEXT NOT NULL)''',
        '''CREATE TABLE trading_policy_versions (
            id TEXT PRIMARY KEY,approved_at TEXT NOT NULL,policy_hash TEXT NOT NULL UNIQUE,
            payload_json TEXT NOT NULL)''',
        '''CREATE TABLE dataset_artifacts (
            id TEXT PRIMARY KEY,kind TEXT NOT NULL,provider TEXT NOT NULL,security_id TEXT,
            observed_at TEXT NOT NULL,published_at TEXT,as_of TEXT,effective_from TEXT,
            effective_to TEXT,coverage_json TEXT NOT NULL,schema_version TEXT NOT NULL,
            sha256 TEXT NOT NULL,relative_path TEXT,byte_size INTEGER,data_environment TEXT NOT NULL
            CHECK(data_environment IN ('REAL','SYNTHETIC')),
            replaces_artifact_id TEXT REFERENCES dataset_artifacts(id),lineage_id TEXT,
            manifest_hash TEXT,status TEXT NOT NULL DEFAULT 'AVAILABLE')''',
        '''CREATE INDEX datasets_vintage_idx ON dataset_artifacts(kind,security_id,as_of,observed_at)''',
        '''CREATE TABLE data_snapshots (
            id TEXT PRIMARY KEY,manifest_hash TEXT NOT NULL UNIQUE,data_environment TEXT NOT NULL,
            observed_at TEXT NOT NULL,manifest_json TEXT NOT NULL)''',
        '''CREATE TABLE data_snapshot_artifacts (
            snapshot_id TEXT NOT NULL REFERENCES data_snapshots(id),
            artifact_id TEXT NOT NULL REFERENCES dataset_artifacts(id),
            PRIMARY KEY(snapshot_id,artifact_id))''',
        '''CREATE TABLE document_chunks (
            id TEXT PRIMARY KEY,document_id TEXT NOT NULL,issuer_id TEXT,source_url TEXT,
            published_at TEXT,observed_at TEXT,permission TEXT NOT NULL,content_hash TEXT NOT NULL,
            start_offset INTEGER NOT NULL,end_offset INTEGER NOT NULL,text TEXT NOT NULL,
            source_metadata_json TEXT NOT NULL)''',
        '''CREATE TABLE embeddings (
            chunk_id TEXT NOT NULL REFERENCES document_chunks(id),model_id TEXT NOT NULL,
            dimension INTEGER NOT NULL,vector BLOB NOT NULL,chunk_hash TEXT NOT NULL,
            PRIMARY KEY(chunk_id,model_id))''',
        '''CREATE TABLE plan_baselines (id TEXT PRIMARY KEY,state_json TEXT NOT NULL)''',
        '''CREATE TABLE plan_runs (
            id TEXT PRIMARY KEY,baseline_id TEXT NOT NULL REFERENCES plan_baselines(id),
            created_at TEXT NOT NULL,as_of TEXT NOT NULL,generated_status TEXT NOT NULL,
            summary_json TEXT NOT NULL,details_json TEXT NOT NULL,
            price_assumptions_hash TEXT NOT NULL,tax_assumptions_hash TEXT NOT NULL)''',
        '''CREATE INDEX plans_created_idx ON plan_runs(created_at DESC,id DESC)''',
        '''CREATE TABLE research_artifacts (
            run_id TEXT NOT NULL REFERENCES research_runs(id),id TEXT NOT NULL,
            kind TEXT NOT NULL,sha256 TEXT NOT NULL,metadata_json TEXT NOT NULL,
            PRIMARY KEY(run_id,id))''',
        '''CREATE TABLE schema_migrations (
            id TEXT PRIMARY KEY,checksum TEXT NOT NULL,applied_at TEXT NOT NULL)''',
    ])
    for table in ('market_data_cache', 'fund_holdings_cache', 'trade_proposals'):
        statements.append(f'''CREATE TABLE {table} (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL)''')
    statements.append('''CREATE TABLE target_versions (
        version_id TEXT PRIMARY KEY,target_id TEXT NOT NULL,version INTEGER NOT NULL,
        payload_json TEXT NOT NULL,UNIQUE(target_id,version),
        FOREIGN KEY(target_id) REFERENCES targets(id) DEFERRABLE INITIALLY DEFERRED)''')
    return statements


DDL = _ddl()
SCHEMA_CHECKSUM = hashlib.sha256('\n'.join(DDL).encode()).hexdigest()


def validate_schema(connection):
    version = connection.execute('PRAGMA user_version').fetchone()[0]
    try:
        identity = connection.execute("SELECT checksum FROM schema_migrations WHERE id='001'").fetchone()
    except sqlite3.DatabaseError:
        identity = None
    if version != SCHEMA_VERSION or not identity or identity[0] != SCHEMA_CHECKSUM:
        raise DomainError('UNSUPPORTED_DEVELOPMENT_SCHEMA: this ledger is not the unified '
                          'schema; preserve it and select an empty new-design path', 3)


class LedgerConnection(sqlite3.Connection):
    """Every application connection participates in the restore exclusion lock."""

    restore_lock = None

    def close(self):
        try:
            super().close()
        finally:
            if self.restore_lock is not None:
                self.restore_lock.close()
                self.restore_lock = None


def _connection(path, *, readonly=False):
    memory = str(path) == ':memory:'
    lock = None
    if not memory:
        lock_path = Path(str(path) + '.restore.lock')
        descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        lock = os.fdopen(descriptor, 'r+')
        try:
            fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError as error:
            lock.close()
            raise DomainError('RESTORE_IN_PROGRESS: ledger access is temporarily blocked', 3) from error
    try:
        selected = (Path(path).absolute().as_uri() + '?mode=ro') if readonly else path
        connection = sqlite3.connect(selected, uri=readonly, timeout=5, factory=LedgerConnection)
    except Exception:
        if lock is not None:
            lock.close()
        raise
    connection.restore_lock = lock
    return connection


def initialize(connection):
    from invest.competitive import create_tables as competitive_tables
    from invest.earnings import create_tables as earnings_tables
    from invest.fund_diligence import create_tables as fund_tables
    from invest.insiders import create_tables as insider_tables
    from invest.news import create_tables as news_tables
    from invest.political import create_tables as political_tables
    from invest.research_storage import create_tables as research_tables

    with connection:
        connection.execute('BEGIN IMMEDIATE')
        for statement in DDL:
            connection.execute(statement)
        political_tables(connection)
        research_tables(connection)
        earnings_tables(connection)
        news_tables(connection)
        competitive_tables(connection)
        insider_tables(connection)
        fund_tables(connection)
        connection.execute('INSERT INTO schema_migrations VALUES (?,?,?)',
            ('001', SCHEMA_CHECKSUM, datetime.now(timezone.utc).isoformat()))
        connection.execute(f'PRAGMA user_version={SCHEMA_VERSION}')


def connect(path, readonly=False, initialize=True):
    """Validate existing files before any write-capable pragmas or initialization."""
    memory = str(path) == ':memory:'
    selected = Path(path)
    if readonly:
        check = sqlite3.connect(selected.absolute().as_uri() + '?mode=ro', uri=True)
        try:
            validate_schema(check)
        finally:
            check.close()
        connection = _connection(selected, readonly=True)
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA busy_timeout=5000')
        return connection
    if not memory and selected.exists() and selected.stat().st_size:
        check = sqlite3.connect(selected.absolute().as_uri() + '?mode=ro', uri=True)
        try:
            validate_schema(check)
        finally:
            check.close()
    elif not initialize:
        raise DomainError('Database is unavailable', 3)
    if not memory:
        selected.parent.mkdir(parents=True, exist_ok=True)
    connection = _connection(':memory:' if memory else selected)
    connection.execute('PRAGMA foreign_keys=ON')
    connection.execute('PRAGMA busy_timeout=5000')
    connection.execute('PRAGMA journal_mode=WAL')
    connection.execute('PRAGMA synchronous=FULL')
    if connection.execute('PRAGMA user_version').fetchone()[0] == 0:
        if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table'").fetchone():
            connection.close()
            raise DomainError('UNSUPPORTED_DEVELOPMENT_SCHEMA: nonempty unversioned ledger', 3)
        # initialize is the function as well as the public flag name.
        globals()['initialize'](connection)
    return connection


def rows(connection, table, key=None):
    physical = TABLE_NAMES.get(table, table)
    if table in PAYLOAD_TABLES:
        return [json.loads(row[0]) for row in connection.execute(
            f'SELECT payload_json FROM {physical} ORDER BY ' +
            ('version_id' if table == 'target_versions' else 'id'))]
    fields = FIELDS[table]
    keys = list(fields)
    result = []
    where = ' WHERE id=?' if key is not None else ''
    for record in connection.execute(f'SELECT {",".join(keys)},present FROM {physical}' + where +
                                     ' ORDER BY id', (key,) if key is not None else ()):
        value = {}
        for index, key in enumerate(keys):
            if not record[-1] & (1 << index):
                continue
            cell = record[index]
            if key in JSON_FIELDS and cell is not None:
                cell = json.loads(cell)
            elif key in BOOL_FIELDS and cell is not None:
                cell = bool(cell)
            value[key] = cell
        if table == 'activities':
            allocations = list(connection.execute('SELECT lot_id,quantity FROM activity_lot_allocations '
                                                  'WHERE activity_id=? ORDER BY rowid', (value['activity_id'],)))
            if allocations:
                value['lot_allocations'] = [dict(lot_id=row[0], quantity=row[1]) for row in allocations]
        result.append(value)
    return result


def put(connection, table, key, value):
    physical = TABLE_NAMES.get(table, table)
    if table in PAYLOAD_TABLES:
        payload = json.dumps(value, default=str)
        if table == 'snapshots':
            connection.execute('''INSERT INTO snapshot_observations VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                (key,value['account']['id'],value.get('source_timestamp'),value['imported_at'],
                 value['source_hash'],value['fingerprint'],int(value.get('positions_complete',False)),
                 int(value.get('lots_complete',False)),int(value.get('cash_known',False)),
                 value.get('data_environment'),value.get('status','ACCEPTED'),payload))
        elif table == 'target_versions':
            connection.execute('INSERT INTO target_versions VALUES (?,?,?,?)',
                               (key,value['id'],value['version'],payload))
        else:
            connection.execute(f'INSERT INTO {physical} VALUES (?,?) ON CONFLICT(id) '
                               'DO UPDATE SET payload_json=excluded.payload_json', (key,payload))
        return
    fields = FIELDS[table]
    unknown = set(value) - set(fields) - {'lot_allocations'}
    if unknown:
        raise DomainError(f'Unsupported {table} fields: {", ".join(sorted(unknown))}')
    keys = list(fields)
    present = sum(1 << index for index, field in enumerate(keys) if field in value)
    cells = []
    for field in keys:
        cell = value.get(field)
        if field in JSON_FIELDS and cell is not None:
            cell = json.dumps(cell, default=str)
        elif field in BOOL_FIELDS and cell is not None:
            cell = int(cell)
        elif field in DECIMAL_FIELDS:
            cell = text_decimal(cell)
        cells.append(cell)
    columns = keys + ['present']
    update = ','.join(f'{field}=excluded.{field}' for field in columns if field != 'id')
    connection.execute(f'INSERT INTO {physical} ({",".join(columns)}) VALUES '
                       f'({",".join("?" for _ in columns)}) ON CONFLICT(id) DO UPDATE SET {update}',
                       (*cells,present))
    if table == 'activities':
        connection.execute('DELETE FROM activity_lot_allocations WHERE activity_id=?', (key,))
        for allocation in value.get('lot_allocations') or []:
            connection.execute('INSERT INTO activity_lot_allocations(activity_id,lot_id,quantity) '
                               'VALUES (?,?,?)', (key,allocation['lot_id'],text_decimal(allocation['quantity'])))
    if table == 'securities':
        connection.execute('DELETE FROM security_aliases WHERE security_id=?', (key,))
        for kind in ('ticker','cusip','isin','figi'):
            if value.get(kind):
                connection.execute('INSERT INTO security_aliases(security_id,kind,value,source) '
                                   'VALUES (?,?,?,?)', (key,kind,value[kind],value.get('source')))
        for alias in value.get('ticker_aliases') or []:
            if alias.get('source'):
                connection.execute('INSERT OR IGNORE INTO security_aliases(security_id,kind,value,source) '
                                   "VALUES (?,'ticker',?,?)", (key,alias['ticker'],alias['source']))


def status(path):
    connection = connect(path)
    try:
        from invest.backup import latest_verified
        receipt = latest_verified(path)
        return {'status': 'AVAILABLE', 'schema_version': SCHEMA_VERSION, 'issues': [],
                'writer_settings': {'foreign_keys': bool(connection.execute('PRAGMA foreign_keys').fetchone()[0]),
                    'journal_mode': connection.execute('PRAGMA journal_mode').fetchone()[0],
                    'synchronous': 'FULL' if connection.execute('PRAGMA synchronous').fetchone()[0] == 2 else 'UNKNOWN',
                    'busy_timeout': connection.execute('PRAGMA busy_timeout').fetchone()[0]},
                'latest_verified_backup': receipt}
    finally:
        connection.close()
