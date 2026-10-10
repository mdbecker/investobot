"""Research may reference sourced canonical identities, never create them."""

import json

from invest.models import DomainError


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
