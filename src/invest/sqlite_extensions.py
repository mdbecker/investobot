"""Load only the verified vector binary baked into the selected Docker runtime."""

import hashlib
import json
import os
import re
from pathlib import Path

from invest.models import DomainError


def load_vector(connection):
    runtime_path = os.environ.get('INVEST_ANALYTICS_RUNTIME')
    if not runtime_path:
        raise DomainError('Pinned SQLite vector runtime manifest unavailable', 2)
    try:
        record = json.loads(Path(runtime_path).read_text())['sqlite_vec']
        binary = Path(record['path'])
        if (record['version'] != '0.1.6' or not binary.is_file() or
                hashlib.sha256(binary.read_bytes()).hexdigest() != record['sha256']):
            raise DomainError('Pinned SQLite vector binary verification failed', 2)
    except (OSError, KeyError, ValueError) as error:
        raise DomainError('Pinned SQLite vector manifest is invalid', 2) from error
    try:
        connection.enable_load_extension(True)
        connection.load_extension(str(binary))
    finally:
        connection.enable_load_extension(False)
    if connection.execute('SELECT vec_version()').fetchone()[0] != 'v0.1.6':
        raise DomainError('Loaded SQLite vector extension version differs from pin', 2)


def load_required(connection):
    """Ordinary ledgers need no extension; vector-bearing recovery needs vec0."""
    definitions = connection.execute("SELECT sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL")
    if any(re.search(r'\bUSING\s+vec0\b', row[0], re.IGNORECASE) for row in definitions):
        load_vector(connection)
