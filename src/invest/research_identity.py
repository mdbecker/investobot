"""Research may reference sourced canonical identities, never create them."""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

from invest.models import DomainError


@contextmanager
def read_ledger(path):
    """Read existing research without creating a selected database on disk."""
    if Path(path).exists():
        connection = sqlite3.connect(Path(path).absolute().as_uri() + '?mode=ro', uri=True)
        try:
            if connection.execute('PRAGMA user_version').fetchone()[0] != 5:
                raise DomainError('Incompatible database schema; select a schema 5 database', 3)
            yield SimpleNamespace(connection=connection)
        finally:
            connection.close()
    else:
        from invest.ledger import Ledger

        db = Ledger(':memory:')
        try:
            yield db
        finally:
            db.connection.close()


def verify_company(ledger, company):
    security_id = company.get('security_id')
    if not security_id:
        return
    row = ledger.connection.execute('SELECT data FROM securities WHERE id=?',
                                    (security_id,)).fetchone()
    if row is None:
        raise DomainError('Research references an unknown canonical security ID', 3)
    security = json.loads(row[0])
    ticker = company.get('ticker')
    accepted = {security.get('ticker')}
    accepted.update(alias['ticker'] for alias in security.get('ticker_aliases') or []
                    if isinstance(alias, dict) and alias.get('source'))
    if ticker and ticker not in accepted:
        raise DomainError('Research ticker contradicts the canonical security identity', 3)
    if company.get('cik') and security.get('cik') and company['cik'] != security['cik']:
        raise DomainError('Research CIK contradicts the canonical security identity', 3)
