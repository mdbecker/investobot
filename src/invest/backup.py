"""Verified SQLite online backups and explicit, staged local restoration.

Verification is read-only. Archives contain ordinary files and a hash manifest;
no archive-controlled path is ever passed to tarfile extraction helpers.
"""

import contextlib
import fcntl
import hashlib
import json
import os
import shutil
import sqlite3
import tarfile
import tempfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from invest.models import DomainError

MANIFEST = 'manifest.json'
LEDGER = 'ledger.db'
MANIFEST_LIMIT = 16 * 1024 * 1024


def _issue(code, message, *ids):
    return {'code': code, 'severity': 'ERROR', 'affected_ids': list(ids),
            'blocks_calculation': True, 'blocks_proposal': True,
            'blocks_execution_review': True, 'message': message}


def _result(issues=(), **details):
    return {'status': 'BLOCKED' if issues else 'AVAILABLE', 'issues': list(issues),
            'coverage': {}, 'as_of': None, 'sources': [], 'manifest_ids': [],
            'assumptions': [], 'environment': 'LOCAL', **details}


def _safe_name(name):
    if (not isinstance(name, str) or not name or '\x00' in name or '\\' in name or ':' in name
            or name.startswith('/') or any(part in {'', '.', '..'} for part in name.split('/'))):
        raise DomainError(f'Unsafe archive or artifact path: {name}')
    if str(PurePosixPath(name)) != name:
        raise DomainError(f'Noncanonical archive or artifact path: {name}')
    return name


def _path(path, *, exists=False, file=False):
    selected = Path(path).absolute()
    for component in [selected, *selected.parents]:
        if component.is_symlink():
            raise DomainError(f'Symlink path is not permitted: {component}')
    if exists and not selected.exists():
        raise DomainError(f'File does not exist: {selected}')
    if selected.exists() and file and not selected.is_file():
        raise DomainError(f'Expected a regular file: {selected}')
    return selected


