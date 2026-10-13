# Investobot — MVP Host-Agent, Docker Isolation, Durable Storage & Read-Only Viewer PRD

**Date:** 2026-10-12  
**Type:** One finite, consolidated MVP correction; six bounded work packages  
**Baseline:** `mdbecker/investobot` at `17d6668e08ab10be6bdf6d31573520d4e1268180` (recheck HEAD before editing)  
**Priority:** A–D must fix before foundation acceptance; E–F complete the same handoff.  
**Dependencies — already complete before this PRD starts:** `docs/PRD-unified-mvp-2026-10-10.md`,
`docs/PRD-mvp-wrap-up-2026-10-12.md`, and `docs/PRD-mvp-foundation-stabilization-2026-10-12.md`,
including deterministic finance, read-only web, approved CLI writes, saved plans/backtests, test-first
synthetic acceptance and the eight representative performance workflows. **This PRD supersedes their
conflicting statements about Docker-owned prompts, Docker named-volume persistence,
host-versus-container agent execution, and active setup instructions.** Historical PRDs/reports stay
historical. It does not reopen previous financial-policy decisions.

## 1. Product contract and nonnegotiable decisions

**The host AI agent is Investobot's primary interface.** The agent reads host-visible `SKILL.md`
instructions, gathers evidence through its own authorized capabilities, chooses deterministic tools and
requests human authorization. A small **containerized Python CLI** performs accounting, validation,
simulation, research persistence and backed-up data changes. The **human-facing dashboard** displays
accepted facts, progress/status already persisted, saved plans/backtests and comparisons; it is
GET-only, never a place to enter facts, invoke the agent, run jobs or mutate SQLite. The CLI remains
technically callable by a human; “agent-only writes” means *workflow ownership*, not new authentication
or a prohibition on human-approved CLI commands.

**Docker is for dependency isolation, not for hosting an AI agent or its instructions.** No host Python,
`uv`, native SQLite extension, DuckDB, pandas or application packages. Docker and ordinary host
shell/Git are the only local execution prerequisites; the AI agent itself is supplied independently by
the operator. Keep **one current Docker image** and the existing Compose `app` service for the web
server plus disposable CLI invocations; do not add a second app, sidecar, RPC layer, scheduler,
orchestration framework, or new database service.

**All durable financial/project-private data lives in `./local-data/` on the host, ignored by Git.** The
container sees the same bytes through explicit bind mounts. Docker images/containers/named volumes are
not the authoritative storage location. The SQLite DB, its WAL/SHM sidecars, immutable artifacts and
backup receipts must share the stable `/data` mount; the backup archive can be saved under
`/data/backups` but needs a separate encrypted/off-device copy for disaster recovery. Never copy a live
SQLite file as a backup. Existing human authorization, idempotent accounting, source evidence,
`Decimal`, immutable data contracts, tax/wash-sale gates, provisional institution adapters, no automatic
trades and no real-document testing during this PRD remain unchanged.

### Canonical paths and execution contract

```text
investobot/
  skills/                         # Tracked canonical agent skills/references
  scripts/invest                  # Tracked host POSIX shell -> Docker CLI bridge
  .agents/skills/                 # Optional host-visible installed copies for Codex
  .claude/skills/                 # Optional host-visible installed copies for Claude Code
  local-data/                     # Entire directory ignored by Git and Docker build context
    state/
      portfolio.db                # Also: -wal, -shm, backup receipt, artifacts/
      backups/                    # SQLite-consistent verified archives
    input/                        # Private supplied broker/source documents
    work/                         # Temporary candidates, reports and exports
    agent-notes/                  # Optional operator-authored agent context/legacy prompts
```

- **Host:** `./local-data/state/portfolio.db`; **container:** `/data/portfolio.db`. The
  `./local-data/state:/data` bind replaces `ledger:/data`; retain `.:/app` for host-visible project
  inputs, outputs and skill installation. `INVEST_DB=/data/portfolio.db`. Container-created DB,
  artifacts, WAL, backups and receipts must be host-visible and survive rebuild, `docker compose down`,
  and `docker compose run --rm`.
