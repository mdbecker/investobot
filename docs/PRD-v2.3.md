# Investobot — SQLite Performance & Plan Storage Optimization

**Product Requirements Document — Version 2.3**

**Repository:** https://github.com/mdbecker/investobot  
**Baseline:** V2.2 complete  
**Priority:** Performance and maintainability  
**Development methodology:** Strict BDD — Red → Green → Refactor  
**Database strategy:** Fresh schema; existing SQLite data may be discarded

---

## 1. Objective

Make Investobot fast and efficient when an AI coding agent creates, lists, retrieves, compares, and reports on multiple hypothetical investment plans.

The current architecture repeatedly copies complete historical portfolio data into saved plans and unnecessarily reloads large objects during routine operations.

The previously measured synthetic benchmark found:

| Metric | Baseline |
|---|---:|
| Accounts | 10 |
| Current positions | 1,000 |
| Tax lots | 2,000 |
| Historical snapshots | 200 |
| Saved plans | 20 |
| Database growth from saving plans | ~221 MiB |
| Average serialized plan | ~11 MiB |
| Time to generate 20 plans | ~44.4 seconds |
| Time to list 20 plans | ~17.9 seconds |
| Time to retrieve one plan | ~0.84 seconds |

These results indicate unnecessary data duplication, repeated deserialization, redundant portfolio-state hashing, and repeated whole-portfolio calculations.

**The goal is not to replace SQLite. The goal is to use SQLite efficiently.**

### Required outcomes

1. Plan listing and comparison operate on small summary records.
2. Multiple plans sharing the same source portfolio reuse one immutable baseline.
3. Historical audit snapshots are not copied into every plan.
4. Planning calculations avoid repeatedly traversing or deep-copying the entire household portfolio.
5. Full plan retrieval and historical report generation remain available.
6. All financial calculations and safety guarantees remain unchanged.
7. The implementation remains a small, understandable Python codebase.

---

# 2. Fixed Architectural Decisions

Keep:

- Python 3.12+
- `uv`
- Typer
- Pydantic
- SQLite through standard-library `sqlite3`
- Decimal financial arithmetic
- Existing portfolio ledger and domain calculations
- Existing target, plan, tax, exposure, and report interfaces
- Existing lightweight WebUI
- pytest + pytest-bdd
- Ruff
- Offline Docker CI

Do not add:

- PostgreSQL
- Redis
- an ORM
- an external database service
- an object-storage service
- background jobs
- compression frameworks
- generalized caching frameworks
- a new financial planning algorithm
- new investment features
- new frontend frameworks

Only add abstractions when they remove real duplication or make ownership of data clearer.

### Database reset policy

**The existing SQLite database is disposable.**

Developers may delete it and initialize a completely new schema.

Do not implement:

- migrations from the old plan schema;
- backfilling old plan records;
- compatibility readers for legacy saved plans;
- dual-write support;
- migration-specific validation or rollback code.

Set the new SQLite schema version to `3`.

A database using an older incompatible schema should produce a clear error with instructions to reset it. The application should not silently destroy a database on startup.

Document a deliberate database-reset procedure for native and Docker installations.

All automated tests must create fresh disposable databases.

---

# 3. Mandatory BDD Development Process

Every work package must follow strict test-first development.

1. Write the new BDD scenarios.
2. Implement their pytest-bdd step definitions.
3. Run the scenarios and confirm expected failures.
4. Investigate unexpected passes or unrelated failures.
5. Implement the minimum production changes required.
6. Make all new scenarios pass.
7. Run the complete regression suite.
8. Run Ruff.
9. Update relevant documentation.
10. Commit the verified changes.

BDD scenarios must test observable behavior and financial results, not private method calls.

Use synthetic portfolio data.

No real brokerage information or live market-data APIs are required.

Performance benchmarks may be implemented as deterministic workload scripts with wall-clock measurements. Avoid brittle CI assertions based on execution times.

---

# 4. Implementation Packages

| Order | Package | Priority | Dependencies |
|---|---|---|---|
| 1 | Shared immutable planning baselines and new SQLite schema | P0 | None |
| 2 | Efficient plan persistence, queries and retrieval | P0 | Package 1 |
| 3 | Faster in-memory trade planning and simulation | P1 | Packages 1–2 |
| 4 | Performance verification, regression tests and documentation | P1 | Packages 1–3 |