def _hash(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _fsync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _atomic_json(path, payload):
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.receipt-', delete=False) as stream:
        temporary = Path(stream.name)
        try:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(json.dumps(payload, sort_keys=True).encode())
            stream.flush()
            os.fsync(stream.fileno())
            os.replace(temporary, path)
            _fsync_directory(path.parent)
        finally:
            temporary.unlink(missing_ok=True)


def logical_fingerprint(connection):
    """Stream a deterministic logical dump; WAL/header layout is not provenance."""
    digest = hashlib.sha256()
    for statement in connection.iterdump():
        digest.update(statement.encode('utf-8'))
        digest.update(b'\n')
    return digest.hexdigest()


def _connect(path):
    from invest.db import connect

    return connect(path, readonly=True, initialize=False)


def _artifacts(connection):
    columns = {row[1] for row in connection.execute('PRAGMA table_info(dataset_artifacts)')}
    if not columns:
        return []
    path_column = 'relative_path' if 'relative_path' in columns else 'path'
    if path_column not in columns or 'sha256' not in columns:
        raise DomainError('Dataset artifact manifest lacks path or hash columns', 3)
    return list(connection.execute(f'SELECT {path_column}, sha256 FROM dataset_artifacts '
                                   f'WHERE {path_column} IS NOT NULL'))


def _check_connection(connection):
    from invest.db import validate_schema

    issues = []
    try:
        rows = [tuple(row) for row in connection.execute('PRAGMA integrity_check')]
        if rows != [('ok',)]:
            issues.append(_issue('SQLITE_INTEGRITY_FAILED', '; '.join(str(row[0]) for row in rows),
                                 LEDGER))
        violations = list(connection.execute('PRAGMA foreign_key_check'))
        if violations:
            issues.append(_issue('SQLITE_FOREIGN_KEY_FAILED',
                                 f'{len(violations)} foreign key violations', LEDGER))
        validate_schema(connection)
    except sqlite3.DatabaseError as error:
        issues.append(_issue('SQLITE_INTEGRITY_FAILED', str(error), LEDGER))
    except DomainError as error:
        issues.append(_issue('UNSUPPORTED_DEVELOPMENT_SCHEMA', str(error), LEDGER))
    return issues


def _check_database(path, artifact_root=None):
    issues = []
    connection = None
    try:
        path = _path(path, exists=True, file=True)
        connection = _connect(path)
        connection.execute('BEGIN')
        issues.extend(_check_connection(connection))
        if issues:
            return issues
        root = _path(artifact_root or path.parent, exists=True)
        for relative, expected in _artifacts(connection):
            try:
                _safe_name(relative)
                artifact = _path(root / relative, exists=True, file=True)
                if _hash(artifact) != expected:
                    issues.append(_issue('ARTIFACT_HASH_MISMATCH', 'Referenced artifact hash differs',
                                         relative))
            except (DomainError, OSError) as error:
                issues.append(_issue('ARTIFACT_UNAVAILABLE', str(error), str(relative)))
    except sqlite3.DatabaseError as error:
        issues.append(_issue('SQLITE_INTEGRITY_FAILED', str(error), str(path)))
    except (DomainError, OSError) as error:
        issues.append(_issue('DATABASE_UNAVAILABLE', str(error), str(path)))
    finally:
        if connection is not None:
            connection.close()
    return issues


def _stage_archive(archive_path, staging):
    """Validate each member and manifest before returning the staged database."""
    issues = []
    try:
        with tarfile.open(_path(archive_path, exists=True, file=True), 'r:gz') as archive:
            names = set()
            members = []
            for member in archive:
                try:
                    _safe_name(member.name)
                    if not member.isfile() or member.name in names or member.size < 0:
                        raise DomainError('Nonregular or duplicate archive member')
                    names.add(member.name)
                    members.append(member)
                except DomainError as error:
                    issues.append(_issue('UNSAFE_ARCHIVE_MEMBER', str(error), member.name))
            if issues:
                return issues, None
            metadata = next((member for member in members if member.name == MANIFEST), None)
            if metadata is None or metadata.size > MANIFEST_LIMIT:
                return [_issue('INVALID_BACKUP_MANIFEST', 'Missing or oversized manifest', MANIFEST)], None
            with archive.extractfile(metadata) as stream:
                manifest = json.load(stream)
            if not isinstance(manifest, dict) or not isinstance(manifest.get('files'), list):
                raise DomainError('Manifest files must be a list')
            declared = {}
            for record in manifest['files']:
                if not isinstance(record, dict):
                    raise DomainError('Manifest entries must be objects')
                name = _safe_name(record.get('path'))
                size, digest = record.get('size'), record.get('sha256')
                if (name == MANIFEST or name in declared or type(size) is not int or size < 0
                        or not isinstance(digest, str) or len(digest) != 64
                        or any(char not in '0123456789abcdef' for char in digest)):
                    raise DomainError(f'Invalid or duplicate manifest entry: {name}')
                declared[name] = record
            if names - {MANIFEST} != declared.keys():
                raise DomainError('Archive members do not match the declared manifest')
            if sum(record['size'] for record in declared.values()) > shutil.disk_usage(staging).free:
                raise DomainError('Insufficient staging space for declared backup')
            for member in members:
                if member.name == MANIFEST:
                    continue
                record = declared[member.name]
                if member.size != record['size']:
                    issues.append(_issue('ARTIFACT_SIZE_MISMATCH', 'Archive member size differs',
                                         member.name))
                    continue
                destination = staging / member.name
                destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                with archive.extractfile(member) as source, destination.open('xb') as target:
                    os.fchmod(target.fileno(), 0o600)
                    shutil.copyfileobj(source, target, length=1024 * 1024)
                    target.flush()
                    os.fsync(target.fileno())
                if _hash(destination) != record['sha256']:
                    issues.append(_issue('ARTIFACT_HASH_MISMATCH', 'Archive member hash differs',
                                         member.name))
            if LEDGER not in declared:
                issues.append(_issue('BACKUP_LEDGER_MISSING', 'Archive has no ledger.db', LEDGER))
            if not issues:
                issues.extend(_check_database(staging / LEDGER, artifact_root=staging))
            return issues, manifest
    except (DomainError, OSError, ValueError, tarfile.TarError, EOFError) as error:
        return [_issue('INVALID_BACKUP_ARCHIVE', str(error), str(archive_path))], None


def verify(path):
    """Check a ledger or archive without creating or modifying the selected ledger."""
    selected = Path(path)
    if selected.name.endswith(('.tar.gz', '.tgz')):
        with tempfile.TemporaryDirectory(prefix='investobot-verify-') as temporary:
            issues, manifest = _stage_archive(selected, Path(temporary))
        return _result(issues, archive=str(selected), manifest=manifest)
    return _result(_check_database(selected), database=str(selected))


def create(path, output, artifact_root=None):
    """Publish an owner-only archive using SQLite's consistent online backup API."""
    try:
        source = _path(path, exists=True, file=True)
        output = _path(output, file=True)
        if output == source or output.suffixes[-2:] != ['.tar', '.gz']:
            raise DomainError('Backup output must be a separate .tar.gz archive')
        output.parent.mkdir(parents=True, exist_ok=True)
        root = _path(artifact_root or source.parent, exists=True)
        with tempfile.TemporaryDirectory(dir=output.parent, prefix='.backup-stage-') as temporary:
            staging = Path(temporary)
            with contextlib.closing(_connect(source)) as origin:
                origin.execute('BEGIN')
                origin.execute('SELECT count(*) FROM sqlite_master').fetchone()
                problems = _check_connection(origin)
                if problems:
                    return _result(problems)
                with contextlib.closing(sqlite3.connect(staging / LEDGER)) as destination:
                    origin.backup(destination, pages=256, sleep=0.01)
                    fingerprint = logical_fingerprint(destination)
                files = [LEDGER]
                expected_hashes = {}
                for relative, expected in _artifacts(origin):
                    _safe_name(relative)
                    if relative in {LEDGER, MANIFEST}:
                        raise DomainError(f'Artifact path collides with reserved backup name: {relative}', 3)
                    if relative in expected_hashes and expected_hashes[relative] != expected:
                        raise DomainError(f'Conflicting artifact hashes: {relative}', 3)
                    expected_hashes[relative] = expected
                for relative, expected in expected_hashes.items():
                    original = _path(root / relative, exists=True, file=True)
                    if original == output:
                        raise DomainError('Backup output would replace a referenced artifact', 3)
                    target = staging / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with original.open('rb') as src, target.open('xb') as dst:
                        os.fchmod(dst.fileno(), 0o600)
                        shutil.copyfileobj(src, dst, length=1024 * 1024)
                        dst.flush()
                        os.fsync(dst.fileno())
                    if _hash(target) != expected:
                        return _result([_issue('ARTIFACT_HASH_MISMATCH',
                                               'Referenced artifact changed or has wrong hash', relative)])
                    files.append(relative)
            problems = _check_database(staging / LEDGER, artifact_root=staging)
            if problems:
                return _result(problems)
            manifest = {'version': 1, 'files': [
                {'path': relative, 'size': (staging / relative).stat().st_size,
                 'sha256': _hash(staging / relative)} for relative in sorted(files)]}
            (staging / MANIFEST).write_text(json.dumps(manifest, sort_keys=True))
            fd, name = tempfile.mkstemp(dir=output.parent, prefix='.backup-', suffix='.tar.gz')
            temporary_archive = Path(name)
            os.close(fd)
            try:
                with tarfile.open(temporary_archive, 'w:gz', format=tarfile.PAX_FORMAT) as archive:
                    for relative in [MANIFEST, *sorted(files)]:
                        info = archive.gettarinfo(staging / relative, arcname=relative)
                        info.mode = 0o600
                        info.uid = info.gid = 0
                        info.uname = info.gname = ''
                        with (staging / relative).open('rb') as stream:
                            archive.addfile(info, stream)
                checked = verify(temporary_archive)
                if checked['status'] != 'AVAILABLE':
                    return checked
                with temporary_archive.open('rb') as stream:
                    os.fsync(stream.fileno())
                os.replace(temporary_archive, output)
                _fsync_directory(output.parent)
            finally:
                temporary_archive.unlink(missing_ok=True)
            receipt = {'version': 1, 'source_path': str(source), 'archive': str(output),
                       'archive_sha256': _hash(output), 'database_fingerprint': fingerprint,
                       'verified_at': datetime.now(UTC).isoformat()}
            _atomic_json(source.with_name(source.name + '.backup-receipt.json'), receipt)
            return _result(archive=str(output), manifest=manifest, receipt=receipt)
    except sqlite3.DatabaseError as error:
        return _result([_issue('SQLITE_INTEGRITY_FAILED', str(error), str(path))])
    except (DomainError, OSError, ValueError, tarfile.TarError) as error:
        return _result([_issue('BACKUP_FAILED', str(error), str(path))])


def latest_verified(path):
    """Return a genuine receipt only while both archive and selected state match."""
    try:
        source = _path(path, exists=True, file=True)
        receipt_path = _path(source.with_name(source.name + '.backup-receipt.json'), exists=True,
                             file=True)
        if receipt_path.stat().st_mode & 0o077:
            return None
        receipt = json.loads(receipt_path.read_text())
        if (not isinstance(receipt, dict) or receipt.get('version') != 1
                or receipt.get('source_path') != str(source)):
            return None
        if _hash(_path(receipt['archive'], exists=True, file=True)) != receipt['archive_sha256']:
            return None
        with contextlib.closing(_connect(source)) as connection:
            connection.execute('BEGIN')
            if logical_fingerprint(connection) != receipt['database_fingerprint']:
                return None
        stamp = datetime.fromisoformat(receipt['verified_at'])
        if stamp.tzinfo is None:
            return None
        return {**receipt, 'age_seconds': max(0, (datetime.now(UTC) - stamp).total_seconds())}
    except (OSError, ValueError, KeyError, TypeError, DomainError, sqlite3.DatabaseError):
        return None


def restore(archive, path, dry_run=False, confirm=False):
    """Validate first; explicit confirmation replaces only the selected ledger."""
    selected = Path(path).absolute()
    try:
        _path(selected, file=True)
        parent = selected.parent
        if not parent.exists():
            if dry_run or not confirm:
                with tempfile.TemporaryDirectory(prefix='investobot-restore-preview-') as temporary:
                    problems, manifest = _stage_archive(archive, Path(temporary))
                return _result(problems, committed=False, manifest=manifest,
                               confirmation_required=True, database=str(selected))
            parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent, prefix='.restore-stage-') as temporary:
            staging = Path(temporary)
            problems, manifest = _stage_archive(archive, staging)
            if problems:
                return _result(problems, committed=False)
            if dry_run or not confirm:
                return _result(committed=False, confirmation_required=True, manifest=manifest,
                               database=str(selected))
            # Resolve every destination before even checkpointing the live ledger.
            reserved = {str(selected), str(selected) + '-wal', str(selected) + '-shm',
                        str(selected) + '.restore.lock', str(selected) + '.backup-receipt.json'}
            for record in manifest['files']:
                relative = record['path']
                if relative == LEDGER:
                    continue
                destination = _path(parent / relative, file=True)
                if str(destination) in reserved:
                    raise DomainError('Artifact destination collides with selected ledger files')
                if destination.exists() and _hash(destination) != record['sha256']:
                    return _result([_issue('RESTORE_ARTIFACT_CONFLICT',
                                           'Existing immutable artifact has different bytes', relative)],
                                   committed=False)
            for suffix in ['-wal', '-shm']:
                _path(str(selected) + suffix, file=True)
            # Never reuse a live WAL against replacement pages. The lock/checkpoint
            # guards active writers/read transactions; operators must stop idle clients.
            lock_path = _path(parent / (selected.name + '.restore.lock'), file=True)
            with lock_path.open('a+b') as lock:
                os.fchmod(lock.fileno(), 0o600)
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    return _result([_issue('RESTORE_WRITERS_ACTIVE', 'Another restore owns the lock',
                                           str(selected))], committed=False)
                if selected.exists():
                    connection = sqlite3.connect(selected, timeout=0.1)
                    try:
                        connection.execute('PRAGMA busy_timeout=100')
                        if connection.execute('PRAGMA journal_mode').fetchone()[0] == 'wal':
                            checkpoint = connection.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()
                            if checkpoint[0]:
                                return _result([_issue('RESTORE_WRITERS_ACTIVE',
                                                       'Live WAL readers or writers prevent replacement',
                                                       str(selected))], committed=False)
                        connection.execute('PRAGMA locking_mode=EXCLUSIVE')
                        connection.execute('BEGIN EXCLUSIVE')
                        connection.commit()
                    except sqlite3.OperationalError as error:
                        return _result([_issue('RESTORE_WRITERS_ACTIVE', str(error), str(selected))],
                                       committed=False)
                    finally:
                        connection.close()
                for record in manifest['files']:
                    relative = record['path']
                    if relative == LEDGER:
                        continue
                    destination = parent / relative
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    if not destination.exists():
                        os.replace(staging / relative, destination)
                        _fsync_directory(destination.parent)
                for suffix in ['-wal', '-shm']:
                    sidecar = _path(str(selected) + suffix, file=True)
                    sidecar.unlink(missing_ok=True)
                os.chmod(staging / LEDGER, 0o600)
                os.replace(staging / LEDGER, selected)
                _fsync_directory(parent)
                return _result(committed=True, database=str(selected), manifest=manifest)
    except (DomainError, OSError, sqlite3.DatabaseError) as error:
        return _result([_issue('RESTORE_FAILED', str(error), str(selected))], committed=False)
