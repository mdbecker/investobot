# Investobot project rules

## Current finite wrap-up scope

- `docs/PRD-mvp-wrap-up-2026-10-12.md` supersedes conflicting performance,
  campaign and evidence requirements below. Keep financial safety unchanged.
- Use exactly eight fixed representative workflows, one pinned reference
  (`d0940a12c44831095492efcd7091fb7b937ad6b3`), one warm-up and five batched
  samples. Confirm a >25% median regression with one complete repeat pair.
  Retire three-revision, stress/scaling, p95 and aggregate certification gates.
- Stop import optimization; retain its functional chronology, reconciliation,
  identity, isolation, atomicity and retry checks. Institution profiles and FMP
  remain unverified pending reviewed real evidence.
- Refactors use existing green behavioral tests. Red checkpoints apply only to
  missing behavior or reproduced bugs, never internal read counts/call ordering.
- Fuzzing is an explicitly requested agent activity with offline disposable
  replay and actionable reports; no quotas, novelty scores, providers or CI
  campaigns. CI may run fixed regressions only.
- Follow `fuzz/SKILL.md` for explicitly requested adversarial review. It is a
  development skill source, separate from bundled financial workflow skills.
- Keep generated evidence outside Git with documented retention. Never run
  untrusted PR code on a personal self-hosted runner. Complete the finite
  acceptance checklist and stop; no speculative framework or performance work.

## Additional verified lifecycle lessons

- Import/reconciliation chronology selects account history in SQLite before
  decoding snapshot payloads. Preserve every selected historical observation,
  fingerprint and source lexeme, including existing status behavior. Read fresh
  on every command; do not introduce cross-command caches or schema changes.
- Account-scoped inventory reads preserve normalized presence bits and exact
  ID ordering. Lot IDs remain globally unique: a missing local lot requires an
  indexed global ID lookup before acceptance. Keep protected historical lots,
  independent other-account cash and atomic collision rejection intact.
  Existing own lot IDs remain known within the writer transaction; avoid
  redundant global lookups after deletes, but refresh actual remaining rows.
  Identity membership is not permission to reuse stale financial lot values.

- Pure P05 performance fixtures may reuse verified immutable inventory only
  under SQLite query_only, total_changes and data_version guards. Verify every
  raw result independently and recheck full inventory/FKs before closing. Keep
  mutating and cache-writing fixtures on their original per-operation resets.
  External no-op SQL need not advance data_version; test actual committed
  mutations, including a committed reversal that leaves final values unchanged.

- Matched scaling evidence hashes each actual recipe/dimension slice. Do not
  inherit a stress hash when measuring medium or fourfold matched inputs.
  Freeze the current main comparator before an optimization; older historical
  optimization baselines are not the current target-branch comparator.
- Paired batch calibration targets 300 ms to leave headroom above the strict
  200 ms sample floor. All revisions/sizes share the count from the fastest
  warm-up. Normalize timings by that count; retain and reject short samples.
  A target margin is not a guarantee against arbitrary measurement noise.
  The earlier 400 ms target exceeded the nominal extended scheduling allowance
  before bulk work; preserve original evidence, strict floor and suite budgets.

- Absolute performance budgets use their specified workload sizes, separately
  from stress regression comparisons. Reuse verified medium scaling observations
  and 100k-chunk vector observations; require 21 samples for import p95. Reject
  missing or mismatched revision, runner and workload evidence.

- Dense conventional cash flows with one chronological sign change use a
  uniquely bracketed XIRR root without dropping records. Long nonconventional
  histories retain a typed complexity review. Statistical tolerances never
  round stored financial values or excuse missing flows.
- Benchmark fixtures use validated deterministic synthetic identities. Verify
  full native outputs before projecting incidental generated IDs/timestamps;
  preserve all financial, source, policy and relationship evidence. Report
  processed counts separately from recipe parameters and keep oracle work
  outside timed operations.

- Confirmed cash and adjusted lot effects must reconcile independently from
  position quantities. Later fixtures must preserve actual recorded lot IDs and
  cash, rather than inventing balancing changes to produce a desired return.
- Retry identity normalizes only financial decimal fields; identifiers and
  source strings stay exact. Precision collectors must distinguish financial
  scalar values from similarly named provenance structures.
