# Investobot — Unified MVP Rebuild PRD

**Status:** Implementation specification · **Date:** 2026-10-10 · **Baseline:** [`mdbecker/investobot`](https://github.com/mdbecker/investobot), commit [`d31316c8`](https://github.com/mdbecker/investobot/commit/d31316c8fbda0c2a5aa27a989c1341bcd1d57a31) · **Priority:** Complete before using Investobot with real portfolio data.

**Dependencies (assumed complete):** The existing Investobot MVP and historical PRDs/addenda through v2.9, including account snapshots, target/plan/report commands, five research skill families, and Docker/BDD infrastructure. This **single PRD supersedes prior active architecture and behavior decisions where they conflict**, while preserving the historical PRD files as reference. No real user data exists: replace the current disposable schema instead of building a pre-release migration. Once this MVP is used with real data, schema migration and backup guarantees are mandatory. Baseline source review: [code review dated 2026-10-10](https://github.com/mdbecker/investobot) (29 findings); the implementation must resolve all findings F01–F29 and the subsequent database/agent-workflow requirements in this document.

## 1. Outcome and boundaries

Build a **single-user, local-first, agent-operated, human-executed** investment toolkit that safely ingests supplied broker HTML, maintains trustworthy portfolio and tax history, computes actual performance, proposes infrequent tax-conscious trades, discovers/screen funds, resolves underlying company exposure, researches top portfolio issuers, and compares candidate allocations in historical simulations. The agent gathers/evaluates public evidence, invokes discoverable CLI tools and explains results; **Python owns every financial calculation and enforceable policy**. Every material input/output is source-dated, coverage-aware and reproducible.

**In scope:** Everything in §§2–6, including seven portfolio-oriented agent skills, preservation of the five existing specialist research skills, on-demand local analytics, a small semantic-search capability, backups, schema migrations, safety controls, tests and canonical docs.

**Out of scope:** Broker login/API credentials, direct order placement, autonomous trading, brokerage scraping, multi-user service/cloud synchronization, tax filing or legally certifying wash-sale safety, options/margin/crypto trading, optimizer frameworks, live news ingestion daemons, cloud vector databases, persistent separate analytical databases, FX conversion, and claims that third-party research is deterministically true. Handle existing individual bonds via explicit analysis only; do not add automated bond trading. Do not implement a generic plugin system, ORM, microservices, event bus, agent runtime, or migration from development schemas 0–9.

### Non-negotiable product rules

1. No trade or target proposal can modify actual holdings, cash, lots or accepted source observations. Only explicitly confirmed, idempotent commands can change authoritative facts. Human executes every broker trade.
2. **Unknown is never zero, recent, complete or safe.** A missing field/coverage/price/rate must be represented as `null` or typed unavailable, with a machine-readable issue; downstream tools do not quietly fill it.
3. Separate **actual portfolio performance**, **hypothetical backtesting**, **public research**, **accepted broker facts**, **simulated executions** and **confirmed executions** in models, command names and reports.
4. Canonical identity is account+security+stable tax lot/event ID, not current ticker or mutable HTML row content. Do not infer security equivalence from a shared ticker if strong IDs conflict.
5. All calculations use `Decimal` for money/quantities/gain/tax math; persisted and CLI financial values use normalized decimal strings. Only historical statistics/solver math may use float, labeled as such. No floating-point tax arithmetic.
6. Every report pins its financial state, policy version, data manifest IDs, algorithm version, and availability/coverage diagnostics. Re-running identical pinned inputs gives identical substantive results; timestamps/opaque generated IDs are excluded from this equality.
7. Local privacy: no raw brokerage HTML, credentials, private full report data, or contribution identities in Git, logs or telemetry; do not silently call external embedding or research APIs.

## 2. Architecture and decisions (do not revisit during implementation)

**Runtime:** Python 3.12+, Typer, Pydantic v2, `Decimal`, stdlib `sqlite3`, existing NumPy/Pandas/SciPy where needed, and **DuckDB installed as an on-demand analytical dependency**. Docker Compose stays the sole supported developer/test execution path; local native CLI remains optional. A single Typer CLI (`invest`) and existing loopback-only dashboard share pure domain functions. No persistent background worker; agent orchestration stays outside the application.

**Storage:**

- **SQLite is the only authoritative writable database**, containing accounts, securities/aliases, accepted observations, confirmed activities, remaining tax lots, cash/valuation checkpoints, year-specific tax assumptions, allocation targets, proposals, research evidence metadata, document chunks, embedding metadata and dataset manifests. Replace generic `(id, data JSON)` financial tables with typed relational columns, foreign keys, unique constraints and well-chosen composite indexes. Keep JSON only for immutable original normalized payloads, variable source evidence and plan detail bodies.
- Enable `foreign_keys=ON`, `journal_mode=WAL`, `synchronous=FULL`, `busy_timeout=5000` on each writer connection. All logically coupled writes are one transaction. Never store the live SQLite WAL database in a network/cloud-sync folder or copy a live `.db` in place to back it up.
- Store financial decimal values as canonical exact decimal `TEXT` validated at the domain boundary; indexed identifiers/dates/currency/status are typed scalar columns. Convert to DuckDB `DECIMAL` in analytical queries. Do not use SQLite `REAL` for authoritative amounts.
- **DuckDB is an ephemeral analytical connection**, reading SQLite through a pinned SQLite extension or from a consistent SQLite-export view, plus immutable local Parquet data. No second writable source of portfolio truth and no required persistent DuckDB database file.
- **Parquet is only for large immutable public observation/history partitions** (e.g., dated fund constituents, price histories, historical fundamentals, backtest source tables). Use it when bulk datasets become material, not for a handful of transactions. Never generate many tiny files. SQLite's `dataset_artifacts` manifest records kind, provider, observed-at, effective/as-of dates, coverage, schema version, SHA-256, relative path, data environment and replacement lineage. Write+fsync+atomically rename artifact first, then commit manifest reference; orphaned artifacts are harmless and collectable.
- **Semantic search:** SQLite FTS5 for text plus `sqlite-vec` as a **rebuildable vector index**; canonical chunk metadata, text, vector bytes and model ID remain in SQLite. No LanceDB, PostgreSQL, Turso, hosted vector DB or persistent DuckDB HNSW in the MVP. Bake the DuckDB SQLite extension and sqlite-vec binary into the **offline-capable** Docker image at build time, pin versions/checksums, and validate on CI-supported Linux amd64/arm64. No implicit extension download when an analysis runs. If vector functionality is unavailable, textual search still works and returns a typed vector-unavailable status. Embeddings are generated only by an explicitly selected, user-authorized agent/model adapter; no implicit remote calls or default third-party model subscription. A later LanceDB index may be evaluated only against measured performance, outside this MVP.

**Lifecycle:** The first MVP install creates **schema version 1 of the new design** on an empty ledger (not an in-place migration from old schema 9). Add a simple transactional `schema_migrations(id, checksum, applied_at)` runner for **future** upgrades, using additive/rebuild-where-needed SQLite patterns and pre-migration verified backup. A legacy DB yields an explicit unsupported-development-schema error and **is never automatically removed**. No backward-compatibility adapters or dual old/new writes.

**Backups:** `invest db backup`, `verify`, `restore --dry-run`, `restore --confirm`, `migrate` and `status` cover the SQLite backup API, all immutable referenced artifacts and optional search indexes (indexes may be rebuilt). The CLI writes a standard-library `tar.gz` archive with a file/size/SHA-256 manifest, restricted owner-only file permissions (`0600`) and atomic rename. The user stores an encrypted off-device copy using the laptop's existing encrypted-backup tooling; do not introduce a new app-level cryptography stack. Backup copies SQLite using its online backup API, verifies `integrity_check`, `foreign_key_check`, artifact hashes and logical invariants, then atomically publishes the archive. Restore validates a separate staging location, closes writers, and requires explicit confirmation before replacement; never overwrite a healthy current ledger implicitly. Back up after each accepted broker import or confirmed activity and allow scheduled invocation by the laptop's existing scheduler. Automatically test restoration using disposable data. `db status` reports latest verified backup age; missing backups block destructive migrations, not read-only analysis.

**Research provenance:** Keep the existing validate → preview → human approve → immutable import lifecycle. Share one tiny research-run/artifact persistence envelope while retaining separate domain schemas for news, political, earnings, competitive and insiders. Every research result states what was checked, when, for which identities, and what remains unknown. No political ideology/rating scores and no implication that legally similar funds are tax-approved substitutes.

### Data flow

```text
Supplied HTML / manual confirmations → validated observations & events → SQLite source of truth
External FMP / public evidence       → versioned source artifacts + SQLite provenance
                                       ↓
                              Pure financial engines
             performance · tax · trading policy · look-through · backtest
                                       ↓
                         Discoverable JSON CLI and reports
                                       ↓
                 Portfolio workflow agent skills + human approval

On-demand DuckDB reads consistent SQLite exports + immutable Parquet.
FTS5/sqlite-vec indexes are derived from SQLite's stored research chunks.
```

## 3. Common contracts and default policies

### 3.1 Shared input/output contract

- Retain `invest tools list`, `tools describe TOOL`, `schema`; expose each tool's actual CLI parameters, authoritative Pydantic JSON schema, read/cache/write mutation scope, privacy/environment requirement, output contract and example from **one registered tool descriptor**. Remove parallel handwritten command descriptions and stale skill copies of JSON schema. All new inputs reject unknown fields unless a deliberate extensible evidence field is specified.
- CLI success is JSON stdout; errors JSON stderr and existing exit codes `1` input, `2` unavailable external data, `3` inconsistent/blocked state, `4` internal error. Domain-level incomplete/blocked analyses should **return structured outcomes rather than masquerading as CLI failures**.
- Common result: `status: AVAILABLE | PARTIAL | UNAVAILABLE | BLOCKED | REVIEW_REQUIRED | READY_FOR_HUMAN_REVIEW`, typed `issues: [{code, severity, affected_ids, blocks_calculation, blocks_proposal, blocks_execution_review, message}]`, `coverage`, `as_of`, `sources`, `manifest_ids`, `assumptions`, `environment`. Boolean flags control gates; **never inspect English warning substrings**.
- `data_environment: REAL | SYNTHETIC` is mandatory on accepted portfolio observations, sourced market data, caches, analytical runs and saved proposals. Reject mixed REAL/SYNTHETIC inputs for any human-actionable proposal; allow fully synthetic offline scenarios. A read-only sandbox explicitly mixing data is labeled `SYNTHETIC_EXPERIMENT` and may never receive an actionable state.
- `date` means an ISO 8601 calendar date with stated observation granularity; precise events use timezone-aware ISO 8601 timestamps. Do not infer source freshness from import or retrieval time. For date-only snapshot/event conflicts on the same day, block authoritative reconciliation until source ordering is explicitly established.
- Time-dependent commands accept explicit `--as-of`, date range, policy version and/or frozen data-manifest IDs; tests use fixed dates. Current time defaults are allowed for interactive convenience but must be persisted in the generated run.

### 3.2 Default investment policy

Represent a **versioned, human-approved policy** separate from a target allocation. Policy contains per-account buy/sell eligibility, allowed securities, lot/fractional increments, cash reserves, minimum trade amount, allocations, loss-harvest preferences, account location restrictions, tax-year budget/rates, calendar/trade limits and exact valuation freshness requirements. The policy is explicit input, never reconstructed from prose.

**Default policy once an account is configured:**

- **Monthly contribution-only** is the normal operation; ordinary executed trading occurs at most once per account per calendar month unless the human selects an override with a reason. An unconfirmed plan does not consume this cadence.
- **Quarterly rebalance only** in March/June/September/December and only if the largest absolute asset allocation deviation exceeds **5 percentage points**; outside those months, no automatic sale proposal. Cash contributions are applied to the most underweight permitted assets first and sales are avoided while cash can meaningfully reduce drift.
- Trade only in explicitly eligible accounts. An allowed **BUY list is not a restriction on selling an existing holding**; sale permissions are separately modeled. Block any action for which buy/sell permission or execution increment is unknown. For configured fractional fund trading, use the account-specific increment (never silently assume whole shares). Default minimum notional **$25** and default minimum account cash reserve **$0**, each configurable; always respect a higher explicit cash floor.
- No proposed taxable **gain-realizing sale** without a known remaining **annual estimated tax-cost budget** and explicit ST/LT marginal-rate assumptions. Default annual tax budget is **$0**, not unlimited. Tax-deferred/free sale planning does not consume this budget. One-off overrides are separate saved policy versions; a CLI flag must never silently bypass policy.
- Minimize, in order: blocked/illegal trades; taxable sales; estimated positive tax cost; number of trades/turnover; absolute target drift. Use a deterministic, documented cash-first/retirement-first/known-lot heuristic with stable tie-breakers and exact post-simulation validation. **Do not implement MILP, stochastic optimization, or claim global optimality** for the MVP. When constraints prevent tolerance, return honest residual drift and feasible alternatives rather than forcing a sale.
- Generated trading proposals always assume **no broker execution** and require human approval. If fees are unknown, show fee estimate as unknown and mark for review; never claim zero real fees. No implicit quote refresh changes account marks.

### 3.3 Testing rule that overrides normal implementation order

**Mandatory global BDD red phase: write every new or changed behavior scenario, step definition and deterministic fixture for ALL work packages before changing ANY production code.** First establish that the existing baseline suite is green on the pinned commit. Add and run the complete new BDD suite: each new scenario must fail for its **intended unmet requirement**, not for syntax errors, misconfigured fixtures, broken test harness or missing dependencies. Record the failing scenario IDs, diagnostics, commit hash, and a red test-only commit. Do not hide failures with `skip`, `xfail`, conditional expectations or mocked internal collaborators. **Only after the entire specified BDD suite has demonstrated valid red outcomes** may implementation start. Implement packages in dependency order, turning scenarios green; each green release gate runs the existing and new full suite, Ruff and Docker integration tests. No code may be committed as a claimed passing stage if its associated scenarios are not green. Tests use `Given / When / Then`, observed CLI/domain behavior, real temporary SQLite files and fake only external market/browser/network boundaries.

## 4. Work packages — small ownership boundaries, one PRD

Work packages below are the only required delivery breakdown, not separate PRDs. All scenario definitions are written **together in WP00's global red phase**. Other packages contain production implementation and any test refinement necessary to correct behavior, never a first attempt to specify untested requirements.

### WP00 — Global behavioral specification and red baseline · P0

**Owns:** `tests/features/mvp/**`, matching pytest-bdd steps and fixtures, fixture provenance inventory, red test manifest. No `src/`, `skills/`, runtime dependency or product-schema edits in this package.

- Write complete independent BDD scenarios for WP01–WP12 (examples in §5) covering positive, negative, missing-data, idempotency, privacy, backup/restore, accounting, tax, planning, search and multi-step agent workflows. Place scenarios by user domain, **not release version**. Existing functional behaviors that remain valid get explicit regression cases.
- Use small invented brokerage HTML examples, synthetic dated market datasets, modeled tax lots/cash flows, generated artifacts and pinned research evidence. External HTTP/agent browser calls may be fake; SQLite, CLI transactions, serialization, DuckDB/Parquet where used, and restore paths must be real in disposable containers. Agent skill acceptance runs each documented CLI sequence through a **scripted test driver** with captured input/output; actual LLM/browser compliance is an additional manual smoke test, never an assumed deterministic CI result. Prepare fixture Parquet files in advance rather than importing unavailable production dependencies during the global-red stage.
- Run all newly defined scenarios before touching production; log expected vs observed failures. Preserve the existing 5 specialist-skill behavior checks and existing CI tests.

**Done when:** Baseline green; the new BDD suite is valid, executable and demonstrably red for every unmet requirement; test-only red checkpoint committed and reviewed. **All subsequent WPs depend on WP00.**

### WP01 — Authoritative SQLite schema, recovery and storage interface · P0

**Owns:** new `db.py`, `migrations.py`, `backup.py`, SQL/schema definitions, data manifest/storage adapter and DB-specific BDD steps. Other packages do not edit migration DDL; request contract additions before WP01 is closed.

- Fresh normalized schema: `accounts`, `securities`, `security_aliases`, `snapshot_observations`, `position_balances`, `cash_balances`, `tax_lots`, `activities`, `activity_lot_allocations`, `valuation_marks`, `external_cash_flows`, `tax_policy_versions`, `targets`, `target_versions`, `plan_runs`, `research_runs`, `research_artifacts`, `document_chunks`, `embeddings`, `dataset_artifacts`, `schema_migrations`. Keep optional domain evidence fields in canonical JSON columns. Materialized current balances are checkpoint projections, **not independent sources of truth**.
- Define FK/unique/date/status/check constraints and indexes for `(account, security)`, `(account, effective_date, event_id)`, lot identity, snapshot source chronology, observation dates, research `(issuer, kind, as_of)`, target versions and manifest hashes. Do not add speculative indexes; replace repeated full-table `.rows()` scans in active queries with bounded indexed SQL, prove main query plans and set import/report baseline benchmarks.
- Implement WAL/FULL, consistent read transaction snapshots, future ordered migrations, online backup, integrity and FK verification, archive/restore, safe atomic staging and tested orphan-artifact cleanup. Persist a small storage schema version/manifest hash in every saved calculation. Guard a nonempty old-development database without reset.
- Ensure simultaneous writer processes serialize or fail clearly; a reader must never see half an accepted batch. Backups remain valid during concurrent reads/writes and after abrupt process termination.

**Depends on:** WP00. **Done when:** All durability, constraints, future-migration and recovery scenarios pass; no live-data reset path exists; an actual archive restores byte-valid referenced data and logically correct balances.

### WP02 — Broker ingestion, provenance, identity and deterministic portfolio ledger · P0

**Owns:** parsers, identity/reconciliation and account-event state logic (`ingest.py`, `identity.py`, `ledger.py`, accounting-event helpers), Pydantic financial observation models. No changes to analytical, tax or research engines.

- HTML is **candidate evidence**, never automatically accepted state. Institution-specific adapters only for verified patterns; generic parsing must select unambiguous account/holdings/lot tables, detect duplicates/summary tables, preserve cell provenance, reject guessed identities, and never persist raw HTML. Ship representative **redacted, human-supplied** golden tests for Vanguard, Fidelity NetBenefits and PNC before describing those adapters as verified. In their absence, mark institution support `PROVISIONAL` and require manual review, not silent success.
- Typed freshness **per positions, lots and cash**, with source date/time, observation coverage (`COMPLETE | PARTIAL | UNKNOWN`), source hash, imported-at and validation issues. `source_timestamp` is typed, not unconstrained text. Unknown cash must not mean zero. Reject materially inconsistent quantity × unit price versus reported market value using each source field's **displayed precision**: allowable rounding difference is `max(one currency minor unit, abs(quantity) × half the displayed price unit + half the displayed market-value unit)`. Unknown price precision blocks acceptance until verified, and the observed discrepancy is always reported; never silently rewrite values.
- Stable canonical security identity uses CUSIP/ISIN/FIGI with explicit conflict rules and sourced ticker aliases; all lookup paths share the same resolver. Lot identity uses verified broker lot ID or an explicitly reviewed `(account, security, acquisition date, immutable acquisition reference)` mapping. Unmatched mutable lot rows stay unresolved and **unsaleable**. Store `remaining_quantity` and **remaining adjusted cost basis** (including documented adjustments), plus optional original fields. Partial sales reduce both exactly, with final-sale residue handled by exact-basis reconciliation, never recreated as duplicate lots.
- Confirmed activities are immutable, event-dated, uniquely identified, idempotent and applied atomically. Supported cash/distribution events include external deposit/withdrawal, dividend, interest, reinvestment, fee, split, return of capital, buys and specific-lot sells; define typed amount, direction, tax impact and lot handling. Unsupported transfers and unknown source semantics block acceptance rather than guessing. Account-to-account household transfers have linked legs and cancel for household performance; do not infer missing transfers from quantity differences.
- Implement the read-only `portfolio check` preflight for state readiness and domain-specific completeness (positions, cash, lot history, marks, environment, identity, tax and trading policy), returning typed blockers and next human actions. Accept an observation only if it cannot erase a later confirmed event. Older observations remain archived but **cannot replace current authoritative balances**; same-day ambiguous ordering blocks acceptance. A later full broker observation reconciles all intervening events against quantity/cash/lot expectations before replacing a checkpoint. If inconsistent, return explicit discrepancies and require a human-corroborated correction event; do not auto-create a balancing trade or overwrite an event. Partial observations never delete absent positions/lots. No new position's value is fabricated as `0` just because a post-activity quote is absent—valuation becomes unavailable until marked.

**Depends on:** WP01. **Done when:** A full import → reconcile → accept → record event → reimport lifecycle cannot double-count/erase holdings, mutate confirmed execution prices, fabricate value or lose lot basis; unverified pages give actionable review issues rather than false confidence.

### WP03 — Public market evidence, immutable dataset snapshots and DuckDB analytics · P0/P1

**Owns:** `market.py`, provider adapters, Parquet artifact writer/reader and `analytics_store.py` (DuckDB); no trading or tax logic. Complements WP01 manifests without editing ledger DDL.

- Keep **FMP** as the only MVP structured market-data provider. Validate actual response contracts for quote, dividend-adjusted historical prices, ETF/fund holdings, fund metadata and security profile with offline schema/contract fixtures. Execute a clearly marked **manual live-provider acceptance gate** using the user's own entitled credentials before claiming real-data readiness. If live validation is unavailable, provider status stays `UNVERIFIED` and no real-world-ready claim is permitted. No fabricated prices or constituents.
- Capture provider, retrieval time, underlying effective/as-of time, type, frequency, coverage, identifier mapping, synthetic/real environment, licensing limitations, source fingerprint and missing/unresolved rows. Split quote freshness from holding quantity freshness. Retain immutable historical observation vintages rather than treating expiring cache data as history. Use TTL caches only as optimization; historical analysis must select **pinned** records.
- Provide `data snapshot|list|verify` domain operations that pin, enumerate and hash-check complete source manifests. Small current data can remain in SQLite; large price/constituent/fundamental histories are Parquet immutable batches registered in WP01's manifest. DuckDB reads a consistent ledger export and Parquet for expensive scans; it may spill to local temporary disk, and must close/release locks on exit. Never let analytical jobs write to authoritative ledger tables. Provide deterministic dataset selection by date and content hash, including unavailable point-in-time historical holdings.
- Never use a fund's currently published constituents to pretend to know its constituents at an earlier backtest date. Do not infer total return from unadjusted close without verified distribution/split handling. Source records in synthetic/real environments cannot be cross-used for actionable plans.

**Depends on:** WP01; independent of WP02's event logic. **Done when:** Identical pinned datasets produce identical analytical rows, large parquet joins work on a laptop without a warehouse service, corrupted/missing artifacts block affected results, and synthetic/live data remain isolated.

### WP04 — Actual portfolio accounting and performance · P0

**Owns:** `performance.py`, historical valuation/cash-flow projection functions, performance result/report schema; no trade-planning logic.

- Add `invest portfolio performance --from YYYY-MM-DD --to YYYY-MM-DD [--account ID]` for **actual**, not simulated, account/household returns. Support net contributions/withdrawals, linked interaccount transfers (internal at household level), security purchases/sales, distributions/reinvestment, fees, corporate actions, account opening/closing, and dated complete valuation checkpoints. Partial/unknown balances invalidate the affected calculation interval.
- **TWR:** Link subperiod returns using complete valuations at each external cash-flow boundary, explicitly classifying the cash flow before/after the valuation; do not interpolate missing boundaries. **MWR/XIRR:** cash-flow sign convention = investor deposits negative, withdrawals positive, terminal complete value positive; use actual day differences/365.25, return root/coverage status, and mark missing or non-unique roots `UNAVAILABLE` (not zero). **CAGR:** annualize an actually supported positive-duration linked TWR: `(1 + TWR)^(365.25 / calendar_days) - 1`, with total loss yielding −100%; label period and methodology. Report gross/net-of-fee method explicitly; ordinary distributions retained in the portfolio are not external flows.
- Account performance treats verified transfers as external per account; household performance nets paired legs to zero. Dividend reinvestment does not count as a fresh investor contribution. Show signed contributions, beginning/end value, actual date span, measured coverage and exact reasons for gaps. Do not use today's portfolio weights to fabricate historical performance.
- Keep existing `portfolio risk` but rename/relabel it explicitly as **hypothetical static-current-weight historical risk** (e.g., `backtest risk` or a `mode: HYPOTHETICAL` output); no report/dashboard may present it as realized CAGR. Where the command name changes, update current docs and tests without deprecated aliases.

**Depends on:** WP02 and WP03. **Done when:** Independent hand-calculated examples for deposits, withdrawals, fees, reinvestment and transfers agree with CLI TWR/XIRR; missing valuation or cash-flow coverage yields an unavailable/partial outcome, never misleading returns.

### WP05 — Complete tax-lot, annual budget and harvest analysis · P0

**Owns:** `tax.py`, `tax_policy.py`, wash-sale candidate assessment and harvest proposal domain function; never owns brokerage execution or generic trading-policy CLI registration.

- Use WP02's exact **remaining adjusted basis** for specific-lot accounting. Record confirmed lot sale allocations and realized ST/LT proceeds, basis, fees, gains/losses with explicit holding-period date rules. Unknown acquisition date/basis, contradictory lot quantities, unsupported adjustment or incomplete taxable history prevents a definitive taxable trade estimate.
- Define one household US tax-year **estimated positive tax-cost allowance in USD**. Annual budget version includes calendar tax year, allowed estimated tax dollars, explicit ST/LT marginal rate assumptions, source/attestation coverage of **all taxable accounts and earlier sales**, and a timestamp. For conservative budget consumption, sum **positive realized gain on each confirmed taxable sale × applicable term rate** (do not offset with losses, estimated tax credits or speculative carryforwards). Spendable remainder = `max(0, annual_allowance − year_to_date_consumption)`; proposed incremental taxable sales must satisfy it. Separately report realized signed net gain and possible losses without treating an unverified loss as budget credit. This is a **conservative planning limit, not a prediction of final tax liability**. Unknown rates, currency or year-to-date sale coverage block gain-realizing taxable sale plans, but not safe cash-only proposals. A saved plan alone spends no budget; only confirmed executed sales change year-to-date consumption. If tax units are not USD, block budget estimates (FX out of scope).
- Household wash-sale inspection looks at known acquisitions in every configured account, including tax-advantaged accounts, in the 30 calendar days before and after a loss sale; future recurring purchases are included only when explicitly recorded. Mark untracked spouse/outside-account history, automatic dividend reinvestments and “substantially identical” comparisons as unknown review conditions. **Never label an ETF replacement legally wash-sale safe.** Existing/broker wash adjustments survive lot reconciliation; speculative tax savings do not appear as guaranteed cash.
- Add `invest tax budget --year YYYY` (consumption, remaining headroom, confidence/coverage) and `invest tax harvest-plan --as-of ... --policy-version ...` (loss lots, conflicts, estimated signed effect if supported, verified comparison metrics, replacement candidates, conditional proposed sales/purchases and review blockers). Harvest execution remains manual; replacement approval must be explicit in the saved policy/plan, not inferred from overlap or correlation. Block proposals that would breach known purchase restrictions or annual cost ceiling.
- Preserve `tax lots`, `analyze`, `harvest-candidates` and `fund replacements` as useful primitive queries; remove misleading ranking interpretation (replacement score means portfolio similarity only). Neither a low replacement fee nor high correlation proves legal suitability.

**Depends on:** WP02 and WP03. **Done when:** Multiple confirmed monthly sales cannot each reuse the full annual allowance, specific-lot adjusted basis is conserved, and tax/wash unknowns result in conservative blocked/reviewed outcomes.

### WP06 — Infrequent contribution-first trade plans and deterministic policy · P0

**Owns:** `planning.py`, pure proposal generator/validators, target-policy models and `simulations.py`. Existing `plans.py` should become thin persistence/summary glue; don't create a general solver framework.

- Introduce `invest plan propose --policy POLICY_VERSION --mode contributions-only|rebalance --as-of ... [--prices FILE]` and retain target versioning, `plan list/show/compare`, report export, and read-only simulation. Separate target percentages from account permissions, tax budget, trade-calendar policy and per-security execution precision. No trading policy is implicit in a natural-language agent request.
- Planning pipeline: **preflight typed checks → frozen accepted baseline/prices/policy → eligible candidate purchases/sales → deterministic action selection → authoritative exact simulation → final typed readiness and immutable report**. Pure stage functions with small inputs replace the 230-line orchestration method; keep no unnecessary classes or framework.
- Ordinary monthly mode proposes buys against **confirmed account cash** and underweights first. It must not sell to fund purchases. Rebalance mode is available only at the defined quarterly window/5-pp trigger unless an explicit human-approved exception policy is saved. Evaluate whether eligible account buying power can address drift before considering any sales. Never transfer cash across accounts invisibly.
- Distinguish `can_buy`, `can_sell` and `can_hold`. Selling an existing holding must not be prohibited solely because it isn't on the list of securities permitted for **new purchases**. Honor excluded positions, restrictions, cash floors, exact increment/notional rules, taxable budget, current holdings dates, source environment and stale/unknown prices. No zero-value invented holdings or implied executable quotes. Minimize trade count and taxable realizations before perfect drift; stable sort ties by account/security/lot ID.
- In an IRA/other tax-advantaged account, sell overweight positions first only if a quarterly rebalance is actually authorized; for taxable sales, select explicitly verified lots by documented HIFO/tax-rate policy and enforce WP05 annual headroom. Do not spend future realized losses to justify present tax cost. Compute final account cash, remaining lots, household values and allocation drift from the canonical simulation, **not** by trusting incremental planner bookkeeping.
- Every plan stores immutable normalized baseline hash, account state, target+policy versions, dates, data snapshot hashes, assumptions, exact lot allocations, ordered actions, before/after simulated state, residual drift, estimated tax budget effect, trading-cadence eligibility and issue codes. `plan compare` only ranks comparable pinned baselines and does not invent investment-quality scores. Distinguish `BLOCKED` (cannot calculate/propose), `REVIEW_REQUIRED` (calculable but material evidence/tax/execution uncertainty) and `READY_FOR_HUMAN_REVIEW` (calculations supported; **never an instruction to execute**).
- Save large plan details once with shared baseline and normalized summary columns. List/compare must not deserialize whole historical snapshots or whole research artifacts; keep plan and CLI responses bounded. A real-state change makes old plans stale without editing saved content.

**Depends on:** WP02, WP03 and WP05. **Done when:** $2,000 monthly contributions produce permitted cash-only purchases, outside-quarter drift does not trigger sales, tax costs remain within the annual allowance, and every candidate's final balances agree with the canonical simulator.

### WP07 — Recursive fund look-through, discovery and portfolio research universe · P1

**Owns:** `lookthrough.py`, `screening.py`, canonical issuer aggregation and selection functions. Uses WP03's data readers, does not edit provider adapters or research import logic.

- Extend `portfolio exposure` (or add `portfolio lookthrough`) to resolve nested ETF/mutual-fund constituents recursively through **at most 8 levels**, detect cycles, and stop at unknown/stale/unresolved underlying positions; never invent proportional fill or normalize a partially reported fund to 100%. Consolidate across accounts and fund wrappers by strong security identity and **issuer/company identity only when corroborated** (verified SEC CIK for US issuers; otherwise sourced LEI or explicit reviewed issuer mapping; names alone never establish issuer identity); preserve each contribution path and source/as-of provenance. Report directly owned, underlying company, sector/asset-type and **unknown residual** exposures in both dollars and percent. Currency mismatch without verified FX **blocks aggregation**, not arbitrarily converts.
- Use reporting-as-of dates and explicit holdings freshness: investment decision look-through requires underlying fund constituent observations no older than **120 calendar days** (configurable via policy version), otherwise mark affected exposure stale and exclude it from complete top-N assertions. An older historical question must use a snapshot actually known by that historical date. Protect recursion against cycles and double counting.
- Keep `security screen`, `fund search`, `fund holdings`, `fund compare`, `fund replacements` as deterministic structured discovery primitives. Improve fund comparisons with issuer, benchmark, share class, tracking/expense ratio, AUM, liquidity where sourced, underlying overlap, realized coverage and multi-period history alignment; missing data must not be scored as zero. No automatic tax-law substitute approval.
- Add `invest portfolio research-universe --as-of DATE --top 20 [--min-exposure 0.01]` to output **deterministically ordered** top underlying operating-company exposures, with tie break by canonical issuer ID; deduplicate holdings reached through multiple funds, preserve unknown exposure and resolved/unresolved issuer mappings. Exclude cash/fund shells from operating-company list. The percentage minimum default is **1% of known household value**, and the command returns fewer than N when fewer qualify; report N and filtered/unknown coverage prominently. A user can explicitly select `--min-exposure 0` to request all detected companies.

**Depends on:** WP03, WP02 for canonical identities. **Done when:** A fund-of-funds portfolio resolves one issuer exactly once at the sum of all paths, unknown residual remains visible, cycle terminates, and identical pinned observations select identical top-N companies.

### WP08 — Real historical backtest and strategy comparison · P1

**Owns:** `backtest.py`, history/strategy result models, reproducible comparison output; uses WP03's DuckDB reader. Not actual-performance code and not a trade-planner rewrite.

- Add `invest backtest run --portfolio current|TARGET_ID[@VERSION] --from DATE --to DATE --policy POLICY_VERSION --data-manifest ID` and `invest backtest compare RUN_ID...`. **`current` means hypothetical deployment of today's positions and weights at the historical start**; explicitly label it `HYPOTHETICAL_CURRENT_ALLOCATION`, never historical realized account performance.
- For fair A/B comparisons, demand identical explicit start/end sessions, included security price-return series, cash-flow schedule, fee model, rebalance frequency, reinvestment/dividend treatment, benchmark selection and fixed data-manifest lineage. If one strategy lacks required history, the comparison is `INCOMPARABLE`/`UNAVAILABLE`, not a favorable shortened period. No survivorship-free claim unless historical security eligibility is actually sourced. Do not use information published after a simulated historical decision date for look-through or screening decisions.
- Default historical model: **buy-and-hold with dividends reinvested and zero external contributions, zero cash return, zero slippage/commissions and no modeled taxes**. User may explicitly supply the **same** dated contribution schedule and fixed per-trade fee for all compared runs; optional quarterly threshold-based rebalancing uses §3.2 policy. Show all assumptions, turnover, tracking dates, total/annualized return, volatility, max drawdown and final allocation. Never claim a backtested pretax benefit is actual tax savings.
- Simulate using aligned, dividend-adjusted daily security total-return observations; no forward filling arbitrary gaps, no unsupported extrapolation and no look-ahead into future provider constituents. Use exact financial action/account balances where needed and clearly label numerical float-based return statistics. Backtest runs pin full historical input universe, algorithm version and model assumptions; comparisons use persisted results, not fresh prices.

**Depends on:** WP03, WP04's return methodology and WP07's security/issuer semantics; independent of WP06's proposed live trades. **Done when:** Two strategies with aligned and complete sources produce reproducible identical-date results, comparisons with missing history refuse false precision, and actual/imagined return outputs cannot be confused.

### WP09 — Portfolio-wide news, political, earnings and insider research · P1

**Owns:** shared research persistence envelope (`research_storage.py`), portfolio research coordinator/models, existing specialty adapters and output aggregation; keeps the five existing specialty evidence validators and change semantics.

- Use WP07's frozen top-N universe for deterministic **research selection and prioritization**, weighting by household underlying company exposure. The agent obtains current source evidence via permitted browsing; existing five skills research each issuer. Add a portfolio batch manifest with issuer list/order, source/cutoff dates, research windows, skill versions, per-company status and bounded summary. Preserve company-level evidence links and explicit `NOT_RESEARCHED`, `PARTIAL`, `REVIEW_REQUIRED`, `AVAILABLE` statuses.
- **News impact** is a cited factual materiality/watchlist assessment, not an AI price prediction or quantified forecast. Research published dates separately from event dates; retain event IDs across runs; preserve disputed/unchanged/missing cases without inventing changes. Portfolio report shows exposure-weighted watchlist ordering but never computes a trade instruction or political/ideological score.
- **Political scope is explicit:** verified contributions of identifiable executives are distinct from a **corporate PAC's** disclosed federal contributions and from individual employees' personal activity. Do not conflate any of them with issuer corporate policy. Existing named-contributor data permission restrictions continue to apply; when permissions/identity linkage are unverified, return excluded/unknown coverage. Corporate PAC category may be included only for verified source and issuer-PAC relationship; no generalized scraping or inferred political stance.
- Centralize immutable `research_runs` / `research_artifacts` metadata, hashing, source permissions, acceptance confirmation and common list/show retrieval; keep specialized earnings, news, political, competitive and insider Pydantic validation and domain queries. Do not rewrite legacy research as a giant untyped union, alter previously observed filing meaning, or create an agent autonomy service. Strict deduplication by issuer/event/source identity prevents reporting one syndicated article as several independent developments.
- Add `invest research portfolio plan --universe-manifest ID` (frozen issuer research queue and scope) and `invest research portfolio report --plan ID` (source-backed aggregation of individually accepted specialty runs; never performs browsing or imports on its own). Portfolio-level structured output: overall exposure coverage, researched company count/weight, top company impacts, outstanding evidence issues, date windows, research-run hashes and links to individual source-backed evidence. If only 12 of 20 issuers were researched, **never** claim whole-portfolio coverage.

**Depends on:** WP07 and WP01; existing five research specialties are preserved. **Done when:** Identical top-N issuer input selects the same research tasks and aggregate ordering, missing/partially permitted evidence stays explicit, and previously accepted specialist runs remain queryable through the consolidated storage interface.

### WP10 — Agent CLI orchestration and seven portable portfolio skills · P1

**Owns:** `cli.py`, `contracts.py`, seven `skills/investobot-*/SKILL.md` bundles plus focused references, consolidated skill registration, agent command documentation. Feature-domain modules remain owned by WP02–WP09.

- Add/retain the following **bounded, discoverable command families**: `db status|backup|verify|restore|migrate`; `portfolio import|reconcile|apply|record-activity|check|summary|performance|exposure|research-universe|simulate`; `tax lots|analyze|budget|harvest-candidates|harvest-plan`; `fund holdings|search|compare|replacements`; `security register|classify|screen`; `target save|list|show|activate|archive|diff`; `plan propose|list|show|compare`; `backtest run|compare`; `data snapshot|list|verify`; `research ...` (existing five groups plus portfolio and search commands); `report export`; `bond analyze` (read-only plain bond analytics); `tools list|describe`, `schema`. Delete redundant `plan generate` if `plan propose` replaces it; no legacy alias required before first live use. Existing local prompt library remains optional and must not duplicate skill contracts.
- Write **seven** portable workflow skills, all project-local installable for Codex and Claude Code, using authoritative CLI tool discovery and explicit stop rules:
  1. `investobot-portfolio-sync`: supplied HTML → review candidate → reconcile → human confirm → apply → preflight/status; never assign unsupported source dates.
  2. `investobot-portfolio-performance`: verify cash flows/checkpoints → actual TWR/XIRR/CAGR and gaps → sourced interpretation.
  3. `investobot-monthly-investing`: configured policy and contribution → check → pinned proposal → tax/drift/cadence inspection → report and human approval; never place trades.
  4. `investobot-tax-loss-harvesting`: validated lot/history coverage → household window → compare user-approved replacement candidates → proposal with missing-data and legal caveats.
  5. `investobot-investment-screening`: translate user goals into explicit measurable fund/equity criteria → structured search → coverage-aware comparisons → register only verified metadata.
  6. `investobot-portfolio-research`: look-through → deterministic top-N → existing earnings/news/competitive/political/insider skills → sourced exposure-weighted research report; track every issuer's status.
  7. `investobot-portfolio-strategy`: candidate target construction → common historical backtest and plan transitions → apples-to-apples metrics, constraints and limitations; no manufactured ranking.
- Each SKILL: trigger, exact prerequisites/CLI command order, data/freshness thresholds, missing-data fallback, authorization boundaries, repeatability manifest, maximum sensible batch size, final artifact schema, and a **concrete success and blocked walkthrough**. Skills do not perform financial arithmetic or directly write accepted portfolio rows. Existing five specialized skills remain modular and reusable.
- Complete `tools describe` with actual Pydantic schemas, flags, precise read/write mutation scopes, status/issue semantics and machine-readable examples. CLI names and arguments are final for this MVP; no speculative backwards-compatible aliases. The CLI and dashboard consume the same domain results and typed issues; dashboard renders, it does not recalculate.

**Depends on:** WP01–WP09 and WP11 domain interfaces. **Done when:** The seven natural-language end-to-end user intents in §5 use installed skills and CLI without inventing computations, human authorization stays explicit, and machine-readable command metadata matches actual behavior.

### WP11 — Local research corpus, text and vector retrieval · P2

**Owns:** `search.py`, `embedding.py` (adapter only), FTS5/sqlite-vec index creation/rebuild, and callable search domain functions; **only WP10 edits central CLI routing**. No external hosted database or embedding calls by default.

- Store source-backed research documents and immutable chunks with issuer, source URL/document ID, licensed/use-permission status, publication/observation date, content hash, text offsets and model provenance; changing source text or embedding model creates a new version, never silent overwrite. Exclude sensitive/personal contribution evidence unless explicitly authorized for indexing.
- SQLite **FTS5** indexes searchable text. Store validated **float32 L2-normalized embedding vectors** as versioned BLOBs in authoritative SQLite, with exact dimension/model ID and chunk fingerprint; index them via **sqlite-vec**, partitioning/searching only compatible model dimensions. Index files/tables are considered derived and rebuildable from canonical vectors. Embedding generation is an explicit user-approved operation through a configured model adapter; no hidden subscriptions, downloads or cloud upload. No automatic broker-derived embeddings.
- Add `invest research search --query TEXT [--issuer ...] [--from ...] [--to ...] [--top-k 10]` for text-only search by default, and `--semantic --embedding-file FILE --model-id ID` for optional vector/hybrid search; a skill/agent may create a compatible vector outside Investobot. Default hybrid ranks only candidates with verified stored embeddings from the **same model**; disclose term-match vs cosine components and stable tie-breaks. Results always return cited chunk IDs, source date, license/coverage, passage and score/method; search never invents cited facts. Explicit mismatch/absent index returns a clear typed error/status and leaves FTS usable.
- No generalized embedding training or autonomous indexing pipeline in MVP. Benchmark on a reproducible **100,000-chunk synthetic corpus** on CI-supported laptop-class hardware; record build size and p50/p95 top-10 latency. Any ANN/database replacement is post-MVP and requires measured evidence, not fashionable technology.

**Depends on:** WP01 and WP09; can be implemented independently of portfolio calculation engines. **Done when:** Search gives deterministic provenance-linked results, compatible model/dimension and permission filters hold, and dropping/corrupting the vector index cannot damage accepted research or portfolio data.

### WP12 — UX security, simplification, docs and release validation · P1

**Owns:** `README.md`, canonical docs, `AGENTS.md`, Compose/runtime packaging, dashboard safety and final test-suite/quality cleanup. No business-algorithm changes are permitted here.

- Keep the dashboard a thin **single-user loopback-only** inspection/preview UI. Native server only binds `127.0.0.1`; Docker may bind `0.0.0.0` **inside the container** only with Compose host publication pinned to `127.0.0.1`, enforced in shipped config and tested. Don't represent Host/Origin checks as authentication or add an unnecessary authentication framework. Never expose it on public interfaces. Render source coverage, typed blocks, actual vs hypothetical distinctions, and confirmation boundaries.
- Replace the release-history README with concise setup, safe first-use, CLI discovery, workflow examples, backup/restore, supported/provisional adapter status and test commands. Canonical docs: `docs/product.md`, `architecture.md`, `data-contracts.md`, `workflows.md`, `testing.md`, `skills.md`, `operations.md`, `tax-limitations.md`. Preserve all historical PRDs **unmodified at their existing paths** and remove release history from the active README/navigation; update AGENTS.md to remove superseded “never migrate” and other conflicting constraints. Never silently redefine existing historical documents.
- Remove redundant JSON/DDL code and unnecessary old schema/version paths. Split the existing oversized ledger/planner into small cohesive persistence, identity, accounting, tax and planning functions **without** adding generic base classes, repositories for every table, or deep abstractions. Reduce the duplicated research storage lifecycle through WP09's shared envelope. Remove `QuantLib` from the default dependency set; retain `bond analyze` as a small **read-only** plain fixed-coupon cash-flow/YTM/duration calculator using existing NumPy/SciPy and documented formulas. Unsupported call/convertible/structured bonds return `UNAVAILABLE`, never invented measures. Keep individual bonds excluded from automatic trade proposals. Rename release-version-named tests by domain, retaining unique behavior coverage; enable a small justified set of additional Ruff rules only after behavior is green.
- Document supported recovery semantics and backup/off-device rotation, source rights, real provider entitlement caveats, durable artifact growth, migration release procedure, data-environment separation, optional vector model setup, and all seven new skills. Any intentionally unsupported coverage appears in both product UI and docs.
- Measure on reproducible fixtures: startup/import/reconcile/backup, 20-plan list/compare, historical Parquet queries, top-N look-through, 100K-chunk vector search. Record hardware/container assumptions, exact fixture SHA and result; no fixed invented throughput target or work on private user data. Compare the existing 20-plan baseline, require no dramatic regression (define **≤2× elapsed time and ≤2× size** on identical benchmark hardware/data unless justified with measurable correctness benefits).

**Depends on:** WP01–WP11. **Done when:** Full Docker BDD/regression suite, Ruff, recovery/security/provider gates, packaging/install checks and canonical docs all pass on the exact release commit; no prior release notes masquerade as active requirements.

## 5. Required BDD acceptance inventory (written in WP00 before production code)

The following IDs are the **minimum** scenarios; each is an independently executable `Given / When / Then` example, with fixed source dates and exact observable output. Developers may split a case if it contains two distinct behaviors but must not weaken or delete its acceptance. Never assert internal class names, helper calls or SQL call counts. Keep the new test suite red for unmet behavior until implementation.

| ID | Given → When → Then (user-observable promise) | Package |
|---|---|---|
| B01 | **Given** an accepted ledger and active reader, **when** a verified online backup is created during another committed write, **then** the restored archive is internally consistent and contains one complete transaction state, not half an update. | WP01 |
| B02 | **Given** a backup with a missing or tampered referenced Parquet file, **when** `db verify` or restore dry-run runs, **then** it reports the exact invalid artifact and refuses replacement. | WP01 |
| B03 | **Given** an old development-schema-9 ledger, **when** the new CLI starts, **then** it reports the incompatible schema and leaves every original byte intact. | WP01 |
| B04 | **Given** a valid archive and a live database, **when** restore is previewed and then separately confirmed, **then** preview changes nothing and confirmed restore produces the expected balances and research history. | WP01 |
| B05 | **Given** a damaged SQLite copy or violated foreign key, **when** verification runs, **then** a specific non-success integrity outcome is returned; no false `OK` status. | WP01 |
| B06 | **Given** a complete position of 10 shares at $100 with reported value $100, **when** acceptance is attempted, **then** it is rejected with an `INCONSISTENT_POSITION_VALUE` issue and previous state stays unchanged. | WP02 |
| B07 | **Given** an Oct 9 snapshot and an Oct 10 confirmed purchase, **when** an Oct 9 observation arrives on Oct 11, **then** the purchase is neither erased nor duplicated and the old snapshot is retained only as evidence. | WP02 |
| B08 | **Given** a trade and an undated/same-date-only brokerage page, **when** event ordering cannot be established, **then** acceptance is blocked until a human supplies verifiable ordering. | WP02 |
| B09 | **Given** a partial page omitting one known holding and with unreported cash, **when** it is applied, **then** the holding remains and cash stays unknown instead of becoming $0. | WP02 |
| B10 | **Given** a broker tax lot after an earlier partial sale, **when** a second statement reports lower remaining quantity and adjusted basis, **then** the same matched lot remains and only its exact remaining basis is available for sale. | WP02 |
| B11 | **Given** an activity ID already confirmed with identical details, **when** the same activity is retried, **then** it is a no-op; different details under that ID are atomically rejected. | WP02 |
| B12 | **Given** a new position from a recorded purchase but no admissible valuation mark, **when** household value is requested, **then** the valuation is incomplete, not a fabricated $0 position. | WP02 |
| B13 | **Given** a reinvested dividend, a stock split and a return-of-capital event with complete evidence, **when** they are accepted, **then** lots, quantities, external cash flow and remaining adjusted basis follow the distinct event meanings without fake deposits. | WP02 |
| B14 | **Given** strong-ID conflicting securities with a common ticker alias, **when** an import uses that alias, **then** it reports an identity conflict and does not merge them. | WP02 |
| B15 | **Given** a broker page containing positions plus a summary total table, **when** imported, **then** the summary is not accepted as an extra holding and ambiguous rows remain review-required. | WP02 |
| B16 | **Given** an FMP response missing a required dividend-adjusted price field, **when** `market history` is requested, **then** adjusted total return is unavailable rather than computed from unadjusted close. | WP03 |
| B17 | **Given** a verified REAL portfolio and a SYNTHETIC quote source, **when** a trade proposal is requested, **then** it is blocked with `MIXED_DATA_ENVIRONMENT`. | WP03/WP06 |
| B18 | **Given** two vintages of the same fund holdings with distinct as-of dates, **when** a pinned historical snapshot is requested, **then** it retrieves the explicitly eligible vintage and never backfills with today's holdings. | WP03 |
| B19 | **Given** a frozen SQLite+Parquet data manifest, **when** an analytical run is repeated without new inputs, **then** the substantive result and source fingerprints are identical and the ledger is unchanged. | WP03 |
| B20 | **Given** $1,000 opening value, $1,100 immediately before a $100 deposit, $1,200 immediately after, and $1,320 closing value, **when** actual TWR is computed, **then** it is exactly **21%**, not 32%. | WP04 |
| B21 | **Given** $1,000 invested for 365 days with no interim flows and $1,100 ending value, **when** XIRR is computed, **then** it matches the stated actual-day annualized equation and is labeled money-weighted. | WP04 |
| B22 | **Given** a $200 transfer from one portfolio account to another, **when** household performance runs, **then** it is not counted as an external $200 contribution. | WP04 |
| B23 | **Given** an internally reinvested $50 dividend, **when** performance runs, **then** it is not counted as an additional investor deposit or double-counted return. | WP04 |
| B24 | **Given** a missing valuation exactly when an external deposit occurred, **when** TWR is requested, **then** TWR is `UNAVAILABLE` for that interval with the missing date reported, not interpolated. | WP04 |
| B25 | **Given** a report that contains historical risk for today's weights, **when** rendered, **then** it is labeled hypothetical and cannot be mistaken for realized CAGR. | WP04 |
| B26 | **Given** a $500 annual conservative tax-cost allowance and $200 already consumed by confirmed taxable sales, **when** a new plan would add $400 positive estimated cost, **then** it is rejected/blocked for that budget (remaining $300). | WP05 |
| B27 | **Given** two saved unexecuted sale proposals, **when** remaining yearly tax budget is queried, **then** saved proposals alone consume no budget; only confirmed activity does. | WP05 |
| B28 | **Given** a loss sale and a purchase in another household IRA 20 days before sale, **when** wash-sale review runs, **then** it finds the conflict and does not promise tax savings. | WP05 |
| B29 | **Given** unknown spouse-account purchases or possible substantially-identical replacements, **when** harvesting is proposed, **then** the legal outcome is marked review-required and no substitute receives a “wash-sale safe” certification. | WP05 |
| B30 | **Given** a lot with 4 remaining shares and $360 remaining adjusted basis, **when** 1 share is sold by specific lot, **then** remaining lot basis is $270 before any separately sourced adjustments. | WP05 |
| B31 | **Given** a $2,000 new confirmed contribution and an underweight permitted fund, **when** monthly contribution-only planning runs, **then** it proposes only affordable permitted purchases and no sales. | WP06 |
| B32 | **Given** an 8-percentage-point drift in February, **when** normal rebalancing is requested, **then** no sale is proposed outside quarterly months unless a separately approved exception policy applies. | WP06 |
| B33 | **Given** a 4-percentage-point drift in March and a 5-pp trigger, **when** normal rebalance runs, **then** it does not sell solely to eliminate that drift. | WP06 |
| B34 | **Given** an existing overweight fund that cannot be newly bought but may be sold, **when** quarterly planning runs, **then** `can_sell` is checked independently of the buy allowlist. | WP06 |
| B35 | **Given** an account permits 0.001-share fund purchases and has enough cash, **when** a monthly buy is proposed, **then** the order honors that increment rather than silently rounding down to whole shares. | WP06 |
| B36 | **Given** missing cash, unknown execution precision or stale positions, **when** a plan is requested, **then** relevant trades are blocked by typed reasons; changing warning wording cannot change readiness. | WP06 |
| B37 | **Given** a saved plan followed by new confirmed activity, **when** the plan is listed or reported, **then** its saved actions are unchanged but its current status is `STALE`. | WP06 |
| B38 | **Given** a sale-and-buy proposal with known fee and lot effects, **when** it is simulated, **then** account cash, quantity, basis and household total match an independent authoritative simulation or saving fails. | WP06 |
| B39 | **Given** a fund owning another fund that owns company X, **when** full look-through is requested, **then** company X receives the product of parent/child weights exactly once per valid contribution path. | WP07 |
| B40 | **Given** cyclic funds A→B→A, **when** look-through runs, **then** recursion terminates and unresolved value is reported without double-counting. | WP07 |
| B41 | **Given** a fund with only 65% identified holdings, **when** look-through runs, **then** the remaining 35% is unknown rather than redistributed to identified companies. | WP07 |
| B42 | **Given** holdings older than the 120-day policy threshold, **when** the top-company universe is generated, **then** affected exposure is flagged stale and cannot be claimed completely known. | WP07 |
| B43 | **Given** several funds owning the same identified issuer, **when** top-20 research universe runs, **then** one issuer appears with summed underlying exposure, stable tie-breaks and explicit unknown coverage. | WP07 |
| B44 | **Given** USD and EUR positions without an approved FX model, **when** household exposure is requested, **then** the tool blocks cross-currency aggregation instead of summing incomparable amounts. | WP07 |
| B45 | **Given** two candidate targets with identical pinned daily histories, **when** backtested over the same dates, **then** comparisons use the same period, cash schedule, fees and assumptions. | WP08 |
| B46 | **Given** a fund absent from one candidate's requested historical period, **when** backtest comparison runs, **then** it reports incomparability and does not silently shorten that candidate's window. | WP08 |
| B47 | **Given** only current constituent weights, **when** a historical look-through/backtest is attempted for years earlier, **then** future-known constituents are not used as historical holdings evidence. | WP08 |
| B48 | **Given** a backtest of today's allocation, **when** its report is exported, **then** it prominently says `HYPOTHETICAL_CURRENT_ALLOCATION`, not actual past performance. | WP08 |
| B49 | **Given** a top-N research list with only 12 of 20 issuers researched, **when** portfolio news impact is summarized, **then** 12/20 and covered portfolio weight are reported without claiming complete research. | WP09 |
| B50 | **Given** two syndicated articles about one underlying event, **when** incremental company news research is accepted, **then** the event is not counted as two new developments. | WP09 |
| B51 | **Given** executive donations and an issuer-associated PAC disclosure, **when** political activity is reported, **then** their contribution categories stay separate and no political-stance score is inferred. | WP09 |
| B52 | **Given** contributor permission cannot be verified, **when** agent research is submitted, **then** unauthorized named contributions are excluded and acceptance cannot override that restriction. | WP09 |
| B53 | **Given** an agent receives new broker HTML, **when** the portfolio-sync skill runs, **then** it obtains typed reconciliation issues and seeks explicit authorization before acceptance. | WP10 |
| B54 | **Given** an incomplete cash-flow history, **when** the performance skill runs, **then** it reports unavailable actual returns rather than calculating from today's weights. | WP10 |
| B55 | **Given** a new contribution, **when** monthly-investing skill runs, **then** it uses the configured policy, preserves manual execution boundaries and produces a saved, source-pinned proposal. | WP10 |
| B56 | **Given** household wash-sale uncertainty, **when** harvesting skill runs, **then** it surfaces review requirements rather than certifying the suggested replacement safe. | WP10 |
| B57 | **Given** a user wants a low-cost broad market fund, **when** screening skill runs, **then** it reports sourced screening criteria, comparisons and explicit missing characteristics without invented scores. | WP10 |
| B58 | **Given** a portfolio-wide news question, **when** research skill runs, **then** it uses the frozen deduplicated issuer list and saves cited issuer-specific coverage/status. | WP10 |
| B59 | **Given** two new target allocations, **when** strategy skill runs, **then** it compares pinned common-history backtests and separate tax-aware transition plans without mixing actual performance. | WP10 |
| B60 | **Given** a registered CLI command, **when** `tools describe` runs, **then** its flags, JSON input schema and mutation scope agree with executable behavior. | WP10 |
| B61 | **Given** keyword-only source text, **when** research search runs without embedding configuration, **then** FTS returns cited permitted chunks without any external API request. | WP11 |
| B62 | **Given** query/document vectors from different embedding models or dimensions, **when** semantic retrieval runs, **then** cross-model comparison is rejected, never silently mixed. | WP11 |
| B63 | **Given** a dropped derived vector index, **when** index rebuild and semantic search run, **then** source documents and accepted ledger data remain identical and retrieval is restored. | WP11 |
| B64 | **Given** an unauthorized source document, **when** text or vector retrieval runs, **then** it is absent from search results regardless of lexical or vector similarity. | WP11 |
| B65 | **Given** a native dashboard launch attempting an external bind, **when** startup is checked, **then** the service refuses insecure exposure; shipped Compose remains host-loopback-only. | WP12 |
| B66 | **Given** a fresh Docker checkout, **when** canonical quickstart commands run, **then** the tooling discovers the installed skills, exercises a synthetic workflow and explains how to back up without resetting or exposing a ledger. | WP12 |

### Example `.feature` requirement (real test files, not just prose)

```gherkin
Feature: Monthly contributions respect the investment policy

  Scenario: Invest new cash without an unnecessary taxable sale
    Given a complete USD household portfolio valued at $100,000
    And $2,000 was deposited into its taxable account on 2026-10-05
    And its approved October contribution policy permits buying FUND-A
    And FUND-A is underweight and its current price and increment are known
    When the agent requests a contribution-only proposal for 2026-10-10
    Then the proposal buys no more than the account's available $2,000
    And it contains no sale
    And its estimated annual tax-budget consumption is $0
    And it is saved for human review without changing actual holdings
```

Use **focused, smaller scenarios** rather than combining these assertions everywhere; this longer sample illustrates the end-to-end contract, while `B31`, `B26` and `B37` separately test individual guarantees. Strict red-first means the developer must observe these failures before implementing any production change.

## 6. Work order, handoffs and release gates

### Non-overlapping implementation sequence

| Stage | Packages | Permitted overlap and handoff |
|---|---|---|
| **Red** | WP00 | All new BDD scenarios/fixtures first; **no application code**. Baseline-green and new-red evidence required. |
| **Foundation** | WP01 → WP02; WP03 may follow WP01 in parallel with WP02 | WP01 fixes relational schema and storage API; WP02 alone edits ledger/ingest; WP03 alone edits provider and analytical reader. Agree fixed contracts at WP01 completion. |
| **Core math** | WP04 + WP05 after their prerequisites | Independent performance versus tax modules; WP04 doesn't edit planner, WP05 doesn't edit ledger. |
| **Decision support** | WP06 + WP07 after prerequisites | Independent planner versus look-through/screening logic. |
| **Historical and research** | WP08 + WP09 after WP07 | Backtesting and specialized research coordinator own distinct modules; shared input is frozen issuer/data manifest contract. |
| **Search** | WP11 after WP09/WP01 | Independent derived index; no CLI routing edits until integration. |
| **Agent integration** | WP10 after WP01–WP09 and WP11 | Only integration owner edits central CLI/contract registry and all 7 skills, resolving command names exactly once. |
| **Hardening** | WP12 last | Security/docs/dependency cleanup and release gate; no changes to financial behavior without reverting to the BDD red/green process. |

**Required checkpoints:** Commit/record the global red scenario set; after each domain package run its scenario subset plus prior green domain tests; after integration run **every** new and existing BDD scenario, Docker tests and Ruff on the exact committed tree. A failing new scenario may persist across intermediate WPs when it requires final CLI integration, but the implementing package must be testable via its public domain behavior before handoff. Keep each package's files/modules separately owned; only WP10 edits command routing and metadata. Do not fake green status with ignored tests.

### Final MVP acceptance gates

1. **Accounting safety:** No accepted snapshot supersedes later confirmed activity; exact lots/basis/cash and per-domain source chronology reconcile; invalid inputs cannot mutate state; reruns are idempotent.
2. **Actual performance:** Auditable TWR, XIRR and CAGR where supported, with precise missing-data statuses. Actual, static-current-weight risk and historical backtest results are visibly different.
3. **Tax and policy:** Conservative year-to-date annual tax allowance, household wash-sale review, cash-only monthly default, gated quarterly rebalance, explicit fractional execution permissions and exact simulated final balances. No legal or tax-filing certification.
4. **Research and comparison:** Complete/unknown underlying fund exposure remains mathematically honest; top-N selection and issuer coverage reproducible; research source/permission categories enforced; backtests use aligned frozen datasets with no future holdings look-ahead.
5. **Reliability and growth:** SQLite restore from verified online backup works; migration tools cannot destroy existing data silently; Parquet/DuckDB queries are read-only and pinned; vector index can be rebuilt from SQLite; laptop benchmarks recorded.
6. **Human control and privacy:** No broker integrations or auto trades; no live data copied into synthetic test environments; dashboard host loopback only; `tools describe` reports true permissions/mutations; acceptance/restore actions require explicit confirmation.
7. **Live-input evidence:** All institution-specific parser claims have real, safely redacted, reviewed golden HTML examples; the actual user's FMP entitlement/endpoints have been validated outside CI. **If external examples/credentials are not provided, mark those integrations provisional and prohibit advertising the project as validated for actionable real-world use.** Fully synthetic workflows may still pass and ship as a **development preview**, not real-data-ready.
8. **Quality and docs:** WP00 test-only red checkpoint exists; final entire Docker suite and Ruff are green; exact release commit recorded; backup restore and security regression tests pass; concise current docs supersede release chronology; no unimplemented requirement is described as done.

### Final user-facing demonstration (no real brokerage credentials)

Using one entirely synthetic household containing a taxable account and an IRA, the agent must: ingest a test HTML statement; reject an inconsistent row; accept a valid snapshot; record a deposit and partial-lot sale; report actual performance/coverage; create an October cash-funded plan within annual tax allowance without a sale; show a blocked or review-required harvest where a 30-day IRA purchase exists; resolve nested fund exposure and name the top companies; research those companies with partial coverage preserved; compare two aligned historical allocation backtests; execute research text/vector search with cited evidence; export an immutable plan report; create, verify and restore an archive; and confirm actual accepted holdings are unchanged by every hypothetical or research step. Everything is invoked through the distributed CLI/skills, returns parseable documented JSON and has no network requirement in CI.

## 7. Traceability to the full review and subsequent decisions

This table prevents cleanup and less-visible requirements from being lost during implementation. F01–F29 refer to the October 10 source review; this PRD is authoritative for the selected implementation approach.

| Review findings / subsequent decisions | Primary owning package |
|---|---|
| F01 stale snapshot/activity ordering; F02 position value consistency; F03 lot ID and adjusted remaining basis; F06 typed freshness; F08 no fake new-holding valuation; F17 event taxonomy; F18 aliases; F20 safe HTML candidate selection | **WP02** |
| F04 annual tax-dollar allowance; F16 household harvest orchestration, substitutions, wash warnings | **WP05** |
| F05 actual TWR/XIRR/CAGR and real external flows | **WP04** |
| F07 typed plan issues; F11 sell-versus-buy rules and deterministic allocation; F12 cadence/drift; F13 trading precision; F21 actionability; F23 small pure planning stages | **WP06** |
| F09 provider/broker validation; F29 real/synthetic separation; dated source artifacts; DuckDB/Parquet | **WP02 + WP03** |
| F10 portfolio agent workflow skills; F28 one tool descriptor source | **WP10** |
| F14 recursive look-through and freshness; fund/security screening | **WP07** |
| F15 same-assumption backtest and comparison | **WP08** |
| F19 portfolio-level weighted news and political evidence; F24 shared immutable research envelope | **WP09** |
| F22 ledger SQL/indexes/large scans; database backups, migrations and integrity | **WP01 + WP12** |
| F25 current docs; F26 unnecessary deps/test taxonomy; F27 secure local dashboard | **WP12** |
| Embeddings, ANN, keyword search and source-linked retrieval | **WP11** |
| Global write-failing-tests-before-any-production-code, observed-red evidence, behavior-first tests | **WP00** |

---

**Definition of done:** The system is small enough that its authoritative financial state, uncertainty rules and trade-policy computation can be understood without an LLM; every critical behavior has a red-first BDD acceptance case; the SQLite ledger can be backed up/restored reliably; heavy history and vector retrieval can grow independently; agents orchestrate the deterministic primitives rather than improvising financial calculations; and humans remain the only parties who make and execute trades.
