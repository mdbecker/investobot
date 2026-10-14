# Investobot project rules

## Current scope and workflow

- [Correctness/simplification PRD](docs/PRD-mvp-correctness-simplification-2026-10-13.md)
  controls explicit later decisions; Gate 0 covers A-F. Use one recursive exposure
  engine and one planner; synthetic preview saves nothing. Real proposals need
  saved targets and approved policies; dataset publication needs confirmation.
  Preserve source-only constituent amounts without ticker-based identity claims.
  Combine compatible household dates without inventing flow chronology.


- [Host-agent/persistence PRD](docs/PRD-mvp-host-agent-docker-persistence-2026-10-12.md)
  controls execution, storage, prompt retirement and viewer corrections. It
  supersedes conflicting execution/storage/setup statements. The owner authorizes
  fresh host-backed state; no migration or compatibility handoff is required.
  [Foundation PRD](docs/PRD-mvp-foundation-stabilization-2026-10-12.md) controls
  financial stabilization/Phase 1–2; [wrap-up](docs/PRD-mvp-wrap-up-2026-10-12.md)
  controls finite performance/fuzz scope; [unified PRD](docs/PRD-unified-mvp-2026-10-10.md)
  supplies the remaining product contract. Historical PRDs/reports are evidence,
  not current setup instructions. See [current handoff](docs/implementation/host-agent-status.md).
- Keep `main`; conventional commits only. No remotes, fetches or pushes.
  Coordinator commits observed test-only red before new behavior/confirmed bugs,
  and verified green afterward. Pure refactors use existing green behavioral tests.
  Write the complete changed A-F scenario set before any production edits.
  No skips, xfails, artificial internal mocks or read-count/call-order assertions.
- When parallel work is requested, agents own separate files/modules and never
  commit. Coordinator owns shared CLI/models/ledger/schema/contracts/integration.
  Announce readiness and freeze writes before exact-tree checkpoint verification.
- All execution, dependency resolution, tests and lint run in Docker; install
  nothing on the host. Host shell/Git and file editing are allowed. Copy `uv.lock`
  before locked sync; dependencies live at `/opt/venv`, never beneath project bind.
  Complete file-edit tool calls before Docker bind-mount verification; host file
  propagation can lag within a combined editing/testing call.
  Use UV_OFFLINE=1 for locked offline resolution and disposable containers without private ledgers; Ruff always receives
  `--config pyproject.toml`. Local results are not remote CI evidence.
- Review intent → architecture → implementation → polish. Investigate bloat,
  redundant/dead interfaces, leaky boundaries, duplication and coupling without
  speculative refactors. Stop after finite acceptance; real-source validation is
  separate Phase 2. Missing referenced review guides must be disclosed.

## Host, Docker and durable storage

- The independently supplied **host agent** reads canonical `skills/` or optional
  project `.agents/skills`/`.claude/skills` copies, gathers authorized evidence and
  requests human review. `./scripts/invest` is a tiny POSIX shell bridge to
  `docker compose run --rm -T app invest`; no host Python, agent runtime, scheduler,
  prompt service, sidecar, RPC layer or second application.
- One current app image/service. Project bind `/app`; host `local-data/state:/data`
  holds `portfolio.db`, WAL/SHM, referenced artifacts and receipts. `input/`, `work/`
  and `agent-notes/` are ordinary private host files. Pre-create restrictive
  directories and verify invoking-user access. Ignore private data, `.env`, HTML,
  SQLite/backups and generated `investobot-*` skill copies; unrelated skills remain
  visible to Git. Docker builds exclude entire `.agents/` and `.claude/` trees,
  private files and host `.venv`; canonical tracked `skills/` stay packaged.
- A bind mount is storage, not backup. Never copy live SQLite files. Online backup
  verifies integrity/FKs/artifact hashes and atomically publishes owner-only archives.
  Restore stages/validates before explicit confirmation and holds restore locks.
  Every application DB handle holds the shared lock until close. Read-only queries
  still require access to the shared filesystem lock; a read-only directory mount
  can block recovery checks. Keep SQLite query-only enforcement independent of mount
  permissions. Preserve unrelated
  files; cleanup targets only unreferenced managed staging under the publication lock.
- Fresh host-backed storage is authorized; initialize through existing application
  behavior. Do not copy development state, alter schemas or delete unused Docker
  volumes as part of setup. Ordinary verified backup/restore safety remains.
- PromptLibrary, bundled defaults and `invest prompt` CRUD are retired. No supported
  `INVEST_PROMPTS` setting. Operator context is ordinary untrusted host Markdown;
  never automatically merge it into trusted skill text.
  Install skills only explicitly into project-local agent directories, rejecting
  traversal/symlinks/nonregular destinations and protecting edited resources.

## Financial invariants

- SQLite is the sole writable financial truth, with FK ON, WAL, synchronous FULL,
  busy timeout 5000 and atomic related writes. No ORM/service framework. Schema 1
  includes the foundation checksum.
  Future migrations are transactional/checksummed with verified pre-migration backup.
  DuckDB is ephemeral/read-only; Parquet artifacts have manifests/hashes; vec0 is
  pinned/baked and derived indexes are rebuildable. Recovery loads verified vec0
  when required and verifies corpus retrieval as well as financial facts.
- Exact Decimal values use plain normalized strings. Scale calculation context to
  magnitudes; conserve low-order residues. Identifiers/source lexemes stay exact.
  Printed precision is explicit source evidence, never inferred from storage.
  Never invent identity, lots, basis, prices, classifications or cash coverage.