- Artifact publication and managed-staging cleanup share a filesystem lock.
  Preview never creates a cleanup lock or removes files; ordinary user files,
  referenced artifacts and symlink paths are never cleanup candidates.
- Policy approval previews validate existing canonical references before opening
  a writer. Nested permissions use strict independent booleans and exact decimal
  strings; immutable versions retain only explicitly submitted fields.
- Household cash transfers require one explicitly reviewed paired command,
  matching currencies/environments and verified event ordering. Both cash changes
  and event legs commit atomically; household/account performance use the same
  durable links rather than inferring transfers from balance differences.
- Hybrid search filters canonical model/dimension/content compatibility before
  lexical ranking. Keyword-only retrieval remains the explicit fallback.
- Exhausted lots referenced by confirmed allocations remain historical rows;
  complete imports must not delete them. Missing positive remaining lots are
  discrepancies, not permission to replace confirmed inventory.
- REAL specific-lot sales require verified status, sourced broker lot identity,
  identity review evidence and explicit saleability. Missing fields are unknown.
- Financial lookups share security_identity.resolve for strong IDs and sourced
  aliases; ambiguous matches fail. Dashboard GET uses read_ledger and closes
  handles before responding, including missing/incompatible ledgers.
- Recovery integrity checks and logical fingerprints must load checksum-verified
  baked vec0 when a ledger contains derived vector tables; ordinary SQLite
  connections otherwise cannot validate or dump them. Recovery must include real
  corpus retrieval, not only a financial-table roundtrip.
- The standalone synthetic demo uses real HTML provenance and actual CLI commands.
  Do not strip source-cell metadata to make simulation pass; numeric collectors
  accept scalar financial leaves and preserve provenance structures separately.

## Verified implementation lessons

- Accept observations only with explicit REAL/SYNTHETIC source provenance.
  Propagate it to accepted financial rows; reject conflicting rows/accounts.
  Fictional fixtures state SYNTHETIC explicitly; parsing must never guess it.
- Legacy unapproved scenarios carry typed policy review issues; REAL inputs
  cannot use scenario generation to bypass approved trading policies. Gate on
  issue fields, never on warning wording.
- Harvest estimates use immutable approved policy identity, verified loss lots
  and sourced current replacement prices. Simulate both cash legs, preserve
  exact fee residue, and keep mandatory human wash review on conditional actions.

- Printed financial precision is source evidence: provide it explicitly in
  synthetic fixtures; never infer it from normalized decimal storage. Keep
  quantity, price and value coherent except in deliberate rejection cases.
- Native analytical extensions must actually load during Docker builds. The
  pinned sqlite-vec ARM64 wheel is unsuitable here; compile the checksum-pinned
  official amalgamation in the Docker builder, then verify the runtime binary.
- Research completeness requires all requested specialty tasks. Filter compact
  issuer metadata before loading immutable packages; unrelated evidence must
  not break a selected report. Historical coverage is not current coverage.

- Schema 1 identity includes the foundation migration checksum, not just SQLite
  user_version. Legacy schema 1 must remain byte-preserved and rejected.
- All application database connections hold the shared restore lock until close;
  close write handles before announcing completion to local HTTP clients.
- Disposable benchmark builders must insert parent accounts before observation
  rows and query plan_runs. Keep foreign keys enabled during fixture creation.
- Scale Decimal calculation contexts to supplied financial magnitudes. A fixed
  100-digit context can erase real low-order cash and value residues.
- Check unknown permissions before iterating eligible trades. An empty rule map
  is unknown eligibility; an empty proposal does not establish readiness.
- Tax inventory and sale analysis use remaining adjusted basis, including when
  original basis is unknown. Final sales conserve the exact remaining residue.
- Historical CLI exposure reads accepted immutable vintages before touching a
  market client. Source publication/observation dates and hashes survive paths.
- Align risk histories on every requested session; silently dropping missing
  rows changes the modeled period and must return a typed coverage blocker.
- Preserve research evidence lexemes and native specialist hashes. Envelope
  issuer labels cannot override reviewed canonical issuer identities.
- The plain bond runtime uses SciPy cash flows. Explicit complex instruments
  remain unavailable; fixed redemption scenarios do not price embedded options.

## Active specification and work order

