"""Transactional future upgrades; development schemas are never migrated."""

import hashlib
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from invest.models import DomainError

_ALLOWED_FIELDS = {'id', 'sql', 'checksum', 'destructive'}
_ALLOWED_SQL = {'CREATE', 'ALTER', 'DROP', 'INSERT', 'UPDATE', 'DELETE', 'REPLACE', 'SELECT'}
_PREFIX = re.compile(r'^(?:\s|--[^\n]*(?:\n|$)|/\*.*?\*/)*([A-Za-z]+)', re.DOTALL)


def _outcome(status, *, code=None, message=None, applied=None):
    issues = []
    if code:
        issues.append({'code': code, 'severity': 'ERROR', 'affected_ids': ['database'],
                       'blocks_calculation': False, 'blocks_proposal': True,
                       'blocks_execution_review': True, 'message': message})
    return {'status': status, 'issues': issues, 'coverage': {}, 'as_of': None,
            'sources': [], 'manifest_ids': [], 'assumptions': [], 'environment': None,
            'applied_migrations': applied or []}


def _blocked(code, message):
    return _outcome('BLOCKED', code=code, message=message)


def _statements(sql):
    """SQLite's parser recognizes trigger bodies; no executescript implicit commits."""
    pending = ''
    statements = []
    for char in sql:
        pending += char
        if char == ';' and sqlite3.complete_statement(pending):
            statements.append(pending)
            pending = ''
    if pending.strip():
        # A final statement need not contain a semicolon. A comment-only tail is harmless.
        if _PREFIX.match(pending):
            candidate = pending + ';'
            if not sqlite3.complete_statement(candidate):
                raise ValueError('Incomplete migration SQL')
            statements.append(candidate)
    for statement in statements:
        match = _PREFIX.match(statement)
        if not match or match.group(1).upper() not in _ALLOWED_SQL:
            raise ValueError('Migration SQL may not manage transactions, pragmas or external files')
    if not statements:
        raise ValueError('Migration SQL must contain a statement')
    return statements


