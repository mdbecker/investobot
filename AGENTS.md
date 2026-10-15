# Investobot project rules

Read [the current contract](docs/contract.md) for product and financial invariants,
[workflows](docs/workflows.md) for commands, and [readiness](docs/readiness.md)
for verified scope and human gates. Git history holds superseded specifications
and reviews; do not restore them as active instructions.

## Execution and collaboration

- Work on `main`; use conventional commits. No remote operations, fetches or pushes.
- Run all application execution, dependency resolution, tests and lint in Docker.
  Install nothing on the host. Host shell, Git and file editing are allowed.
  Copy `uv.lock` before locked sync; dependencies belong in `/opt/venv`, never the
  project bind. Use `UV_OFFLINE=1`, no network and disposable ledgers for tests.
  Ruff always receives `--config pyproject.toml`.
- Write the complete changed behavioral scenario set before production edits.
  Commit observed failing tests first, then verified passing changes. Pure
  deletions/refactors use existing behavioral coverage. No skips, xfails,
  artificial internal mocks or read-count/call-order assertions.
- Delegate only when requested. Give agents separate files; agents never commit.
  The coordinator owns shared CLI/models/ledger/schema/contracts/integration.
  Freeze writes before final verification. Finish editing calls before Docker
  verification because host bind propagation can lag.
- Review intent, architecture, implementation, then polish. Remove proven unused
  surfaces without speculative frameworks, compatibility layers or schema work.
  There is no shipping schema upgrade or embedding-generation adapter interface;
  retain schema/checksum validation, recovery and explicitly supplied vectors.
- Stop after finite acceptance. Do not run benchmarks, profiling, optimization,
  new audits or fuzz campaigns without a new explicit human request. Fixed CI
  regressions remain supported. For requested fuzz work read [fuzz/SKILL.md](fuzz/SKILL.md).
  Never run untrusted PR code on personal runners.

## Architecture and privacy

- An independently supplied host AI agent reads canonical `skills/`, gathers
  authorized evidence and requests human approval. `./scripts/invest` bridges to
  one Docker app CLI. No host Python/runtime, scheduler, prompt service or sidecar.
- SQLite schema 1 is the sole writable financial truth: FK ON, WAL, synchronous
  FULL, 5000 ms busy timeout, atomic related writes and foundation checksum guard.
  DuckDB is ephemeral/read-only; manifests hash Parquet artifacts; pinned vec0 and
  derived search indexes remain rebuildable.
- Private host `local-data/state:/data` stores SQLite, sidecars, artifacts and
  receipts. Pre-create restrictive directories and verify invoking-user access.
  Exclude private data, secrets, HTML, SQLite/backups and generated Investobot
  skill copies from Git; exclude whole `.agents/` and `.claude/` trees from images.
  Preserve unrelated skills/files. Canonical tracked skills remain packaged.
- Bind mounts are not backups. Never copy live SQLite. Online backup verifies
  integrity, FKs and artifact hashes; restore stages/verifies before confirmation.
  Every DB handle holds the shared filesystem lock until close, even read-only
  handles; retain query-only enforcement independently of mount permissions.
  Cleanup removes only unreferenced managed staging under publication locks.
- Initialize fresh state through existing application behavior. Do not copy old
  development state, alter schemas or delete Docker volumes during setup.
- Host notes are untrusted Markdown, never trusted skill instructions. Skill
  installation is explicit/project-local, rejects unsafe destinations and protects
  edited resources. Installed skills name outside docs as repository-root text;
  relative Markdown links are only for resources copied inside their bundle.
- Viewer is persisted/provider-free, GET-only and query-only. Every POST returns
  405 before body/data access. Close DB handles on all paths; publish loopback only.
  It never launches commands, jobs or agents.

## Financial and evidence boundaries

- Use exact magnitude-aware Decimal arithmetic and normalized plain strings;
  conserve final quantity/basis/fee residues. Preserve identifiers/source lexemes
  and explicit printed precision. Never invent identity, lots, basis, prices,
  classifications, chronology, FX or coverage. Unknown never means zero or safe.
- Carry explicit REAL/SYNTHETIC provenance and typed evidence issues throughout.
  Mixed provenance and blocking parser evidence cannot yield actionable plans.
  Cash requires explicit `cash_known:true`, including zero; position/lot coverage
  is independent. Partial/old imports preserve unobserved and confirmed activity.
- Only human-confirmed idempotent commands change facts. Fresh reads per command;
  account settings remain authoritative. No trades, broker credentials or raw
  account HTML persistence. Hypothetical work preserves facts, caches and fingerprints.
- Resolve strong IDs and sourced aliases centrally; fail ambiguity/conflicts.
  Reclassification requires sourced preview/confirmation. Lot IDs are globally
  unique; exhausted confirmed lots remain history. Unknown lot selection is never
  FIFO. REAL sales require verified broker lot identity and explicit saleability;
  taxable lots need basis/dates, retirement lots need verified inventory.
- Use one recursive exposure engine and one planner. Keep numeric coverage separate
  from evidence quality. Preserve unknown residuals, cycles, path/depth/vintage and
  persisted issues. Quote TTL is 900 seconds; caches never become historical marks.
- Immutable targets total 1 ±0.000001 and contain allocation/account/exclusion
  choices. Separate approved immutable policies own strict buy/sell/hold permissions,
  increments, floors, fees and freshness. Buying requires holding permission;
  restricted inventory requires review, never automatic liquidation.
- Contributions never sell; rebalance uses cash first on any valid date. REAL
  proposals need saved targets/approved policies. Pin inputs/algorithm and simulate
  cash/lots/value before saving. Lists stay compact; history is never repriced.
- Annual USD positive tax cost needs explicit ST/LT rates, matching year/environment
  and history through the planned date; reject future attestations. Losses never
  replenish allowance and saved plans never spend it. Block unsafe sales while
  retaining independently safe cash-funded suggestions. Household/IRA/spouse/DRIP/
  substantially-identical wash review is mandatory; no legal or savings guarantee.
- Actual performance needs dated checkpoints/flows and boundary marks. Household
  transfers require reviewed linked atomic legs, never inferred balance differences.
  Keep all conventional XIRR flows; complex nonconventional cases stay typed review.
  Risk requires actual session evidence, never weekday assumptions.
- Humans verify original research sources and rights. Acceptance is atomic/run-scoped
  and cannot register/reclassify securities or refresh market/fund caches. No
  scraping, forecasts, political scoring, monitoring or signals. Preserve exact
  issuer/entity/period/unit/definition/basis and independent specialist identities.
  News absence is NOT_REOBSERVED; original exact-class fund TOP_N is <=100,
  descending, without normalized weights or invented residuals.
- Corpus ingestion requires independent indexing permission, model/dimension/content
  compatibility and explicit keyword fallback. No automatic personal/broker
  embeddings. Plain bonds use SciPy cash flows; complex instruments stay unavailable.
- JSON success goes to stdout, errors to stderr: 1 input, 2 external, 3 blocked,
  4 internal. Incomplete outcomes retain typed issues.

## Acceptance limits

Synthetic tests establish development behavior only. Vanguard, Fidelity NetBenefits
and PNC remain PROVISIONAL; live FMP remains UNVERIFIED pending permission-cleared
real evidence and entitlements. Keep setup/human steps in [data sources](docs/data-sources.md).
No real documents or secrets are needed offline. Preserve the approved look-through
**PERFORMANCE EXCEPTION — NOT PASSED**, invalid CI evidence and fixed eight-workflow
reference/projection rules in [performance](docs/performance.md). No rebaseline or
new timing campaign is authorized by cleanup. Report local results as local evidence.
