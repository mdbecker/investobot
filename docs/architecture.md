# Local architecture

The independently supplied host AI agent reads tracked/installed skills, retrieves
permitted sources and requests human approval. A single containerized Python app
exposes a deterministic JSON CLI and a thin read-only dashboard. The host bridge
`./scripts/invest` forwards directly to disposable Compose `app` commands. There
is no agent container, ORM, service framework, scheduler, RPC layer or database
service. Dependencies and pinned native extensions live in `/opt/venv` and the
image; no project runtime is installed on the host.

Compose binds the project to `/app` and host `local-data/state` to `/data`.
SQLite `/data/portfolio.db`, sidecars, immutable artifacts and receipts share that
stable mount. Host `input/`, `work/` and `agent-notes/` hold private supplied files,
candidates and ordinary context. Git/image builds exclude `local-data/`.
Canonical instructions are tracked `skills/`; project-local installation copies
are optional host-readable resources. There is no separate prompt library.

SQLite alone owns writable financial truth: normalized accounts, identities,
observations, balances, lots, confirmed events, policies, plans and research.
Financial decimals are exact normalized text. Foreign keys, WAL, synchronous FULL
and a five-second busy timeout protect related transactional writes. Observation
evidence is separate from accepted balances and execution facts. Schema 1 is
checksum-identified and initializes only empty ledgers; incompatible development
ledgers are rejected unchanged. Future transactional migrations require verified
pre-migration backups. Shared connection locks exclude restore.

Large immutable Parquet artifacts carry SQLite manifests/hashes. Ephemeral
DuckDB scans consistent exports; it never writes financial tables. Canonical
corpus chunks/vectors live in SQLite; FTS5/sqlite-vec indexes are rebuildable.
Native extensions are checksum-pinned and baked in, without runtime downloads.

Shared domain calculations drive the CLI and viewer. Every dashboard GET uses
query-only application reads, closes handles and reads persisted observations;
no provider/cache refresh or command dispatch occurs. POST returns 405 before
body/data access. Numeric fund coverage and verified evidence completeness are
separate, preserving known exposure and unknown residual. Backtest lists project
compact saved metrics; detail and comparison use immutable stored runs.
Host publication is loopback only. See [viewer](inspection.md),
[operations](operations.md) and [data contracts](data-contracts.md).