- Explicit REAL/SYNTHETIC provenance reaches parser and accepted facts. Mixed inputs
  cannot yield actionable proposals; blocking parser evidence cannot become clean
  accepted holdings. Unknown never means zero/current/complete/safe. Gate on typed
  issue fields, not warning prose. JSON success stdout/errors stderr use codes
  1 input, 2 external, 3 blocked/inconsistent, 4 internal; incomplete outcomes retain issues.
- Human-confirmed idempotent commands alone change facts. No trades, broker credentials
  or raw account HTML persistence. Partial imports preserve unobserved inventory;
  old observations cannot erase confirmed activity. Source/import dates differ;
  date-only same-day ambiguity requires reviewed ordering. Fresh reads on every
  command; no cross-command caches. Account settings remain authoritative.
- Strong IDs and sourced aliases share `security_identity.resolve`; ambiguous or
  conflicting matches fail. OTHER reclassification requires sourced preview/confirm;
  registration cannot bypass it. Lot IDs are globally unique; missing local IDs
  require indexed global checks. Protected exhausted confirmed lots remain history;
  identity membership never permits stale financial values.
- Specific executions preserve exact remaining adjusted basis and final residues;
  unknown selection is never FIFO. Fees stay separate; execution prices are not
  marks. REAL sales require verified sourced broker lot identity, identity review
  and explicit saleability. Retirement share sales need verified inventory but may
  have null basis/dates; never invent retirement gain/term. Taxable lots need basis/dates.
- No currency aggregation without FX. Quote TTL is 900 seconds; dataset TTL differs.
  Caches are not historical evidence and never update canonical marks/quantities.
  Hypothetical research/plans/backtests preserve holdings, marks, caches/events and
  fingerprints. Look-through preserves known numeric exposure and unknown residual,
  cycles/depth/path/vintage; completeness needs matching environment/source/date and
  visible persisted typed issues. Numeric coverage is separate from evidence quality.
- Actual performance needs complete dated checkpoints/flows and boundary marks.
  Household transfers need explicitly reviewed linked atomic legs with matching
  currency/environment/order, never inferred balance differences. Dense conventional
  XIRR retains every flow; nonconventional complexity remains typed review. Risk
  aligns every requested session; weekdays never establish exchange-calendar evidence.
- Targets are immutable fractions totaling 1 ±0.000001. Separate approved immutable
  policies have independent strict buy/sell/hold booleans and exact increments,
  floors/minimum notionals/freshness. Unknown permissions/fees remain review gates.
  Contributions-only never sells; rebalance uses cash first on any valid date without
  calendar/month/drift gates. Quarterly strategy is explicitly historical only.
- Annual USD positive tax-cost allowance uses confirmed taxable sales and explicit
  ST/LT rates/coverage. Losses do not replenish it; saved plans do not spend it.
  Mandatory household/IRA/spouse/DRIP/substantially-identical wash review remains;
  never certify legality or guaranteed savings. Harvest uses approved policy identity,
  verified loss lots, sourced replacement prices and both exact cash legs/fee residue.
- Plans pin source/policy/manifest/algorithm and simulate cash/lots/value before save.
  Current staleness is separate from immutable history. List/compare use compact
  projections; full detail stays explicit. No historical recalculation with fresh prices.

## Viewer, research and acceptance

- Dashboard is GET-only, query-only, persisted/provider-free. Every POST returns 405
  before body/application-data access; no commands/jobs/agent launch. Close DB handles
  before responding, including errors. Native bind is loopback; Docker publishes
  host loopback only. Backtest list is compact; detail/compare use immutable runs.
- External agents research; humans verify original sources and rights. Investobot
  validates strict immutable evidence, never establishes source truth/permissions
  through structure. No scraping, FEC/SEC clients, political scores, forecasts,
  monitoring or trade signals. Research acceptance is atomic/run-scoped and does
  not register/reclassify securities or refresh fund/market caches. Named contributor
  evidence needs independently reviewed rights, never agent assertions or `--yes`.
- Specialty completeness covers every requested task. Preserve native hashes,
  exact issuer/entity/period/definition/unit/basis comparability and independent skill
  identities. News absence is NOT_REOBSERVED, not closure; explicit terminal evidence
  controls history. Insider corrections preserve filing/owner/person associations and
  separate transaction codes. Fund diligence requires original exact-class identity,
  <=100 descending TOP_N, no normalized weights/invented residual.
- Corpus adapters need explicit permission; no automatic broker/personal embeddings.
  Canonical model/dimension/content compatibility precedes ranking; keyword-only
  fallback stays explicit. Plain bonds use SciPy cash flows; complex instruments
  remain unavailable, and fixed redemption does not price embedded options.
- Synthetic fixtures and actual CLI demo establish development behavior only.
  Vanguard, Fidelity NetBenefits and PNC remain PROVISIONAL; live FMP remains
  UNVERIFIED pending reviewed real evidence/entitlements. No real documents/secrets
  needed for offline acceptance. See [data sources](docs/data-sources.md).
- Exactly eight fixed representative paired workflows, reference
  `d0940a12c44831095492efcd7091fb7b937ad6b3`, native ARM64 same runner, one warm-up,
  five shared-batch samples. Calibration targets 600 ms; reject raw samples <200 ms.
  Confirm >25% median slowdown with one complete repeat pair. No p95/scaling/import
  optimization/general certification. Verify native outputs before projecting only
  reviewed incidental/semantic deltas; retain invalid evidence, actual failures and
  exit codes outside Git. Fixtures/reset/oracles stay outside timed operations.
- Fuzzing requires explicit human invocation and [fuzz/SKILL.md](fuzz/SKILL.md):
  offline disposable allowlisted full-scenario JSON replay, actionable reports,
  independent exact oracles. CI runs fixed regressions only, never agent campaigns,
  providers or issue publication. Never run untrusted PR code on personal runners.
