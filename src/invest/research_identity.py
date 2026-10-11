"""Research may reference sourced canonical identities, never create them."""

from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

from invest.models import DomainError


def same_research_company(first, second):
    """Shared identifiers must agree; names are fallback only without strong IDs."""
    keys = ('cik', 'security_id')
    if any(first.get(k) and second.get(k) and first[k] != second[k] for k in keys):
        return False
    if any(first.get(k) and second.get(k) and first[k] == second[k] for k in keys):
        return True
    if any(item.get(k) for item in (first, second) for k in keys):
        return False
    return bool(first.get('ticker') and second.get('ticker') and
                first['ticker'].casefold() == second['ticker'].casefold() and
                ' '.join(first['company_name'].split()).casefold() ==
                ' '.join(second['company_name'].split()).casefold())


@contextmanager
def read_ledger(path):
    """Read existing research without creating a selected database on disk."""
    if Path(path).exists():
        from invest.db import connect
        connection = connect(path, readonly=True)
        try:
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
    from invest.db import rows
    security = next(iter(rows(ledger.connection, 'securities', security_id)), None)
    if security is None:
        raise DomainError('Research references an unknown canonical security ID', 3)
    ticker = company.get('ticker')
    accepted = {security.get('ticker')}
    accepted.update(alias['ticker'] for alias in security.get('ticker_aliases') or []
                    if isinstance(alias, dict) and alias.get('source'))
    if ticker and ticker not in accepted:
        raise DomainError('Research ticker contradicts the canonical security identity', 3)
    if company.get('cik') and security.get('cik') and company['cik'] != security['cik']:
        raise DomainError('Research CIK contradicts the canonical security identity', 3)
