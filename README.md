# Investobot

Investobot keeps local portfolio records, validates source-backed research and
compares hypothetical plans. Your **host AI agent** is the primary interface: it
reads skills, gathers permitted evidence and brings concrete changes to you for
approval. The Docker CLI performs deterministic calculations and approved writes.
The dashboard shows accepted facts and saved results through GET-only reads.
You review evidence and execute trades manually; Investobot never accepts broker
credentials or places orders.

This is a synthetic-tested **development preview**. Vanguard, Fidelity NetBenefits
401(k) and PNC HTML adapters remain PROVISIONAL; live FMP contracts are UNVERIFIED.
The [current PRD](docs/PRD-mvp-host-agent-docker-persistence-2026-10-12.md)
governs execution and storage; [handoff evidence](docs/implementation/host-agent-status.md)
records validation and outstanding operator steps.

## Where things run

| Location | Responsibility | Files |
|---|---|---|
| Host | Your independently supplied AI agent, shell and Git | Canonical `skills/`, optional installed `.agents/skills` or `.claude/skills` |
| Docker, one `app` service/image | Python CLI and read-only dashboard; dependencies in `/opt/venv` | Project mounted at `/app`; durable state mounted at `/data` |
| Host `local-data/` | Authoritative private data, excluded from Git and image builds | `state/portfolio.db`, sidecars, artifacts, receipts, backups; `input/`, `work/`, `agent-notes/` |

A bind mount exposes host files to Docker. Unlike the old named volume, the
current data directory is directly visible in the checkout and survives container
removal and image rebuilds. **A bind mount is not a backup.** Neither the image nor
an agent container owns your financial data or instructions.

## Five-minute quickstart

You need Docker with Compose, ordinary shell/Git and an independently configured
host agent. Install no host Python, uv or project packages. No secret is needed
for discovery or fictional examples. The first image build can take longer than
five minutes.