Packages must be implemented in order.

Each package must leave the existing financial behavior correct and the full test suite green before proceeding.

---

# 5. Package 1 — Shared Immutable Planning Baselines

**Priority: P0**

**Dependencies: None**

## 5.1 Problem

Plan generation currently includes full portfolio state in every saved plan.

That state contains historical snapshots, even though most of them are unnecessary for producing or explaining the plan.

When 20 hypothetical alternatives share the same starting portfolio, each plan stores its own copy of substantially the same information.

This is the primary storage-design problem.

## 5.2 New design

Introduce an immutable, content-addressed **planning baseline**.

A baseline represents the authoritative household financial information used when a plan was generated.

Multiple plans may reference the same baseline.

A baseline contains:

- Current account configuration.
- Current security identities and metadata.
- Current positions.
- Current known tax lots.
- Current known cash balances.
- Relevant confirmed transaction history required by existing tax calculations.
- Latest accepted observation references and source dates for each account.
- Data completeness information.
- Other financial fields demonstrably required by existing planning, tax, and simulation functions.

A baseline must not include:

- Every historical account snapshot.
- Historical snapshot HTML.
- Saved plans.
- Saved targets unrelated to the selected target version.
- Market-data caches.
- Fund-holdings caches.
- Unrelated audit records.
- Previous plan calculations.

Historical snapshots remain in the authoritative ledger. They are not copied into planning baselines.

### Critical correctness requirement

Do not omit financial information that existing tax or wash-sale calculations actually require.

The optimization must not truncate acquisition history merely to make the baseline smaller.

If an activity-history filter is introduced, it must be proven by BDD tests to preserve all information needed for the same financial results. Otherwise retain the relevant confirmed activity history in the baseline.

## 5.3 Planning-state API

Add an explicit lightweight state-reading operation:

```python
ledger.planning_state()
```

This returns only the financial inputs required for planning and its dependent calculations.

Keep the existing full ledger-state operation for other functionality that actually needs complete history.

The new operation must not:

- Deserialize every historical snapshot.
- Read saved plans.
- Read market-data caches.
- Perform external network requests.

It may retrieve a compact latest-snapshot projection per account.

Use direct SQL queries where appropriate instead of loading every row into Python and then filtering.

## 5.4 State fingerprints

Create a deterministic planning-state fingerprint.

Use SHA-256 over a canonical serialization of the planning-relevant state.

Canonicalization must have stable ordering for:

- Accounts.
- Securities.
- Positions.
- Lots.
- Activities.
- Cash balances.
- Latest observation references.

Decimal and date representations must be normalized consistently.

The fingerprint must change when financially relevant input changes, including:

- Share quantities.
- Tax lots or cost basis.
- Cash.
- Security classifications.
- Account tax status.
- Confirmed transactions relevant to analysis.
- Market valuations used as accepted planning inputs.
- Relevant data freshness or source provenance.

The fingerprint must not change solely because an unrelated older audit snapshot was added or reordered.

A newer accepted observation containing materially different source provenance must be reflected appropriately.

Do not use database row order as an implicit component of the fingerprint.

## 5.5 New SQLite schema

Replace the old generic plan storage with dedicated tables:

```sql
CREATE TABLE plan_baselines (
    id TEXT PRIMARY KEY,
    state_json TEXT NOT NULL
);

CREATE TABLE plans (
    id TEXT PRIMARY KEY,
    baseline_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    as_of TEXT NOT NULL,
    generated_status TEXT NOT NULL,
    summary_json TEXT NOT NULL,
    details_json TEXT NOT NULL,
    price_assumptions_hash TEXT NOT NULL,
    tax_assumptions_hash TEXT NOT NULL,

    FOREIGN KEY (baseline_id)
        REFERENCES plan_baselines(id)
);
```

Use `plan_baselines.id` as the canonical planning-state hash.

`state_json` stores the immutable planning baseline.

`summary_json` stores the compact plan summary defined by V2.2.

`details_json` stores the immutable information specific to that plan, including:

