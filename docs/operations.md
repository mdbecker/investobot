# Local recovery operations

Use the Docker runtime and the selected ledger only. Do not copy a live SQLite
`.db`, `-wal` or `-shm` file as a backup. Keep the ledger outside cloud-sync and
network folders. These commands do not access a brokerage or place trades.

```sh
docker compose run --rm app invest db status
docker compose run --rm app invest db backup --output /data/backups/ledger.tar.gz
docker compose run --rm app invest db verify /data/backups/ledger.tar.gz
docker compose run --rm app invest db restore /data/backups/ledger.tar.gz --dry-run
```

Backup uses SQLite's online backup API, so committed observations and activities
form one consistent snapshot while normal readers and writers run. The archive
contains `ledger.db`, every referenced immutable dataset artifact and a manifest
with each file's size and SHA-256. It verifies SQLite integrity, foreign keys and
artifact hashes before publishing an owner-only (`0600`) archive atomically.
Search indexes within SQLite travel with that snapshot; they are derived and may
be rebuilt from canonical stored chunks and vectors.

After each accepted broker import or confirmed activity, verify the resulting
backup. Keep an encrypted off-device copy using your existing encrypted-backup
tooling. Investobot does not add a separate encryption service. A laptop scheduler
can invoke the backup command when the runtime is available; Investobot does not
start a background scheduler.

## Restore an explicitly selected ledger

Stop the dashboard and every process using the selected ledger before replacement.
Read-only preview verifies a separate staging directory and leaves the current
ledger unchanged. Review its manifest, then run the explicit confirmation:

```sh
docker compose stop app
docker compose run --rm app invest db restore /data/backups/ledger.tar.gz --confirm
docker compose run --rm app invest db verify /data/portfolio.db
```

Restore rejects traversal, symlinks, hard links, devices, duplicate members and
unlisted files. It rejects hash mismatches and conflicting existing immutable
artifacts. Active WAL readers or writers block replacement; an idle client must
also be stopped because it can retain an old file handle. Restore removes only
the selected ledger's SQLite sidecars after the writer guard and validation pass.
It preserves prompt overrides and unrelated files. Immutable artifacts copied
before the final ledger replacement are harmless orphan files if replacement
cannot finish.

Do not reset a private ledger to work around a schema error. Development schemas
are unsupported and remain untouched. Future migrations need a verified backup
matching the selected database's current logical state. Backup publishes an
owner-only receipt beside the database; verification and restore previews never
create receipts. Missing, tampered or stale receipts cannot authorize a migration.
Make another verified backup after a restore or new accepted financial/research
change before requesting a future schema upgrade.

## Missing inputs and operational limits

The release remains a development preview until reviewed, safely redacted broker
HTML and actual market-provider entitlements have passed the separate manual
acceptance gates. Synthetic offline tests establish behavior, not real-source
accuracy. Never put brokerage credentials, raw account HTML or private backup
archives in Git. Store prompt overrides separately at `/data/prompts`; restoring
an archive does not replace that directory.
