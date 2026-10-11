# Immutable public datasets

SQLite owns accepted dataset metadata and snapshot manifests. A snapshot pins
artifact hashes, dates, source coverage and REAL or SYNTHETIC provenance. Reading
or verifying a snapshot does not accept it, refresh quotes or change holdings.
`snapshot(..., confirm=True)` explicitly accepts a verified manifest atomically;
repeating identical acceptance is a no-op. Changed content cannot reuse an ID.

Artifacts can contain small inline observations or reference immutable Parquet
files. Financial Parquet columns must use exact decimal or text storage; floating
point financial inputs are rejected rather than silently rounded. Identifiers
remain text, including leading zeros. Each accepted artifact needs an explicit
provider and observation timestamp. Source publication/effective dates and
retrieval dates are separate fields. Missing source facts remain missing.

`publish_artifact` copies a source whose hash and declared size match its manifest
into the configured artifact root. Confirmation publishes owner-only bytes
atomically without overwriting an existing different artifact, then accepts the
SQLite manifest. A failed database acceptance may leave an unreferenced immutable
file; it does not leave a partially accepted snapshot. Paths must stay inside the
root and cannot contain traversal or symlinks. The default root is the ledger's
directory; backups include accepted referenced files relative to that root.

`verify_snapshot` checks every referenced hash and declared size.
`read_snapshot` verifies before and after reading, returns stable ordered rows and
a source fingerprint, and reports the exact affected path when verification
fails. `list_snapshots` returns compact metadata. An accepted manifest ID can be
passed to verification or reading instead of the original manifest object.

## Historical selection

`select_vintage` requires the requested security and an effective date plus an
observation date known by the requested cutoff. Future publications never fill
missing historical holdings. A date-only observation is not assumed to precede
a precise timestamp on the same day. Eligible evidence from mixed environments
blocks selection; explicitly pin an artifact to disambiguate. Holdings older
than the configurable age policy retain their rows with a typed stale issue.
Cache TTLs govern refresh opportunities and never establish historical coverage.
Unadjusted close prices cannot establish dividend-adjusted total returns.

## Offline analytical runtime

DuckDB connections are in-memory and temporary. `analytical_connection` attaches
a consistent temporary SQLite export read-only and creates views over pinned
Parquet batches. It never attaches the authoritative ledger to DuckDB. Consumers
must use fixed domain SQL and preserve exact SQLite decimal strings; casting to a
bounded analytical decimal requires an explicit precision check. The generic
connection does not provide financial aggregation or arbitrary user SQL.

The Docker build pins DuckDB, sqlite-vec and the SQLite scanner extension.
`INVEST_ANALYTICS_RUNTIME` selects the build-produced binary manifest. Runtime
loading verifies binary hashes; automatic extension installation and autoloading
are disabled. `capabilities()` checks actual offline loading and reports missing
or mismatched facilities. It does not download or repair them. Rebuild the Docker
image when changing versions or platforms.

FMP is the planned sole market-data provider. Offline synthetic acceptance does
not verify live entitlement, source accuracy or license permission. A human must
validate account entitlement and permitted use before introducing REAL data.
No credentials or private ledger are required for synthetic tests. Large public
datasets belong in immutable Parquet partitions; there is no persistent DuckDB
database. These readers do not implement provider acquisition or refresh.

## Market source dates and return coverage

Market responses distinguish `source_timestamp`/`data_as_of` from
`retrieval_timestamp`/`retrieved_at`. Cache retrieval never establishes current
source data. Quote cache TTL remains 900 seconds; history and holdings retain
their separate day TTL. Typed source-date status and coverage disclose unknown,
future or stale observations independently of cached content availability.
Holdings preserve each constituent's supplied source date; incomplete date
coverage cannot claim complete decision freshness. Decision holdings freshness
uses the 120-day default, and quote freshness uses the 900-second limit.

Historical rows without dividend-adjusted prices return
`MISSING_DIVIDEND_ADJUSTED_PRICE`; unadjusted close is never substituted. A response
with no supported adjusted observations is unavailable, and mixed supported and
unsupported rows retain explicit partial coverage. Potential missing sessions are
reported as unverified coverage: a weekday heuristic is not an exchange calendar.
Provider-adjusted closes remain identified as provider evidence; they do not
establish actual account performance or verified complete backtest history.

Fixture data is labeled SYNTHETIC and live-provider data REAL. These market reads
may update their dedicated caches, while simulations use read-only clients and
suppress cache writes. Refresh never updates accepted account quantities or
canonical valuation marks. Live FMP entitlement and source truth remain separately
unverified until human review; offline tests do not contact a provider.
