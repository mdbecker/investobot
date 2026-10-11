# Local architecture

One Python application exposes a JSON CLI and a thin loopback dashboard. There
is no ORM, service framework, hosted vector database or brokerage integration.
Financial domain functions drive both interfaces.

SQLite holds normalized accounts, identities, observations, current balances,
lots, immutable confirmed events, policies, plans and research provenance.
Exact financial decimals are normalized text. Foreign keys, WAL, synchronous
FULL and a five-second busy timeout protect related transactional writes.
Observation evidence is distinct from authoritative balances and execution facts.

The persistence-facing ledger delegates exact activity accounting, read-only
portfolio summaries and canonical security lookup to cohesive modules. Stable
financial fingerprints are separate from compact saved-plan retrieval. Preserved
scenario proposal generation and approved-policy planning share authoritative
simulation primitives; they are not generic repository or solver abstractions.

Checksum-identified schema 1 initializes only empty ledgers. Existing incompatible
development ledgers are rejected without modification. Future migrations require
a verified pre-migration backup and transactional checksum tracking. Shared
connection locks exclude restore; restore stages and validates before explicit
confirmed publication. See [operations](operations.md).

Large immutable Parquet artifacts have SQLite manifests and content hashes.
Ephemeral DuckDB scans consistent exports/artifacts and never writes financial
tables. Canonical corpus text and vectors live in SQLite; FTS5 and sqlite-vec
indexes are rebuildable. Extensions are checksum-pinned and baked into Docker,
with no runtime download. Prompts are copied text under `/data/prompts`.

Docker contains dependencies and all execution/testing. The host stores source,
Git history and explicitly mounted local data. Host publication is loopback only.
The dashboard's same-origin checks are local write safeguards, not authentication.