- The historical additive specification is
  `docs/PRD-performance-ai-fuzz-2026-10-10.md`; the October 12 wrap-up controls
  current measurement and fuzz scope. Preserve financial behavior.
- Fixed performance measurements use offline disposable Docker fixtures and
  candidate and one reviewed reference. Archived timings are evidence, never a
  cross-machine comparator. Check native engine/image ARM64 and same-runner facts.
- Exploratory AI campaigns require explicit human invocation after performance
  acceptance. CI may test the fixed harness and promoted regressions, but must
  never generate campaigns, launch providers or publish issues automatically.

- The active rebuild specification is `docs/PRD-unified-mvp-2026-10-10.md`.
  Historical PRDs/addenda remain unmodified reference documents. Conflicting
  release-specific architecture decisions are superseded by the unified PRD.
- This checkout starts at `5120897e9e5a314ad50fb242ad1496d976549a92`, after fund
  diligence schema 10, rather than the attachment's earlier review baseline.
  Preserve existing fund diligence and all specialist research behavior as well.
- New behavior and confirmed bugs require observed test-only red checkpoints
  before implementation. Pure refactors use existing green behavioral tests.
  Minimum B01–B66 is not the complete specification. Do not silently replace
  success workflows with blocked-only examples or leave fixture facts unused.
- Keep `main`. Conventional commits only. No remotes, fetches or pushes.
  Coordinator commits red/green checkpoints; agents never commit.
- Independent agents own separate files/modules. Coordinator owns shared models,
  ledger, schema, central CLI, descriptors and integration. Announce readiness
  and freeze test writes before checkpoint verification. Tests must match the
  exact committed tree; no skips, xfails or artificial internal mocks.
- All execution, dependency resolution, lint and tests run in Docker. Install
  nothing on the host. Read/edit files and Git operations may run on the host.
- Build with `uv.lock` copied before locked sync. Exclude host `.venv`, private
  data and SQLite `.db`, `-wal`, `-shm` files from build contexts. Dependencies
  live at `/opt/venv`, never in a volume nested within the project bind mount.
- Offline CI uses disposable containers, `INVEST_PROMPTS=/data/prompts`, no
  private ledger volume and `uv run --locked`. Mounted-source development may
  use `--no-sync` after the locked image is built. Ruff always receives
  `--config pyproject.toml`. Local evidence is not a remote CI result.

## Authoritative facts and financial safety

- Single local Python app; SQLite is the sole writable source of financial
  truth. No ORM or service framework. Decimal financial values are exact plain
  normalized strings; never normalize identifiers as numbers or lose precision.
- New normalized storage design starts at schema 1 on an empty ledger. Reject
  old development schemas without changing them. Never reset private databases.
  Future migrations are transactional and checksum-tracked with a verified
  pre-migration backup; historical blanket migration prohibitions are obsolete.
- SQLite writer settings: foreign keys ON, WAL, synchronous FULL, busy timeout
  5000. Related writes share one transaction. Backup uses SQLite's online API,
  verified referenced artifacts, owner-only archives and atomic publication.
  Restore stages/validates first and requires explicit confirmation.
- DuckDB is ephemeral and read-only over consistent exports/immutable Parquet.
  SQLite manifests identify artifacts and hashes. No persistent analytical DB.
  sqlite-vec is a rebuildable index; canonical chunks/vectors remain in SQLite.
  Extensions are pinned and baked into Docker; no implicit runtime downloads.
- Never place trades, accept brokerage credentials, persist raw account HTML,
  invent identities, lots, basis, prices, classifications or cash coverage.
  Only explicitly confirmed idempotent commands mutate accepted facts.
- Unknown never means zero, current, complete or safe. Return typed issues with
  explicit calculation/proposal/review gates; never parse warning prose to gate.
  Success is JSON stdout; errors JSON stderr with codes 1 input, 2 external,
  3 inconsistent/blocked state, 4 internal. Incomplete analyses return outcomes.
- REAL/SYNTHETIC provenance is mandatory. Mixed inputs cannot produce actionable
  proposals. Research, simulations and backtests cannot change holdings, marks,
  caches, confirmed events or financial fingerprints.