- **CLI:** `./scripts/invest portfolio summary` is equivalent to `docker compose run --rm -T app invest
  portfolio summary`. Implement `scripts/invest` as a tiny executable POSIX shell script: change to
  repository root using its script location, then `exec docker compose run --rm -T app invest "$@"`
  (faithfully forward arguments, stdin, stdout, stderr and exit status). Do not implement financial
  logic, JSON parsing or Python environment setup in the wrapper. Use `/app/local-data/...` for files
  passed as container path arguments, or pipe via `-` as already supported.
- **Web:** `docker compose up -d app`; host access only at `http://localhost:8765`. The dashboard's
  SQLite queries remain read-only and provider-free. Starting or browsing against no ledger must not
  create one.
- **Skills:** canonical text is the tracked `skills/` directory. Existing `invest research skills
  install --agent codex|claude-code --workspace /app`, invoked **through `./scripts/invest`**, installs
  into the host project bind mount; the *external host agent* reads those files. Copying skill text into
  a distributable Python wheel or Docker image is an installation mechanism, **not** agent execution in
  Docker. No special agent container, daemon or prompt service.
- **Prompts:** remove the redundant independent `PromptLibrary` / `invest prompt` CRUD interface and
  bundled default-prompt package *after* checking each default for unique, still-relevant content and
  incorporating only such content into a matching existing skill/reference. Existing skill subjects
  suffice; no new skills for duplicate topics. Operator-authored context is ordinary host Markdown (e.g.
  `local-data/agent-notes/`), directly accessible to the agent, not a Docker-managed `/data/prompts`
  library. If local user overrides exist, export/copy them to host notes for review before retiring the
  interface; never silently discard or treat their content as instructions from a trusted source. Drop
  `INVEST_PROMPTS` from the supported runtime setup, not unrelated research/evidence controls.
- **Private files:** continue ignoring `.env`, `local-data/`, `*.db*` and private HTML. Add narrow
  ignores for generated project skill copies (the `investobot-*` bundles within `.agents/skills` and
  `.claude/skills`) without ignoring unrelated operator skills. Do not commit actual account files,
  SQLite sidecars, backups, credentials, prompt overrides or reports. Keep `local-data` outside the
  Docker build context. On supported hosts, pre-create private directories with restrictive permissions,
  and ensure the invoking user can inspect/back up the resulting host files; do not leave root-owned
  inaccessible state.

## 2. Required development and review protocol

Use **both supplied guides**: `code_review(8).md` and `code_smell_review(9).md`. Review **intent →
architecture → implementation → polish**; check Bloaters, Object-Orientation Abusers, Change Preventers,
Dispensables and Couplers, including overlong docs, redundant prompt systems, leaky boundaries,
duplicated execution instructions, dead routes, stale contracts and over-mocked tests. Smells are
prompts for investigation, not automatic refactor orders. Choose one coherent implementation, remove
obsolete features (pre-user codebase), and avoid backwards-compatibility layers or migrations for unused
schemas. **The sole exception is the explicit one-time preservation/transfer of any existing
Docker-volume data; never destroy user files just because formal compatibility is unnecessary.**

**Mandatory red-first BDD for all changed behavior in packages A–D:**

1. Before changing *any* production code, **write the complete new/changed behavioral scenario set for
   A–D** in small domain-focused pytest/pytest-bdd tests, and separately identify existing green
   invariants and obsolete tests to delete. Scenario wording follows concrete **Given / When / Then**
   outcomes observable through the shell command, CLI, dashboard, host filesystem or data report—not
   internal calls or mocks. A refactor-only/docs-only item does not need a contrived failing test.
2. Run all changed-behavior scenarios against the **unchanged baseline**. Record which go red and
   exactly why; investigate unexpected passes rather than weakening or manufacturing failures. Keep this
   as a test-only checkpoint before source edits. Use disposable synthetic data and real temporary
   SQLite/Compose paths; mock only external provider/network boundaries, never domain internals, storage
   transactions or command call order.