- Selected target and target version.
- Proposed actions.
- Assumed prices and timestamps.
- Tax assumptions.
- Tax-analysis results.
- Allocation calculations.
- Exposure-analysis results.
- Warnings.
- Cash before and after.
- Remaining target drift.
- Report-specific metadata.

It must not contain another copy of the complete baseline.

It must not contain historical snapshots.

The assumption hashes provide inexpensive plan-comparison checks without loading detailed JSON.

Create one index:

```sql
CREATE INDEX plans_created_idx
ON plans (created_at DESC, id DESC);
```

Additional indexes require profiling evidence.

Retain SQLite foreign-key enforcement.

Do not create a generalized relational portfolio schema, object store, or deduplication framework.

## 5.6 Baseline reuse

When creating a new plan:

1. Read the planning-relevant household state.
2. Calculate its canonical hash.
3. Check whether a baseline with that ID already exists.
4. Insert it if absent.
5. Save the new plan referencing that baseline.

Use `INSERT OR IGNORE` or an equivalent atomic operation.

If two alternatives use identical planning-relevant state, both must reference the same baseline.

Do not modify an existing baseline after creation.

If the actual portfolio changes, subsequent plans reference a new baseline.

### Atomicity

The baseline insert and plan insert must occur in one transaction.

If plan persistence fails, no orphaned baseline from that operation should remain.

## 5.7 Saved-plan staleness

A plan is stale when the current planning-state fingerprint differs from the fingerprint of its saved baseline.

This calculation must not require deserializing historical snapshot contents.

The current fingerprint is calculated once per list or compare request.

Target changes do not retroactively alter a plan's pinned target version.

### BDD scenarios

```gherkin
Feature: Shared immutable planning baselines

Scenario: Alternative plans reuse the same portfolio baseline
  Given a household portfolio with accepted holdings and tax lots
  When twenty alternative plans are generated from that portfolio
  Then all twenty plans reference one immutable planning baseline
  And no plan duplicates the complete historical account snapshots

Scenario: A changed portfolio creates a new baseline
  Given two plans share an immutable portfolio baseline
  When a confirmed trade changes the accepted holdings
  And a new plan is generated
  Then the new plan references a different baseline
  And the original plans remain reproducible and are marked stale

Scenario: Unrelated historical audit data does not invalidate a plan
  Given a saved plan uses an accepted household baseline
  When unrelated older audit history is added
  Then the planning-state fingerprint remains unchanged
  And the saved plan remains current

Scenario: Baseline persistence is atomic
  Given a portfolio baseline does not yet exist
  When plan persistence fails
  Then no incomplete plan is saved
  And no orphaned baseline remains
```

Also test:

- Deterministic fingerprints.
- Decimal normalization.
- Multiple accounts.
- Known and unknown tax lots.
- Account classification changes.
- Security classification changes.
- Source provenance changes.
- Concurrent attempts to create the same baseline.
- No cache writes during simulation.

### Definition of Done

Multiple alternative plans share one immutable baseline, without repeating historical portfolio snapshots or losing financial information necessary for correct analysis.

---

# 6. Package 2 — Efficient Plan Storage and Queries

**Priority: P0**

**Dependencies: Package 1**

## 6.1 Problem

The existing plan operations perform excessive work.

A lookup for one plan may deserialize every stored plan.

Listing plans can repeat that process for each result.

Stale-status evaluation can repeatedly reload and hash the household ledger.

Even compact output is inefficient if the implementation still loads huge plan details internally.

## 6.2 Design decision

Plan queries must operate on the smallest required data.

The rules are:

- Listing uses summaries.
- Comparison uses summaries and assumption hashes.
- Full retrieval loads one plan and its baseline.
- Report export loads one plan and its baseline.
- Current state is read and hashed at most once per listing/comparison operation.

Do not deserialize `details_json` or `state_json` unless the operation genuinely needs them.

## 6.3 Storage ownership

Add a small, focused module if useful:

```text
src/invest/plan_storage.py
```

Its responsibility is only:

- Baseline insertion and retrieval.
- Plan insertion.
- Summary listing.
- Selected-plan comparison reads.
- Full single-plan retrieval.

Keep financial analysis and planning strategy in the existing domain modules.

Do not create a generic repository framework or ORM-like abstraction.

## 6.4 Plan listing

`invest plan list` must execute one summary-only SQL query.

