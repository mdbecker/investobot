"""Explicit managed staging cleanup serialized against artifact publication."""

import contextlib
import fcntl
import os
from pathlib import Path

from invest.models import DomainError


def safe_root(root):
    selected = Path(root).absolute()
    if any(component.is_symlink() for component in [selected, *selected.parents]):
        raise DomainError('Artifact cleanup rejects symlink paths', 3)
    return selected


@contextlib.contextmanager
def publication_lock(root, *, exclusive=False, create=True):
    root = safe_root(root)
    lock = root / '.artifacts.lock'
    if lock.is_symlink():
        raise DomainError('Artifact publication rejects symlink lock', 3)
    if not create and not lock.exists():
        yield
        return
    if create:
        root.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(lock, os.O_NOFOLLOW | (os.O_RDWR | os.O_CREAT if create else os.O_RDONLY), 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        yield
    finally:
        os.close(descriptor)


def cleanup(ledger, root, *, confirm=False):
    root = safe_root(root)
    if not root.is_dir():
        raise DomainError('Artifact root must be an existing directory')
    with publication_lock(root, exclusive=confirm, create=confirm):
        referenced = {row[0] for row in ledger.connection.execute(
            'SELECT relative_path FROM dataset_artifacts WHERE relative_path IS NOT NULL')}
        candidates = []
        for path in sorted(root.rglob('.artifact-*')):
            if path.is_symlink() or any(component.is_symlink() for component in path.parents):
                raise DomainError('Artifact cleanup rejects symlink staging', 3)
            if not path.is_file():
                raise DomainError('Managed artifact staging must be a regular file', 3)
            relative = str(path.relative_to(root))
            if relative not in referenced:
                candidates.append((path, relative))
        if confirm:
            for path, _ in candidates:
                path.unlink()
            for directory in {path.parent for path, _ in candidates}:
                descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
    return {'status': 'AVAILABLE' if confirm else 'PREVIEW', 'committed': bool(confirm),
            'removed' if confirm else 'candidates': [relative for _, relative in candidates],
            'issues': [], 'canonical_changed': False,
            'scope': 'unreferenced managed .artifact-* staging only'}
