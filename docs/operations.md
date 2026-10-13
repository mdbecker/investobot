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

Backup publishes an owner-only receipt beside the database. Verification and
restore previews never create receipts. Make another verified backup after
accepted financial or research changes.

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

## Host storage

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

Fresh host-backed storage is authorized; no migration or data transfer is required.
The existing application initializes an empty ledger when an initializing CLI
command or confirmed acceptance needs it. Dashboard reads never create a ledger.
Complete `.agents/` and `.claude/` directories belong to the host agent and are
excluded from image builds; the tracked canonical `skills/` remain packaged for
installation. Keep ordinary operator context in `local-data/agent-notes/`.