Example:

```sql
SELECT
    id,
    baseline_id,
    created_at,
    generated_status,
    summary_json
FROM plans
ORDER BY created_at DESC, id DESC;
```

The implementation must not read `details_json` or `plan_baselines.state_json`.

Calculate the current planning fingerprint once and determine each plan's effective status.

Return the V2.2 compact summary contract.

Do not return complete saved financial state.

### Response size

For the existing 20-plan synthetic workload:

**Plan-list JSON must remain below 128 KiB.**

## 6.5 Plan comparison

`invest plan compare` must query only the requested plans.

Use a parameterized SQL query for their IDs.

Read:

- Summary JSON.
- Baseline IDs.
- Price assumption hashes.
- Tax assumption hashes.
- Planning dates.
- Creation dates.
- Saved statuses.

Do not load complete plans or baselines.

Preserve comparison warnings when:

- Source baselines differ.
- Prices differ.
- Tax assumptions differ.
- Analysis dates differ.

Do not produce a ranking score.

The result must remain below 128 KiB for comparison of 20 synthetic plans.

Unknown IDs must produce the existing structured input error.

## 6.6 Plan generation response

`invest plan generate` must:

1. Generate financial calculations.
2. Save the immutable baseline and plan details.
3. Return only the compact plan summary.

Do not serialize the full baseline to CLI stdout or WebUI responses.

The full internal result can remain available during generation, but should not be retained in multiple unnecessary in-memory copies.

## 6.7 Full plan retrieval

`invest plan show PLAN_ID` must load:

- Exactly one plan's details.
- Exactly one referenced baseline.

Return the same logical financial information required by the existing complete plan interface.

The implementation may reconstruct the full response from plan-specific details and the baseline.

It must not query unrelated plans.

## 6.8 Report export

Keep:

```bash
invest report export PLAN_ID \
  --format markdown \
  --output report.md
```

Report export must reconstruct the report from the immutable plan and its saved baseline.

It must not:

- Recalculate tax liabilities.
- Fetch current market prices.
- Query live holdings for the original plan.
- Replace saved assumptions with current ones.
- Modify actual portfolio state.

Two exports of the same plan must be byte-identical, even after new portfolio transactions or snapshots.

## 6.9 CLI and WebUI parity

Apply the same efficient queries to:

```text
GET  /api/plans
POST /api/plans/generate
POST /api/plans/compare
GET  /api/plans/PLAN_ID
GET  /api/plans/PLAN_ID/report
```

The dashboard must not retrieve full plans merely to populate a plan list.

Only load the full details when the user explicitly opens a particular plan or requests a report.

Do not redesign the WebUI.

## 6.10 Database settings

Keep database configuration conservative.

Use:

```sql
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;
```

WAL mode may be enabled for a local database if the CLI and WebUI require concurrent reads and writes.

Do not rely on WAL for the primary performance improvement.

Do not reduce financial data durability for benchmark speed.

Do not enable aggressive settings that risk database corruption.

### BDD scenarios

```gherkin
Feature: Efficient plan queries

Scenario: Listing twenty plans produces a small result
  Given twenty plans share an immutable household baseline
  When the agent lists the saved plans
  Then twenty compact summaries are returned
  And the JSON response is smaller than 128 KiB
  And historical portfolio state is not included

Scenario: Comparing plans does not retrieve full histories
  Given twenty saved plans use the same source portfolio
  When the agent compares those plans
  Then the response contains financial summary metrics
  And incompatible assumptions are identified
  And the response is smaller than 128 KiB

Scenario: Full plan retrieval is explicit
  Given a saved plan references an immutable baseline
  When the agent requests full plan details
  Then the original target assumptions and proposed trades are returned
  And no unrelated plan is retrieved

Scenario: Reports remain reproducible
  Given a plan has been saved and exported
  When the accepted portfolio changes
  And the historical plan is exported again
  Then both exports contain identical bytes
```

Also cover:

- Empty plan list.
- Invalid plan IDs.
- Different baseline IDs.
- Different price assumptions.
- Different tax assumptions.
- Stale-plan status.
- CLI/WebUI parity.
- Read-only query behavior.
- Account metadata changes that invalidate the baseline.
- Database reopen and report reproducibility.