**Upgrading an existing installation?** First follow the
[existing-volume preservation procedure](docs/operations.md#preserve-an-existing-named-volume-before-switching).
Do not start a new empty bind in place of a populated old ledger. The existing
volume inspected during this change has an unsupported development schema;
its actual handoff is stopped pending an operator decision, with data preserved.
The following setup is for a new installation or a completed verified handoff.

```sh
umask 077
mkdir -p local-data/state/backups local-data/input local-data/work local-data/agent-notes
chmod 700 local-data local-data/state local-data/state/backups local-data/input local-data/work local-data/agent-notes
docker compose build
./scripts/invest tools list
./scripts/invest tools describe portfolio.apply
docker compose up -d app
```

Open [localhost:8765](http://localhost:8765). Browsing an absent ledger does not
create one; the viewer displays the missing-data outcome. `docker compose down`
stops the service without deleting host data. On Docker Desktop, check that you
can inspect resulting host files. Linux operators should configure their own
UID/GID as described in [operations](docs/operations.md#host-storage-and-one-time-named-volume-handoff)
before private writes.

## Give your host agent the skills

```sh
./scripts/invest research skills list
./scripts/invest research skills install --agent codex --workspace /app
# For Claude Code instead:
# ./scripts/invest research skills install --agent claude-code --workspace /app
./scripts/invest tools describe portfolio.check
```

The installer copies all 13 canonical bundles into the host-visible project.
Your external agent reads them; installation does not start an AI model in Docker.
Ask it to use `investobot-portfolio-sync` and call commands from the checkout with
`./scripts/invest`. The bridge forwards arguments, stdin, output and exit status
to `docker compose run --rm -T app invest`. Container file arguments use
`/app/local-data/...`; stdin uses `-`. Modified installed skills require reviewed
`--confirm` replacement. Unrelated operator skills are preserved.

Success is JSON stdout with exact decimal strings. Errors are JSON stderr:
1 input, 2 external, 3 inconsistent/blocked state, 4 internal. Read typed issues
and review gates even when a command succeeds. Discover options with `tools describe`
and models with `schema`; the agent does no independent financial arithmetic.

## A complete fictional approval flow

For a **new empty demo ledger**, ask the host agent to prepare this explicitly
SYNTHETIC snapshot as `local-data/work/fictional.json`. These invented values are
only a tutorial; never relabel them REAL or apply them to your real account.

```sh
cat > local-data/work/fictional.json <<'JSON'
{
  "data_environment": "SYNTHETIC",
  "account": {"id": "fictional-ira", "name": "Fictional IRA", "tax_status": "TAX_FREE"},
  "positions": [{"security": "SYN-DEMO", "asset_type": "ETF", "quantity": "10",
    "price": "100.00", "market_value": "1000.00", "as_of": "2026-10-12",
    "displayed_price_precision": 2, "displayed_market_value_precision": 2}],
  "cash": "100.00", "cash_known": true,
  "source_timestamp": "2026-10-12", "source_hash": "SYNTHETIC-tutorial-v1",
  "positions_complete": true, "lots_complete": false
}
JSON
./scripts/invest portfolio reconcile /app/local-data/work/fictional.json
./scripts/invest portfolio apply /app/local-data/work/fictional.json
```

The agent shows the preview, source date, identity, quantities, cash and missing
lot/evidence limitations. Preview leaves the selected ledger absent or unchanged.
After you authorize **this specific fictional acceptance**, it runs:

```sh
./scripts/invest portfolio apply /app/local-data/work/fictional.json --confirm
./scripts/invest portfolio summary
./scripts/invest portfolio check --as-of 2026-10-12
```

The accepted ledger now lives at `local-data/state/portfolio.db`; refresh the
read-only dashboard to see it. Incomplete fund evidence stays visible even when
known numeric weights total 100%. This tutorial does not establish trading
readiness. For supplied HTML, `portfolio import` requires explicit
`--data-environment REAL|SYNTHETIC`; then reconcile, preview and authorize exactly
as above. The [account workflow](docs/workflows.md) explains precision, dates and
independent position/lot/cash coverage. The existing offline
[34-step demo](docs/testing.md) exercises plans, research and recovery separately.

## Private files and recovery

`local-data/input/` holds supplied documents; `work/` holds candidates/reports;
`agent-notes/` holds ordinary operator Markdown. SQLite, WAL/SHM, referenced
`artifacts/` and backup receipts share `local-data/state/` (`/data` in Docker).
Keep `.env`, private HTML, SQLite and archives out of Git. Do not keep the live
ledger in a cloud-sync/network directory or copy a live `.db` as a backup.

```sh
./scripts/invest db backup --output /data/backups/reviewed.tar.gz
./scripts/invest db verify /data/backups/reviewed.tar.gz
./scripts/invest db restore /data/backups/reviewed.tar.gz --dry-run
# Stop all writers/readers and review the preview before explicit replacement:
docker compose stop app
./scripts/invest db restore /data/backups/reviewed.tar.gz --confirm
./scripts/invest db verify /data/portfolio.db
```

Backup uses SQLite's online API and verifies referenced artifact hashes. Keep a
separate encrypted off-device copy with your own backup tooling. An archive on
the same laptop does not protect against device loss. Existing named-volume
handoff requires a verified archive, matching logical fingerprint/inventory and
explicit restore confirmation; preserve the original volume for rollback. On
verification failure, stop and preserve both sides. See [operations](docs/operations.md).
The prompt CRUD interface is retired; export any legacy overrides to host notes
for review before switching. Never merge untrusted notes into canonical skills.

## Manual gates and detailed references

Phase 2 begins after foundation acceptance: humans review anonymized original
Vanguard, Fidelity NetBenefits and PNC HTML, then validate actual FMP responses
and entitlements. No real account documents are used in offline tests. If you
choose public market integration later, create your own FMP account and supply
`FMP_API_KEY` through ignored `.env`; see [data sources](docs/data-sources.md).
Never provide brokerage passwords, cookies or sessions. Original-source truth,
reuse rights, wash-sale review, outside-account coverage and manual execution
remain human responsibilities. There is no automatic trade or schedule gate.

[Architecture](docs/architecture.md) · [Workflows](docs/workflows.md) ·
[Skills](docs/skills.md) · [Research skills](docs/research-skills.md) ·
[Viewer](docs/inspection.md) · [Trading policy](docs/trading-policy.md) ·
[Operations](docs/operations.md) · [Testing](docs/testing.md) ·
[Performance](docs/performance.md) · [Project rules](AGENTS.md).