3. Implement A–D, making the relevant scenarios green package by package. Delete tests only for
   intentionally retired behavior, retaining unrelated safety assertions. E reconciles
   docs/instructions; F runs integrated acceptance. Retest failure paths after simplification.
4. Review the touched diff with the guides. Do not use formatting-only metrics or speculative cleanup to
   expand scope. Report changed/deleted files, baseline red evidence, final green results and remaining
   limitations.

## 3. Work packages (distinct ownership, ordered dependencies)

### A — Host-to-Docker CLI bridge and agent command contract

**Owner:** `scripts/invest` (new), lightweight shell/CLI invocation tests, command examples in existing
13 `skills/**/SKILL.md` and nearest CLI references **only**. **Depends on:** none beyond baseline.

Supply the one-command POSIX shell bridge specified above. Update skill instructions to explicitly
distinguish *commands invoked by the host agent* from the Python CLI executed inside Docker; example
invocations must consistently use `./scripts/invest ...` (or an explicitly shown equivalent Docker
Compose command). All source retrieval and human approval happens in the host agent; deterministic math,
provider access via existing CLI integrations and accepted state writes happen in Docker. Do not
introduce a separate adapter CLI, host Python entrypoint, installed agent runtime or an alias that
depends on interactive shell state. Ensure command discovery (`tools list`/`describe`) works through the
wrapper.

**BDD examples:** Given Docker but no host Python environment, when the agent runs `./scripts/invest
tools list`, then it receives the canonical JSON and no host virtualenv/package installation occurs.
Given a valid JSON file/standard-input payload, when an agent invokes the wrapper, then bytes and exit
codes correspond to the containerized CLI. Given project-local skills installed using the wrapped
command, then the host agent can read all 13 skills from its chosen workspace and still relies on Docker
for calculation.

### B — Durable host binding, safe existing-volume handoff, and backup behavior

**Owner:** `compose.yaml`, `.gitignore`/`.dockerignore`, host-storage integration tests,
deployment/migration subsection of `docs/operations.md`. **Depends on:** A for test ergonomics, but
changes must not alter the CLI's financial behavior.

Replace the named `ledger` volume with `./local-data/state:/data`, remove its Compose declaration,
retain project bind `/app`, loopback web publication, current image and existing environment/secrets
behavior (except retired prompt path). Create needed ignored directories explicitly before Compose
startup; ensure non-root host access to the created state on the supported target environment. Keep
data/root semantics consistent with existing backup and immutable artifact paths. No new tables,
migrations, file copy on each startup, background sync, duplicate databases or custom backup service.

**One-time migration if the prior named volume contains any data:** **never** mount over it and lose
visibility. While the original Compose mapping still applies, stop ordinary writers as appropriate,
create a consistent verified archive using existing `invest db backup --output
/app/local-data/work/pre-bind-volume.tar.gz`, verify it and capture the logical financial
fingerprint/ledger inventory; preserve this host archive. Only then switch Compose, stop the web
service, preview restore from the host archive using the existing `db restore` contract, require
explicit confirmation and restore into the new bind-mounted `/data`; verify ledger integrity, referenced
artifact hashes, financial fingerprint and saved records against the source. On any error, stop and
preserve both archive and original named volume; do not auto-delete/prune volumes, fabricate state or
silently initialize an empty replacement. For a genuinely empty/uninitialized volume, create the host
state normally without pretending a migration occurred. Document the operator-controlled rollback path.
Keep an encrypted off-device backup as a separate human operational step. A backup under
`local-data/state/backups` alone does not protect against device failure.

**BDD examples:** Given a synthetic ledger with accepted holdings, saved analysis and an artifact, when
a CLI container is removed/recreated and the image rebuilt, then exact accepted records and artifacts
remain in `local-data/state` and are accessible to the next agent command and dashboard. Given a prior
populated named volume, when its verified archive is restored into the bind mount, then records and
artifact hashes match and the original volume remains untouched. Given an invalid/missing archive or
failed verification, then no existing accepted DB is overwritten. Given a repository checkout, when
private files/backups are created, then Git cannot stage them through ordinary `git add .` and Docker
build context excludes them. Given an absent ledger, a dashboard GET does not create a DB.