### Definition of Done

Plan listing and comparison retrieve only small records and perform no unnecessary full-plan deserialization or repeated household hashing.

---

# 7. Package 3 — Faster In-Memory Planning

**Priority: P1**

**Dependencies: Packages 1–2**

## 7.1 Problem

The planning algorithm repeatedly recalculates whole-household allocation differences while iterating over positions and proposed purchases.

Activity transformations also copy portfolio state more often than necessary.

With large portfolios and many alternative plans, these repeated operations create avoidable CPU and memory overhead.

## 7.2 Preserve existing financial logic

Do not change:

- The retirement-first trade planning strategy.
- Taxable lot-selection rules.
- Gain-budget handling.
- Account eligibility.
- Trade increments.
- Cash constraints.
- Security restrictions.
- Wash-sale analysis.
- Reported tax calculations.
- Human-only trade execution.

This package is a computational optimization, not a change to investment strategy.

### Exact-result requirement

For the same deterministic input, the optimized planner must produce the same:

- Trade action sequence.
- Trade quantities.
- Specific lot selections.
- Realized gains and losses.
- Estimated tax effects.
- Cash balances.
- Remaining target drift.
- Relevant warnings.

New plan IDs and timestamps are naturally excluded from exact-result comparisons.

## 7.3 Calculate allocation once

At the start of planning, calculate:

- Total household portfolio value.
- Current value by security.
- Current cash by account.
- Current household cash.
- Target dollar value by security.
- Target cash allocation.

Maintain in-memory Decimal maps for these quantities.

For example:

```python
current_value_by_security = {
    security_id: Decimal("10000.00")
}

cash_by_account = {
    account_id: Decimal("5000.00")
}
```

When a hypothetical trade is applied, update the affected values incrementally.

Calculate overweight and underweight amounts from these maps rather than repeatedly traversing the entire portfolio.

Use existing allocation comparison logic to calculate the initial state and to validate the final state.

## 7.4 Avoid repeated deep copies

Review the path by which hypothetical trades are applied.

If each action deep-copies the entire portfolio, replace that with one initial copy and a shared in-place transformation operating on the working hypothetical state.

For example:

```python
working = deepcopy(baseline)

for action in actions:
    apply_activity_to_working_state(working, action)
```

The same core validation and accounting rules must be used by:

- Confirmed activity recording.
- Hypothetical simulation.
- Trade-plan generation.

Do not create a second, faster implementation with different tax-lot or cash rules.

If necessary, refactor the existing transformation so a small internal function performs validated in-place changes, while the existing public read-only behavior retains its copy-on-write semantics.

## 7.5 Avoid repeated searches

Create appropriate in-memory indexes when preparing a planning run:

```text
positions_by_account_security
lots_by_account_security
accounts_by_id
securities_by_id
cash_by_account
target_weights_by_security
```

Build these indexes once.

Update them as hypothetical actions change the working state.

Do not repeatedly scan the entire position list to find a single security in one account.

## 7.6 Tax correctness

Maintain the existing tax analyzer as the authoritative calculation source.

If an optimization requires fewer analyses, prove that it does not change selected lots, gain budgets, or relevant wash-sale warnings.

Do not introduce approximations to financial calculations for performance.

## 7.7 Final validation

After generating the complete action list:

1. Simulate the proposed trades using the authoritative scenario engine.
2. Calculate the full resulting household allocation.
3. Compare the result against incremental balances.
4. Reject inconsistent results.
5. Persist the validated plan.

Intermediate calculations may be optimized, but the saved final result must remain grounded in the existing domain engine.

Avoid unnecessary duplicate scenario passes unless required for validation.

### BDD scenarios

```gherkin
Feature: Efficient deterministic trade planning

Scenario: Optimized planning preserves exact proposed trades
  Given a synthetic household with taxable and retirement accounts
  And the expected trade plan was calculated by the existing implementation
  When the optimized planner processes the same target
  Then proposed trades and exact lot allocations match the expected plan
  And final cash and allocation values match

Scenario: Gain budgets remain authoritative
  Given a taxable portfolio with multiple gain and loss lots
  And a configured long-term gains budget
  When the optimized planner creates a plan
  Then the gain budget is respected
  And the selected lots match the expected tax-aware result

Scenario: Many securities can be planned without repeated full-state transformations
  Given a household with one thousand current positions
  When a target portfolio plan is generated
  Then the proposed plan is financially consistent
  And the simulation does not modify accepted holdings
```

