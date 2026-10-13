# Future schema upgrades

Fresh host-backed storage initializes schema 1 through the existing application.
No schema upgrade is required for setup. The schema foundation checksum and
version are validated independently.

`invest db migrate` currently has no future upgrades to apply. It validates the
selected existing schema and returns an available no-op. A missing ledger is
reported as blocked; migration is not a database initialization command.

Future releases supply an ordered migration registry containing a stable ID,
exact SQL, its SHA-256 checksum and an explicit destructive flag. IDs use ascending
order, conventionally zero-padded numbers such as `002`. Applied checksums cannot
change, duplicate IDs and reordered upgrades are rejected, and repeating an
already applied upgrade is a no-op. The runner does not infer `user_version` from
an identifier; a future schema release must explicitly register its supported
version and schema changes.

Every actual upgrade requires a previously created, verified backup of the current
selected ledger. Run `invest db backup --output /safe/local/location/archive.tar.gz`
first, then keep an encrypted off-device copy using your existing backup tooling.
Backup creation records an owner-only receipt beside the selected ledger. Its
archive hash, ledger identity and logical database fingerprint must still match.
A missing, altered or stale receipt blocks the upgrade without opening a writer.
An unexecuted proposal or old backup cannot authorize replacement of current data.

All SQL and migration history inserts share one transaction. The runner uses
SQLite statement parsing, including trigger bodies, rather than `executescript`,
which can implicitly commit. Migration SQL cannot issue transaction controls,
connection pragmas or attach external databases. Table rebuilds temporarily disable
foreign-key enforcement on the migration connection, then run foreign-key and
integrity checks before committing. Failure rolls back the entire upgrade. The
runner takes a write lock and rechecks the backup fingerprint before changing
anything, protecting against accepted activity between backup and migration.

Use only disposable synthetic ledgers for upgrade testing. Inspect the reported
issue codes before retrying; never reset a private ledger or bypass the backup
receipt to make an upgrade proceed.
