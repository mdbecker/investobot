"""One exact canonical resolver for accepted strong IDs and reviewed ticker aliases."""

from invest.models import DomainError


def resolve(securities, identifier):
    matches = []
    for security in securities:
        identities = {security.get(field) for field in ('id', 'ticker', 'cusip', 'isin', 'figi')}
        identities.update(alias['ticker'] for alias in security.get('ticker_aliases') or []
                          if isinstance(alias, dict) and alias.get('ticker') and alias.get('source'))
        if identifier is not None and identifier in identities:
            matches.append(security)
    if len(matches) != 1:
        raise DomainError('Security is unknown or ambiguous', 3)
    return matches[0]