Also cover:

- Unknown basis.
- Partial tax lots.
- Insufficient cash.
- Excluded positions.
- Retirement account restrictions.
- Fractional mutual-fund increments.
- Multiple eligible accounts.
- Infeasible targets.
- Market-data freshness.
- Potential wash-sale conflicts.
- Simulated action order.

### Definition of Done

The planner avoids redundant portfolio traversals and copies while producing the same deterministic financial results as before.

---

# 8. Package 4 — Performance Verification and Hardening

**Priority: P1**

**Dependencies: Packages 1–3**

## 8.1 Benchmark workload

Reuse the existing synthetic storage benchmark.

The exact workload remains:

```text
10 accounts
1,000 current positions
2,000 tax lots
200 historical account snapshots
20 saved alternative plans
```

Use the same financial inputs and equivalent planning assumptions as the original benchmark.

Run on a disposable SQLite database.

No brokerage accounts, live market APIs, or private user data are required.

## 8.2 Required measurements

Measure and record:

- SQLite database size before generating plans.
- SQLite size after generating 20 plans.
- Total growth from plans.
- Count of unique planning baselines.
- Average baseline JSON size.
- Average plan summary JSON size.
- Average plan details JSON size.
- Total time to generate 20 plans.
- Time to list 20 plans.
- Time to compare 20 plans.
- Time to retrieve one complete plan.
- Time to export a Markdown report.
- Plan-list response size.
- Plan-comparison response size.

Include separate measurements for the planning and persistence portions of plan generation where practical.

Use `time.perf_counter()`.

Do not add a metrics server or telemetry.

## 8.3 Performance targets

These are targets for the documented synthetic benchmark, not claims about every computer or live-data workflow.

| Operation | Previous result | Target |
|---|---:|---:|
| Save 20 alternative plans: additional SQLite storage | ~221 MiB | Under 44 MiB |
| List 20 plans | ~17.9 s | Under 1 s |
| Compare 20 plans | Previously inefficient | Under 1 s |
| Generate 20 plans | ~44.4 s | Under 15 s |
| List response JSON | Potentially hundreds of MiB | Under 128 KiB |
| Compare response JSON | Potentially hundreds of MiB | Under 128 KiB |
| Number of duplicated baselines for identical source state | 20 embedded copies | One shared baseline |

Stretch goal: reduce incremental plan storage by at least 90%.

Performance must be measured using the same environment before and after when possible.

Do not make wall-clock time limits mandatory unit-test assertions.

The response-size and baseline-reuse requirements should be tested deterministically.

If a performance target is missed, profile and document the remaining bottleneck. Do not weaken accounting correctness or introduce new infrastructure merely to hit a number.

## 8.4 Database query verification

Use SQLite query plans to confirm that:

- Listing plans does not scan or deserialize plan detail blobs unnecessarily.
- Single-plan lookup uses the primary key.
- Plan comparison retrieves only selected summaries.
- Baseline lookup uses the primary key.
- Ordering can use the intended index.

Document any query changes required to eliminate demonstrably inefficient operations.

Do not add indexes speculatively.

## 8.5 Memory and response behavior

Ensure:

- Lists do not build complete plan objects internally.
- Comparison does not load unrelated plans.
- Full plan retrieval loads only one baseline.
- Report export does not access live market data.
- Plan generation does not print the entire baseline.
- Large historical snapshot payloads are not duplicated in plan details.

Do not add an in-memory application-wide cache unless a measured bottleneck remains after these changes.

## 8.6 Documentation

Update:

```text
README.md
AGENTS.md
docs/agent-usage.md
docs/data-model.md
docs/plans.md
docs/development.md
```

Document:

- The new planning baseline concept.
- Shared immutable baseline references.
- The distinction between summary and full-detail queries.
- How plan staleness is calculated.
- How historical report reproducibility is preserved.
- The schema reset procedure.
- Benchmark results.
- Any remaining performance limitations.

The documentation must not claim that financial calculations were optimized if their semantics changed.

