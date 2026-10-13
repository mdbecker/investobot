# Local recovery operations

Use the Docker runtime and the selected ledger only. Do not copy a live SQLite
`.db`, `-wal` or `-shm` file as a backup. Keep the ledger outside cloud-sync and
network folders. These commands do not access a brokerage or place trades.

```sh
./scripts/invest db status
./scripts/invest db backup --output /data/backups/ledger.tar.gz
./scripts/invest db verify /data/backups/ledger.tar.gz
./scripts/invest db restore /data/backups/ledger.tar.gz --dry-run
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
./scripts/invest db restore /data/backups/ledger.tar.gz --confirm
./scripts/invest db verify /data/portfolio.db
```

Restore rejects traversal, symlinks, hard links, devices, duplicate members and
unlisted files. It rejects hash mismatches and conflicting existing immutable
artifacts. Active WAL readers or writers block replacement; an idle client must
also be stopped because it can retain an old file handle. Restore removes only
the selected ledger's SQLite sidecars after the writer guard and validation pass.
It preserves unrelated host notes and ordinary files. Immutable artifacts copied
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
archives in Git. Keep operator context at host `local-data/agent-notes/`; restoring an archive does not replace it.

Preview abandoned managed publication staging with `invest db cleanup-artifacts
--artifact-root /data/artifacts`; repeat with `--confirm` to remove reviewed
unreferenced `.artifact-*` staging files. This command shares the publication lock,
preserves referenced artifacts and ordinary user files, and rejects symlink paths.
It is not general directory cleanup and never changes canonical financial state.

## Host storage and one-time named-volume handoff

The current Compose configuration binds `./local-data/state` to `/data` and the
project to `/app`. SQLite, its sidecars, immutable artifacts and backup receipts
therefore remain on the host after disposable CLI containers, the web container
or its image are removed. This bind mount is storage, not a backup.

For a new installation, pre-create private directories before starting Compose:

```sh
umask 077
mkdir -p local-data/state/backups local-data/input local-data/work local-data/agent-notes
chmod 700 local-data local-data/state local-data/state/backups local-data/input local-data/work local-data/agent-notes
```

On macOS with Docker Desktop, verify the invoking user can read the resulting
files. On Linux, run disposable CLI commands with `--user "$(id -u):$(id -g)"`
when using Docker Compose directly; apply the same user setting to the web
service through a local Compose override. Check host access before accepting
private data. Do not start with inaccessible root-owned directories. Never add
private files or that local override to Git.

### Preserve an existing named volume before switching

Do not start the new bind configuration until the old volume has been inspected
and its populated ledger successfully preserved. Keep the old Compose definition
available and stop its web service and ordinary writers. While `ledger:/data`
still selects the original volume, use that old configuration to run:

```sh
docker compose run --rm -T app invest db status
docker compose run --rm -T app invest db verify /data/portfolio.db
docker compose run --rm -T app invest db backup --output /app/local-data/work/pre-bind-volume.tar.gz
docker compose run --rm -T app invest db verify /app/local-data/work/pre-bind-volume.tar.gz
```

Retain the command JSON reports in `local-data/work`, including the backup's
`receipt.database_fingerprint`, archive hash and manifest file inventory. The backup archive
includes accepted records, saved calculations and referenced immutable artifacts;
retain it independently of the volume. Also save `portfolio summary`, `plan list`
and `target list` outputs with the old configuration and compare them after
restoration; the logical fingerprint covers all stored tables, including saved
backtests and research. Check that the archive is readable by the host user. Export any operator-authored prompt overrides to
`local-data/agent-notes` for human review before retiring their old interface;
never merge them automatically into trusted skills.

Only after successful verification, select the new bind configuration, leave
writers stopped, and preview the preserved archive:

```sh
./scripts/invest db restore /app/local-data/work/pre-bind-volume.tar.gz --dry-run
```

Review the manifest and request human authorization before the replacement:

```sh
./scripts/invest db restore /app/local-data/work/pre-bind-volume.tar.gz --confirm
./scripts/invest db verify /data/portfolio.db
./scripts/invest db backup --output /data/backups/post-bind-verification.tar.gz
```

Compare the new backup's logical `database_fingerprint` to the preserved source
report; also compare saved-record inventory and referenced artifact hashes. Keep
both archives and the original named volume. Take an encrypted off-device copy
using operator-selected backup tooling. A backup on the same device does not
protect against device loss.

If inspection shows a genuinely absent/uninitialized ledger and no other private
volume files, create the host directories normally; report that no migration was
necessary. If any verification, backup, preview or comparison fails, stop. Preserve
the archive, source volume and destination files; do not initialize an empty
replacement, delete/prune the source volume or reset an unsupported schema.
Rollback selects the retained old Compose mapping and original volume after all
new writers stop. Do not copy live SQLite files between the two locations.

During this implementation the operator's existing named volume contained an
86,016-byte unsupported development-schema ledger. Verification and backup could
not produce a valid archive. Its original volume and existing service were
preserved; no real-data restore or successful migration is claimed. Do not start
the new bind service against that installation until the operator resolves this
blocked preservation step. Synthetic disposable archives separately verify the
supported backup/restore path.

For a selected ordinary legacy override, preserve its bytes before retiring the
old prompt interface. With the old mapping still active, inspect filenames and
review the chosen regular Markdown file; then copy it explicitly (replace the
example slug, and repeat only for files you choose):

```sh
umask 077
mkdir -p local-data/agent-notes/legacy
# Run with the retained OLD Compose configuration, before changing its mapping:
docker compose run --rm -T --entrypoint sh app -c \
  'test -f /data/prompts/CHOSEN.md && test ! -L /data/prompts/CHOSEN.md &&
   test ! -e /app/local-data/agent-notes/legacy/CHOSEN.md &&
   test ! -L /app/local-data/agent-notes/legacy/CHOSEN.md &&
   cp -p /data/prompts/CHOSEN.md /app/local-data/agent-notes/legacy/CHOSEN.md'
```

Choose a new destination name if a note already exists; the guard refuses replacement.
Check the host copy against the source before proceeding. This transfers context,
not trusted instructions; review it manually, and retain the original volume.
No overrides were found in the volume inspected during this implementation.
