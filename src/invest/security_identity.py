"""One exact canonical resolver for accepted strong IDs and reviewed ticker aliases."""

from invest.models import DomainError


def _matches(security, identifier):
    identities = {security.get(field) for field in ('id', 'ticker', 'cusip', 'isin', 'figi')}
    identities.update(alias['ticker'] for alias in security.get('ticker_aliases') or []
                      if isinstance(alias, dict) and alias.get('ticker') and alias.get('source'))
    return identifier is not None and identifier in identities


def resolve(securities, identifier):
    matches = [security for security in securities if _matches(security, identifier)]
    if len(matches) != 1:
        raise DomainError('Security is unknown or ambiguous', 3)
    return matches[0]


def resolve_observation(securities, position, held):
    """Strong evidence takes precedence; reviewed aliases never override conflicts."""
    supplied = {key: position[key].strip().upper() for key in ('cusip', 'isin', 'figi')
                if position.get(key)}
    aliases = [row for row in securities if _matches(row, position['security'])]
    if any(any(row.get(key) and row[key] != value for key, value in supplied.items())
           for row in aliases if row['id'] in held or row.get('ticker_aliases')):
        raise DomainError('Reviewed security alias has conflicting strong identity', 3)
    existing = [row for row in securities if any(row.get(key) == value for key, value in supplied.items())]
    if not existing:
        existing = [row for row in aliases if not any(
            row.get(key) and row[key] != value for key, value in supplied.items())]
    if len(existing) > 1 or (existing and any(existing[0].get(key) and existing[0][key] != value
                                            for key, value in supplied.items())):
        raise DomainError('Security aliases conflict; resolve identity explicitly', 3)
    return (existing[0] if existing else None), supplied