- Source and import timestamps are distinct. Positions/lots/cash coverage and
  chronology are independent. Old observations cannot erase later confirmed
  activity; date-only same-day ambiguity requires verified ordering. Partial
  imports never delete unobserved inventory. Accepted account settings remain
  authoritative; observations cannot silently change them.
- Canonical identities use sourced strong IDs and reviewed ticker aliases.
  Conflicting strong IDs never merge by ticker/name. Reuse one resolver.
  Existing OTHER classification requires sourced preview and explicit confirm;
  registration cannot bypass classification controls.
- Stable verified lot identity and remaining adjusted basis survive partial
  sales; exact final residue is conserved. Unknown executed lot selection never
  becomes FIFO. Fees remain separate from gross activity prices. Activity IDs
  make identical repeats no-ops and conflicts atomic errors. Executions do not
  become portfolio valuation marks. Unknown source precision blocks acceptance.
- Never aggregate currencies without an FX model. Quote cache refresh never
  changes canonical marks or quantity freshness. Keep 900-second quote TTL
  distinct from day/week dataset TTL; caches are not historical evidence.
- Actual performance requires complete dated checkpoints/external cash flows.
  Household linked transfers net internally; reinvestment is not a deposit.
  Missing flow-boundary marks block TWR. Current-weight risk/backtests are
  hypothetical, with cash/fee/dividend assumptions and coverage disclosed.
- Targets are immutable versioned fraction allocations totaling 1 ±0.000001.
  Approved trading policies are separate from targets; buy/sell permissions are
  independent. Same-account confirmed cash only; explicit increments, floors,
  minimum notionals, freshness and cadence. Unknown fees require review.
- Default contribution-only monthly; quarterly rebalance March/June/September/
  December only above 5 percentage-point drift. Exceptions are saved approved
  policy versions, never bypass flags. No automatic individual bond trades.
- Annual USD positive estimated tax-cost allowance uses confirmed taxable sales
  and explicit ST/LT rates. Losses do not replenish it; saved plans do not spend
  it. Unknown rates/year-to-date coverage block taxable gain-sale proposals.
  Household IRA/spouse/DRIP/substantially-identical uncertainty requires review;
  never certify wash-sale safety or guaranteed tax savings.
- Plans are immutable, source/policy/manifest/algorithm pinned and stale at read
  time after actual changes. Authoritative simulation validates cash, lots,
  values and total before save. List/compare use compact projections, not full
  baselines/details; historical reports never recalculate from fresh prices.
- Look-through preserves unknown residual, path provenance, cycles, depth limit
  and holdings vintage/freshness. Do not normalize partial holdings or backfill
  historical constituents with future knowledge. Issuer mappings are sourced.

## Research, skills and local operation

- External agents research; humans review original sources/rights; Investobot
  validates strict JSON and stores immutable evidence. Structural validation
  cannot establish source truth, permissions or legal conclusions. No scraping,
  FEC/SEC clients, political scoring, forecasts, monitoring or trade signals.
- Preserve specialty validation and independent trusted skill/hash identities,
  including the existing fund diligence family. All acceptance inserts are
  atomic, run-scoped FKs prevent cross-run evidence. Preview/reads must not
  create the selected ledger. Only explicit import confirmation writes research.
- Named contributions need independently reviewed local rights policy; agent
  rights assertions and `--yes` cannot authorize restricted use. Distinguish
  executive, employee and verified corporate PAC evidence. Fictional fixtures
  only; no private donor fields, raw pages or unsolicited personal information.
- Earnings compare exact definition/basis/unit/entity/scope/period/duration;
  missing/nonpositive baselines do not imply growth. No invented quarterization,
  adjusted/GAAP mixing or FX. Source locators are narrow, credential-free and
  issuer-compatible. Research cannot register/reclassify canonical securities.
- News stable event keys, disputed facts, explicit cited closures and bounded
  baseline chronology remain authoritative. Absence is NOT_REOBSERVED, never
  resolution. Terminal observations tombstone older active records; inherited
  provenance/staleness and overlapping evidence-category counts stay explicit.
- Competitive comparisons need sourced overlap and exact comparable metrics;
  no investment rankings/scores. Insider evidence needs exact issuer/owner/
  filing/person association, effective correction links, separate P/S vs other
  codes, no inferred venue/intent and no cross-run reconstructed ownership.