def _validated(migrations):
    if not isinstance(migrations, list):
        raise ValueError('Migrations must be an ordered list')
    result, seen = [], set()
    for migration in migrations:
        if not isinstance(migration, dict) or set(migration) != _ALLOWED_FIELDS:
            raise ValueError('Every migration requires only id, sql, checksum and destructive')
        identifier, sql, checksum = (migration[key] for key in ('id', 'sql', 'checksum'))
        if not isinstance(identifier, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', identifier):
            raise ValueError('Migration IDs must be explicit safe identifiers')
        if identifier in seen:
            raise ValueError('Migration IDs must be unique')
        if not isinstance(sql, str) or not sql.strip() or len(sql.encode()) > 1024 * 1024:
            raise ValueError('Migration SQL must contain at most one MiB of text')
        if type(migration['destructive']) is not bool:
            raise ValueError('Migration destructive must be a JSON boolean')
        actual = hashlib.sha256(sql.encode('utf-8')).hexdigest()
        if not isinstance(checksum, str) or checksum != actual:
            raise ValueError('Migration checksum does not match its exact UTF-8 SQL bytes')
        result.append({**migration, 'statements': _statements(sql)})
        seen.add(identifier)
    identifiers = [m['id'] for m in result]
    if identifiers != sorted(identifiers):
        raise ValueError('Migration IDs must be supplied in ascending immutable order')
    return result


def _history(connection):
    return connection.execute(
        'SELECT id, checksum FROM schema_migrations ORDER BY id').fetchall()


def _pending(migrations, history):
    recorded = dict(history)
    pending = []
    for migration in migrations:
        identifier = migration['id']
        if identifier in recorded:
            if recorded[identifier] != migration['checksum']:
                raise ValueError('An applied migration checksum cannot change')
        else:
            if history and identifier <= history[-1][0]:
                raise ValueError('New migrations cannot precede an already applied migration')
            pending.append(migration)
    return pending


def migrate(path, migrations=None):
    """Apply explicitly supplied future upgrades after a verified current backup.

    No registered future upgrade ships yet. Empty input checks the existing schema
    and returns a no-op. SQL and applied checksums are immutable, and user_version
    is never inferred from a migration's opaque identifier.
    """
    from invest import db

    path = Path(path).absolute()
    if not path.is_file() or path.is_symlink():
        return _blocked('LEDGER_NOT_FOUND', 'Select an existing regular local ledger')
    try:
        supplied = _validated([] if migrations is None else migrations)
    except ValueError as exc:
        return _blocked('INVALID_MIGRATION_INPUT', str(exc))
    # Read-only preflight must precede every writer connection and its WAL settings.
    reader = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
    try:
        try:
            db.validate_schema(reader)
        except DomainError:
            return _blocked('UNSUPPORTED_DEVELOPMENT_SCHEMA',
                            'Only the supported new-design schema may receive future upgrades')
        history = _history(reader)
        try:
            pending = _pending(supplied, history)
        except ValueError as exc:
            return _blocked('MIGRATION_HISTORY_CONFLICT', str(exc))
    except sqlite3.DatabaseError:
        return _blocked('INVALID_LEDGER_SCHEMA', 'Migration history is missing or unreadable')
    finally:
        reader.close()
    if not pending:
        return _outcome('AVAILABLE')

    from invest import backup

    receipt = backup.latest_verified(path)
    if receipt is None:
        return _blocked('VERIFIED_BACKUP_REQUIRED',
                        'Create a verified backup of the current selected ledger before upgrading')
    try:
        connection = db.connect(path, initialize=False)
    except (DomainError, sqlite3.DatabaseError, OSError):
        return _blocked('DATABASE_CHANGED_DURING_PREFLIGHT',
                        'The selected ledger became unavailable or changed during preflight')
    try:
        # Rebuilds may temporarily remove referenced tables. Check all FKs before
        # committing; foreign_keys is re-enabled on this connection afterward.
        connection.execute('PRAGMA foreign_keys=OFF')
        connection.execute('BEGIN IMMEDIATE')
        try:
            db.validate_schema(connection)
        except DomainError:
            connection.rollback()
            return _blocked('UNSUPPORTED_DEVELOPMENT_SCHEMA', 'The selected schema changed during preflight')
        if backup.logical_fingerprint(connection) != receipt['database_fingerprint']:
            connection.rollback()
            return _blocked('VERIFIED_BACKUP_REQUIRED', 'The accepted ledger changed after its verified backup')
        try:
            locked_pending = _pending(supplied, _history(connection))
        except ValueError as exc:
            connection.rollback()
            return _blocked('MIGRATION_HISTORY_CONFLICT', str(exc))
        applied = []
        original_history = dict(_history(connection))
        for migration in locked_pending:
            for statement in migration['statements']:
                connection.execute(statement)
            connection.execute('INSERT INTO schema_migrations(id, checksum, applied_at) VALUES (?, ?, ?)',
                (migration['id'], migration['checksum'], datetime.now(timezone.utc).isoformat()))
            applied.append(migration['id'])
        current_history = dict(_history(connection))
        expected_history = {**original_history,
                            **{item['id']: item['checksum'] for item in locked_pending}}
        if current_history != expected_history:
            raise sqlite3.IntegrityError('Migration altered immutable applied history')
        if connection.execute('PRAGMA foreign_key_check').fetchone() is not None:
            raise sqlite3.IntegrityError('Migration violates foreign keys')
        integrity = connection.execute('PRAGMA integrity_check').fetchall()
        if len(integrity) != 1 or integrity[0][0] != 'ok':
            raise sqlite3.IntegrityError('Migration violates SQLite integrity')
        connection.commit()
        return _outcome('AVAILABLE', applied=applied)
    except sqlite3.DatabaseError:
        connection.rollback()
        return _blocked('MIGRATION_FAILED', 'Upgrade rolled back; inspect the supplied SQL and ledger constraints')
    finally:
        connection.execute('PRAGMA foreign_keys=ON')
        connection.close()