### C — Host-owned skills and deletion of redundant prompt storage

**Owner:** `src/invest/prompts.py`, `src/invest/prompt_defaults/`, relevant `src/invest/cli.py` prompt
subcommands, prompt tests, `docs/prompts.md` and installation tests. **Depends on:** A; B only for host
notes path. **No change** to existing researched financial calculations or external-agent integration.

Audit the nine bundled prompt defaults against the thirteen tracked skill workflows; fold **unique,
currently supported instructions** into the closest existing skill/reference without dumping duplicate
prose. Remove the independent `PromptLibrary`, `invest prompt list/show/save/delete`, obsolete tests and
prompts documentation after the audit. Preserve (by explicit host export and human review) any actual
user override Markdown before deletion; no automatic merger of untrusted overrides into trusted skill
instructions. Continue packaging/installing skills for agent discovery, but explicitly verify their
installed destination is host-visible, not `/data/prompts`. Remove runtime defaults and Docker
environment settings that give the impression prompts must be kept in a container volume. Keep exact
current skill contracts and human approval; no new instruction registry, database table, skill API,
prompt editor, UI or compatibility alias.

**BDD examples:** Given a clean checkout and an agent installation request, when the Docker CLI
installer completes, then the host workspace has the available financial skills and their references,
with no hidden dependency on a prompts volume. Given an edited installed skill, when an installation
would overwrite it, then the existing explicit overwrite safeguard remains. Given legacy user-authored
notes, when preparing to remove prompt storage, then the files are preserved on the host for review.
Given a bundled topic once available only as a prompt, when the appropriate skill is read, then any
**unique supported** workflow guidance remains available without a separate prompt command. Retired
`invest prompt` commands must not appear in public discovery.

### D — Finish the two remaining dashboard review fixes

**Owner:** `src/invest/web.py`, the smallest related change to `src/invest/analytics.py` (if needed),
`src/invest/static/app.js` only for display, focused dashboard tests. **Depends on:** B's read-only
persistence assumption; no other package should edit these files.

**Evidence correctness (must fix):** the currently selected persisted fund-holdings observation may
contain `issues` such as `PARTIAL_SOURCE_DATE_COVERAGE`; the shared dashboard exposure calculation
currently uses numeric holdings but fails to surface these typed observation issues. Propagate source
issues into the read-only dashboard's existing response/visible warnings, label **numeric holdings
coverage separately from verified evidence completeness**, and preserve all known exposure dollars and
unknown residuals. A 100%-weighted, $1,000 synthetic ETF with a partial-source-date issue must still
show its known $1,000 allocation **and** a clear evidence warning, never a false claim of fully verified
coverage. Do not add another look-through engine, make provider requests or discard good data.

**Compact saved backtest lists (should fix now):** `/api/backtests` returns a small per-run summary only
(ID, start/end, status, creation date and useful headline metrics; no full history/manifest/curve).
`/api/backtests/ID` still returns the full immutable record, and the existing GET comparison still calls
`backtest.compare` on stored runs, preserving assumption mismatch statuses. Use the existing table and
ordinary SQL/JSON projection; no schema change, materialized view, pagination service or caches. Add BDD
for listing many saved runs without transferring full histories, inspect one full run and compare
incompatible saved runs without changing DB bytes.

### E — Rebuild the README and reconcile the *active* source of truth

**Owner:** `README.md`, `docs/architecture.md`, `docs/operations.md` remaining narrative,
`docs/workflows.md`, `docs/skills.md`, `docs/research-skills.md`, `docs/inspection.md`,
`docs/testing.md`, `docs/trading-policy.md` if stale, and **`AGENTS.md`**. **Depends on:** A–D; no new
product behavior. This package alone resolves cross-cutting documentation conflicts; A–D may edit only
their narrowly owned docs.