## 8.7 Full regression verification

Run the complete project suite:

```bash
uv run --locked pytest
uv run --locked ruff check --config pyproject.toml src tests
```

Run the existing offline Docker CI workflow.

Also validate the WebUI plan listing, comparison, detailed plan view, and report export.

### Definition of Done

The documented benchmark demonstrates substantially reduced database growth and fast plan queries, while all financial and regression tests remain green.

---

# 9. Cross-Package Financial Invariants

These requirements apply to all changes.

### Financial state

- Accepted holdings and balances cannot be changed by plan generation.
- Tax-lot accounting must remain exact.
- No cost basis or acquisition date may be invented.
- Missing data must remain explicitly unresolved.
- No automated trades may be executed.
- No financial calculation may silently use newer data when reproducing a historical plan.

### Immutability

- A planning baseline cannot be modified after creation.
- A saved plan cannot be silently altered.
- A target version remains pinned to its plans.
- Historical reports use saved assumptions and calculated results.
- Plan comparisons disclose incompatible baselines and assumptions.

### Determinism

- Identical financial inputs produce identical proposed actions and numerical results.
- Financial precision must remain Decimal-based.
- Hashes must not depend on incidental ordering or timestamps unrelated to planning.
- Optimizations must not change tax and allocation semantics.

### Agent usability

- Common CLI operations emit small JSON responses.
- Detailed data remains explicitly retrievable.
- Error messages remain structured.
- The external coding agent remains the primary interface.
- The WebUI uses the same optimized domain functions.

---

# 10. End-to-End Acceptance Workflow

The final test should exercise this scenario:

> A household contains 10 accounts, 1,000 positions, 2,000 tax lots, and a history of 200 accepted account snapshots. An AI agent proposes 20 target portfolios and generates a plan for each. The user compares all alternatives, selects two plans for closer inspection, and exports reports for both.

Expected behavior:

1. The agent generates the 20 plans without changing accepted holdings.
2. All plans reuse the same immutable portfolio baseline.
3. The full account snapshot history is not embedded in each plan.
4. `invest plan list` quickly returns 20 compact summaries.
5. `invest plan compare` quickly returns comparable allocation and tax metrics.
6. The agent retrieves complete details for only the two interesting plans.
7. Both reports reproduce correctly from persisted information.
8. A later confirmed portfolio change causes the previous plans to be identified as stale.
9. Old reports remain reproducible.
10. New planning uses a new baseline.
11. No new infrastructure or services are required.

---

# 11. Explicitly Out of Scope

Do not implement:

- Migration from the existing database.
- Preservation or conversion of existing saved plans.
- New portfolio algorithms.
- New trading strategies.
- New financial products.
- New data providers.
- Real brokerage HTML validation.
- Live FMP validation.
- New tax-law calculations.
- Cross-household optimization.
- New WebUI pages.
- Automatic trading.
- Database synchronization across machines.
- Cloud storage.
- Background processing.
- Compression or encryption frameworks.
- A generalized caching subsystem.

All existing data may be discarded and recreated for this implementation.

---

# 12. Final Definition of Done

This PRD is complete when:

1. The new SQLite schema initializes successfully from an empty database.
2. No migration or legacy plan-support code is required.
3. Multiple plans reuse shared immutable planning baselines.
4. Historical snapshots are not repeatedly stored inside plans.
5. Compact plan listing and comparison use efficient SQL queries.
6. The current planning fingerprint is calculated once per listing/comparison request.
7. Full plans and reports remain explicitly accessible.
8. Reports remain reproducible after the portfolio changes.
9. The planning hot path avoids redundant household traversals and deep copies.
10. Financial calculations match the previous implementation for deterministic test fixtures.
11. The 20-plan benchmark meets the storage and response-size requirements.
12. Performance timings are recorded and evaluated against the targets.
13. All BDD tests and regression tests pass.
14. Ruff and offline CI pass.
15. The codebase remains small, readable, and easy for an AI coding agent to maintain.

## Guiding Principle

**Store each financial fact once whenever possible. Load only the data an operation actually needs. Calculate only what changed.**

Investobot should remain a trustworthy local investment toolkit whose performance is determined by the financial work requested—not by repeatedly copying, reading, and serializing its entire portfolio history.