"""Stable exact financial fingerprints, independent of collection order."""

import hashlib
import json
from decimal import Decimal

from invest.models import DomainError, decimal


def state_hash(state):
    """Canonical financial fingerprint, independent of incidental collection order."""
    numeric_fields = {'quantity', 'remaining_quantity', 'price', 'market_value', 'cost_basis',
                      'amount', 'fee', 'execution_price', 'gross_amount', 'net_amount'}
    def exact_decimal(value):
        text = format(value, 'f')
        return (text.rstrip('0').rstrip('.') if '.' in text else text) if value else '0'

    def canonical(value, field=None):
        if isinstance(value, dict):
            return {k: canonical(v, k) for k, v in sorted(value.items())}
        if isinstance(value, list):
            items = [canonical(v) for v in value]
            return sorted(items, key=lambda v: json.dumps(v, sort_keys=True, default=str))
        if isinstance(value, Decimal):
            return exact_decimal(value)
        if isinstance(value, str) and field in numeric_fields:
            try:
                return exact_decimal(decimal(value))
            except (ValueError, DomainError):
                return value
        return value
    return hashlib.sha256(json.dumps(canonical(state), sort_keys=True, default=str).encode()).hexdigest()