Rewrite the README **for a first-time user**, not as a terse release log or command index. It must
teach, in this order: (1) what Investobot is, including human/agent/CLI/dashboard responsibility, (2)
clear “host vs Docker vs bind-mounted data” diagram/table, (3) prerequisites and five-minute quickstart,
(4) how to make an agent discover/install skills and invoke a first safe Docker CLI command, (5) one
complete fictional agent-run flow through preview → human authorization → accepted data → read-only
dashboard, (6) exact private paths and consistent SQLite backup/restore, including safe existing-volume
migration, (7) limitations/real-source validation gate, and (8) links to detailed operations/reference
docs. Show commands that actually work from a fresh checkout; use valid `.tar.gz` archives, explicit
REAL/SYNTHETIC labels and real command options. Do not make the agent's skill installation or CLI calls
seem to execute an AI model inside Docker. Explain Docker *named volume vs bind mount* accurately, and
that the host bind is not itself a backup.

Remove current active contradictions: `/data/prompts` as the canonical agent instruction store, obsolete
prompt-library docs, stale “quarterly rebalance required” statements, old skill counts/schema claims,
dashboard write instructions, conflicting directory paths and developer-only implementation chronology
in the README. **Prune `AGENTS.md`** into current invariants and pointers to detailed references; remove
obsolete write-route, benchmark and historical implementation directives instead of appending another
superseding header. Keep old PRDs/status reports as historical context, with a small supersession
pointer where appropriate; do not rewrite historical measurements. Avoid verbose repetition across docs,
misleading guarantees, marketing claims or private data examples.

**Review proof:** a developer unfamiliar with the repo can follow the README from zero host Python
installation to an installed host skill, one synthetic CLI read/preview, persistent host DB and working
read-only dashboard; all commands/paths agree with Compose, current CLI discovery and the active skills.
This is a documentation validation exercise, not a contrived failing financial test.

### F — Integrated synthetic acceptance and stop

**Owner:** final integrated tests, lean handoff report and existing benchmark checks; no new features.
**Depends on:** A–E.

Run full offline tests and Ruff in disposable Docker without a real/private ledger; include wrapper
stdin/stdout/error, host skill installation, host bind persistence, safe synthetic backup/restore,
absent/present viewer, provider-free GET, rejected POST, typed look-through evidence, compact backtest
lists/full details/compare, accepted-state fingerprints, 34-step existing synthetic demo and existing
eight paired representative performance workflows. Do not make real provider calls, include private
source files in CI, or reintroduce general fuzz campaigns. Retain the existing confirmed >25%
representative performance slowdown check and treat intentional changed outputs as explicit reviewed
deltas, not permissive rebaselines.

Deliver concise evidence: initial intended-red scenarios (and surprising passes investigated);
successful green counts/commands; files/code and deprecated interfaces removed; preservation/rollback
outcome for any legacy volume; local vs remote CI status; known limits. **Stop after these criteria
pass.** Separate Phase 2 real brokerage HTML and live FMP response validation begins only after the
operator accepts this foundation.

## 4. MVP definition of done

- The **host agent** can read the installed `skills/` instructions and call every deterministic CLI
  capability via one small Docker bridge; no project packages install on the host and no agent runtime
  lives in Docker.
- The **single shared host project data directory** contains authoritative SQLite, WAL/SHM, immutable
  referenced artifacts, backups and agent working files, remains Git-ignored, and survives
  container/image deletion; old named-volume data is explicitly verified/migrated without loss or forced
  deletion.
- The **read-only dashboard** can never trigger a DB mutation or provider refresh; persisted fund
  evidence quality remains visible even when numerical weights total 100%; backtest list responses
  remain compact without losing full detail/compare.
- Canonical agent skills are accessible from the host, with no redundant Docker prompt-library
  persistence or duplicate instructions; any actual user prompt overrides are preserved before interface
  retirement.
- The README correctly teaches the complete workflow and persistence/backup model, and active docs,
  skills, tests and `AGENTS.md` do not contradict it.
- All new/changed BDD behavior was **authored and observed red before any production code changes**,
  then made green; unaffected financial invariants, the full offline suite, end-to-end demo and current
  lightweight performance guard remain green.
- **No new frameworks, services, DB schema, hosted infrastructure, authentication system, automation of
  trades, branch-protection requirement, broad refactor or premature real-financial-document testing.**