- Fund diligence needs original SEC registrant/series/exact-class identity;
  exact-class fees/distributions, descending TOP_N <=100, no normalized weights
  or invented residual. Never update fund-holdings/market caches from research.
- Corpus indexing requires source permission and no automatic broker/personal
  embeddings. Explicit authorized adapters only; model/dimension compatibility,
  float32 normalized vectors, immutable revisions and textual fallback required.
- Portable skills orchestrate discovered CLI contracts; they do no financial
  arithmetic. Prompt text is copied, never executed. Install only explicitly
  to project `.agents/skills` or `.claude/skills`; reject traversal, symlinks,
  nonregular destinations and unsafe overwrites. Preserve recoverable defaults.
- Dashboard is thin and local. Native bind must be loopback; Docker may bind
  internally only with host-loopback publication. Shared domain outputs drive
  rendering. Same-origin checks/body limits apply to every write route; they
  are not authentication. Prompts stay at `/data/prompts` beside Docker ledger.
- Institution adapters remain PROVISIONAL without reviewed real anonymized HTML
  for Vanguard, Fidelity NetBenefits and PNC. FMP live entitlement is separately
  UNVERIFIED until human validation. Synthetic acceptance ships development
  preview only. No secrets are needed for offline acceptance.
- Benchmark only reproducible disposable synthetic ledgers/corpora. Record
  hashes/hardware/timings/sizes; never invent measurements. Exclude fixture
  preparation/builds from measured domain operations. Recovery and synthetic
  workflow demonstrations remain required gates.
- Document actual behavior clearly and concisely, including setup/manual gates
  and outstanding scope. See `docs/implementation/unified-mvp-status.md` for
  context and `docs/implementation/wrap-up-status.md` for current acceptance;
  do not describe unimplemented requirements as complete.

## Performance addendum harness lessons

- Fuzz scenarios are allowlisted JSON data, never executable instructions.
  Use fresh offline Docker subprocesses, independent exact oracles and replayable
  seeds/minimized examples. Fixed fixtures do not authorize agent exploration.
- Resource failures remain environmental/unresolved. Preserve original failure
  reports and actual exit codes; one reproduction cannot establish a confirmed
  bug or regression. Report missing oracle evidence as a failure.
- Historical metric benchmarks call the single adjusted-series calculation,
  preserving its source/cache evidence; whole-fund comparison is a separate case.
- The user's native M4/ARM64 scope supersedes x86 requirements in the preserved
  performance PRD. Check both engine and image architectures; do not certify
  emulated measurements. Current vector fixtures are prepared synthetic inputs
  for CPU retrieval, with no embedding provider or GPU acceleration claimed.
- Build each case/revision/dimension template once, close every SQLite handle,
  checksum its complete tree, and copy it into a fresh worker before timing.
  Never inherit live connections or share writable fixture volumes. Include
  hydration/copy time as preparation evidence; remove only owned fixture volumes.
- On Docker Desktop, controller containers mount the engine's
  `/var/run/docker.sock`, not the macOS user-socket path. Never mount private
  application volumes into the controller or observation workers.
- Scaling evidence distinguishes processed record growth from surrounding ledger
  cardinality. Never claim more timed records from unrelated recipe dimensions.
  Single quotes remain measured bounded controls; they cannot establish a 4x
  record-growth ratio. Selected look-through counts exclude unused vintages.
- Native specialty scaling expands distinct fictional evidence within reviewed
  schema limits, retaining insider correction links, exact fund weight coverage,
  and comparable metric identities. Keep scale-one fixtures byte-equivalent in
  content for historical revision comparisons.
- Specialty output coverage checks actual returned counters and row identities,
  not just stored run totals. Fund summaries do not read holdings; keep them
  fixed-size controls rather than claiming holdings-growth coverage.
- Publish paired-run evidence atomically after each completed case/scaling pair.
  Interruptions, budget and cleanup failures must retain completed measurements
  and the original failure; partial reports never establish full acceptance.
- Profile measured offenders before optimizing. Import acceptance uses call-local
  inventories; update indexes after actual writes and refresh lots after guarded
  deletes. Keep ambiguity checks, protected historical lots, exact Decimal
  accumulation order and partial basis; never cache across commands.
