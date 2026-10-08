# Canonical ledger
SQLite schema version 1 stores accounts, UUID securities with aliases, current positions, lots, cash balances, activity history, immutable normalized snapshots, market/fund caches and proposal records. Decimal values are serialized as strings; dates use ISO 8601. Explicit snapshot application supersedes current state, preserving activities and audit snapshots. Import does not write. Missing lots never become fabricated basis.

Snapshot application rejects duplicate positions, nonfinite/negative values, and lot balances exceeding their positions before any write. Synthetic account aliases are used as local identifiers.
