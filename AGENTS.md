# Investobot project rules

## Verified implementation lessons

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

## Active specification and work order

- The active rebuild specification is `docs/PRD-unified-mvp-2026-10-10.md`.
  Historical PRDs/addenda remain unmodified reference documents. Conflicting
  release-specific architecture decisions are superseded by the unified PRD.
- This checkout starts at `5120897e9e5a314ad50fb242ad1496d976549a92`, after fund
  diligence schema 10, rather than the attachment's earlier review baseline.
  Preserve existing fund diligence and all specialist research behavior as well.
- Follow WP00's global red gate: specify every new/changed behavior across all
  packages, observe intended failures, record evidence and commit test-only red
  before any production, schema, dependency or skill implementation changes.
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
  hashes/hardware/timings/sizes, never invent measurements or make CI wall-clock
  limits. Recovery and synthetic workflow demonstrations are required gates.
- Document actual behavior clearly and concisely, including setup/manual gates
  and outstanding scope. See `docs/implementation/unified-mvp-status.md` for
  current evidence; do not describe unimplemented requirements as complete.
