# Canonical ledger
SQLite schema version 1 stores accounts, UUID securities with aliases, current positions, lots, cash balances, activity history, immutable normalized snapshots, market/fund caches and proposal records. Decimal values are serialized as strings; dates use ISO 8601. Explicit snapshot application supersedes current state, preserving activities and audit snapshots. Import does not write. Missing lots never become fabricated basis.

Snapshot application rejects duplicate positions, nonfinite/negative values, and lot balances exceeding their positions before any write. Synthetic account aliases are used as local identifiers.

Security UUIDs persist through ticker changes when explicit CUSIP/ISIN/FIGI aliases identify the same security. Conflicting aliases are rejected rather than merged. A ticker is only a provisional resolution alias, never the primary key. Known confirmed purchases increase known position basis; unknown pre-existing basis stays unknown. Manual sales invalidate aggregate position basis pending authoritative broker reconciliation.

`invest schema` emits the normalized snapshot JSON Schema and common output/error contract. Successful analysis commands return named domain metrics plus warnings/provenance; no unaudited estimate replaces missing fields. Decimal monetary values/quantities and fractional holdings weights use JSON strings; historical risk statistics/correlations are numeric. Tax results explicitly mark insufficient data. Dates are ISO8601.
