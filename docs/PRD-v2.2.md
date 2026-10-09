# Investobot — Final Agent Usability & Classification Audit PRD

**Version:** 2.2  
**Repository:** https://github.com/mdbecker/investobot  
**Baseline:** Commit `d4431be`  
**Priority:** Final MVP stabilization  
**Development methodology:** Strict BDD — Red → Green → Refactor

## 1. Objective

Complete the Investobot MVP by resolving two remaining issues:

1. **Oversized CLI responses:** Plan listing, generation, and comparison expose unnecessarily large financial data structures, making the tools inefficient for AI coding agents.
2. **Classification audit bypass:** Accepting an HTML portfolio snapshot can upgrade an existing `OTHER` security classification without using the explicitly confirmed, audited classification workflow.

Fix these issues with minimal changes to the existing codebase.

The project must remain a small, local, deterministic Python toolkit primarily operated by external AI agents such as Codex and Claude Code.

### Success criteria

An agent should be able to list and compare many saved investment plans using small JSON responses, retrieve full details only when necessary, and trust that every correction to an existing security's classification has been explicitly confirmed and audited.

All existing financial calculations and saved reports must remain unchanged.

---

# 2. Architectural Constraints

Preserve the current architecture:

- Python 3.12+
- Typer CLI
- Pydantic models
- SQLite with standard `sqlite3`
- Decimal-based financial arithmetic
- Existing `ledger.py`, `plans.py`, `contracts.py`, `cli.py`, and WebUI
- pytest + pytest-bdd
- Ruff
- Existing offline Docker CI

Do not introduce:

- New database tables.
- Database schema migrations.
- A new persistence system.
- Compression frameworks.
- Background workers or caching services.
- An ORM.
- Another frontend framework.
- MCP or LLM integrations.
- New financial calculations or planning algorithms.

Reuse existing domain logic and stored financial data.

**Do not rewrite the planner, ledger, or reporting system.**

---

# 3. Mandatory BDD Development Process

Each implementation package must follow this sequence:

1. Write the complete set of new BDD scenarios.
2. Implement pytest-bdd step definitions.
3. Run the scenarios and verify expected failures.
4. Investigate unexpected passes or unrelated failures.
5. Implement the smallest production changes required.
6. Run the scenarios until green.
7. Run the complete existing test suite.
8. Run Ruff.
9. Update relevant documentation.
10. Commit the tested changes.

BDD scenarios must describe observable behavior, not implementation details.

Tests must use synthetic data and require no external API access.

---

# 4. Implementation Order

| Order | Package | Priority | Dependencies |
|---|---|---|---|
| 1 | Compact Plan CLI and API Responses | P0 | None |
| 2 | Classification Audit Enforcement | P0 | Package 1 |
| 3 | Integration Regression and Documentation | P1 | Packages 1–2 |

Complete packages sequentially. Avoid overlapping changes where possible.

---

# 5. Package 1 — Compact Plan CLI and API Responses

**Priority: P0**

**Dependencies: None**

## 5.1 Problem

Saved plans currently include complete portfolio state, historical snapshots, and detailed analysis data.

This is useful for reproducibility but inappropriate for most agent interactions.

The existing benchmark demonstrated:

- Approximately 11 MiB of serialized JSON per saved plan.
- Approximately 221 MiB of database growth from 20 saved alternatives.
- Approximately 18 seconds to list 20 plans.

The current implementation returns full plan objects from operations that should only require summary information.

For a coding agent, this unnecessarily consumes context, increases latency, and makes routine interactions expensive.

## 5.2 Design Decision

Introduce **one shared compact plan-summary representation**.

Use it for:

```bash
invest plan generate
invest plan list
invest plan compare
```

Preserve full plan retrieval through:

```bash
invest plan show PLAN_ID
```

Preserve existing report generation:

```bash
invest report export PLAN_ID --format markdown --output report.md
invest report export PLAN_ID --format json --output report.json
```

Do not change the format of persisted plans.

Do not change the existing `plans.generate()` financial calculations or its full internal result. Apply compact output formatting at the CLI/WebUI boundary while making list and compare load only the fields they need.

## 5.3 Plan Summary Contract

Create one shared summary representation containing:

```json
{
  "id": "PLAN_ID",
  "name": "Candidate portfolio",
  "target_version_id": "TARGET_VERSION_ID",
  "created_at": "2026-10-08T12:00:00Z",
  "as_of": "2026-10-08",
  "status": "READY_FOR_HUMAN_REVIEW",
  "generated_status": "READY_FOR_HUMAN_REVIEW",
  "trade_count": 6,
  "turnover": "25000.00",
  "tax_summary": {
    "short_term_gain_loss": "0",
    "long_term_gain_loss": "1200.00",
    "estimated_tax_effect": null
  },
  "drift_summary": {
    "maximum_absolute_weight_drift": "0.012",
    "positions_outside_tolerance": 2
  },
  "warning_count": 3,
  "warnings_preview": [
    "Example warning"
  ]
}
```

Values above are illustrative.

Requirements:

- All financial decimal values remain JSON strings.
- Unknown financial values remain `null`.
- `status` reflects the current effective status, including `STALE`.
- `generated_status` retains the original saved status.
- Summary values are derived from persisted plan data, not recomputed financial analysis.
- Maximum drift is the largest absolute remaining `difference_weight`.
- Positions outside tolerance are counted using the saved target's tolerance.
- `warnings_preview` contains at most the first five saved warnings, preserving their original order.
- `warning_count` represents the total number of saved warnings.
- Full warnings remain available through `plan show`.

Implement the representation in one shared domain function. Do not maintain separate CLI and WebUI summary logic.

Existing plan records missing an optional summary field must remain readable and return `null` or a safe empty value rather than failing.

## 5.4 Plan Generation

After generating and persisting a plan, the CLI must emit:

```json
{
  "plan": {
    "id": "PLAN_ID",
    "name": "Candidate portfolio",
    "status": "READY_FOR_HUMAN_REVIEW",
    "trade_count": 6
  }
}
```

The `plan` object must contain the complete summary contract defined above; the example is abbreviated.

Do not return:

- Complete source portfolio.
- Historical snapshots.
- Full exposure datasets.
- Full lot inventories.
- Complete proposed action objects.
- Raw external market-data payloads.

The agent can request these explicitly with `plan show` or export a report.

**Generating a plan must remain financially identical to the previous implementation.**

## 5.5 Plan Listing

Change:

```bash
invest plan list
```

to return:

```json
{
  "plans": [
    {
      "id": "PLAN_A",
      "name": "Conservative",
      "status": "READY_FOR_HUMAN_REVIEW"
    },
    {
      "id": "PLAN_B",
      "name": "Growth",
      "status": "STALE"
    }
  ]
}
```

Each entry uses the full compact summary contract.

Requirements:

- Do not return full plan objects.
- Do not include source snapshots or original portfolio state.
- Calculate the current portfolio state hash once for the request.
- Determine each plan's stale status against that hash.
- Return plans ordered by creation time, newest first, with ID as a stable tie-breaker.

### Efficient SQLite reads

Because persisted plans are stored as JSON in SQLite, use SQLite's built-in JSON extraction functionality to select only fields needed for summaries.

Do not load and deserialize every complete saved plan merely to construct its summary.

Avoid repeated calls that read and hash the live household ledger for each plan.

Do not add denormalized database tables or indexes unless profiling demonstrates they are necessary.

## 5.6 Plan Comparison

Change:

```bash
invest plan compare PLAN_A PLAN_B PLAN_C
```

to return compact summaries and comparison metadata.

Response structure:

```json
{
  "plans": [],
  "same_source_snapshot": true,
  "same_price_assumptions": true,
  "same_tax_assumptions": true,
  "same_analysis_date": true,
  "warnings": [],
  "ranking": null
}
```

The `plans` array contains compact summaries, not full objects.

Preserve the existing comparison behavior for:

- Portfolio baseline.
- Price assumptions.
- Tax assumptions.
- Analysis dates.
- Turnover.
- Trade count.
- Tax effects.
- Remaining target drift.
- Stale status.

Comparison warnings must explicitly identify incompatible assumptions.

Do not invent a ranking score.

Do not return full source state, tax-lot inventories, complete exposure datasets, or action lists.

The existing planning and comparison calculations remain authoritative.

## 5.7 Full Plan Retrieval

Preserve:

```bash
invest plan show PLAN_ID
```

as the explicit operation for retrieving complete details.

It should continue returning the complete saved plan, including source state, assumptions, proposed actions, tax analyses, and exposure analyses.

No pagination or truncation is required for this explicit full-detail command.

The documentation must warn agents that full plan retrieval may produce a large JSON response.

For reviewing a plan without loading its entire structure into the agent's conversation, prefer:

```bash
invest report export PLAN_ID --format markdown --output report.md
```

## 5.8 WebUI Compatibility

The WebUI currently shares planning domain functions with the CLI.

Update these endpoints to use the compact response contract:

```text
GET  /api/plans
POST /api/plans/generate
POST /api/plans/compare
```

Retain full retrieval through:

```text
GET /api/plans/PLAN_ID
GET /api/plans/PLAN_ID/report
```

Update the existing frontend to consume compact summaries for lists and comparisons.

If detailed plan information is needed, fetch that specific plan explicitly.

No UI redesign or additional page is permitted.

WebUI and CLI must produce equivalent summary values.

## 5.9 Performance Acceptance

Use the existing synthetic benchmark containing:

- 10 accounts.
- 1,000 positions.
- 2,000 lots.
- 20 snapshots per account.
- 20 saved plans.

Requirements:

- Listing 20 plans must produce less than 128 KiB of JSON.
- Comparing those 20 plans must produce less than 128 KiB of JSON.
- Plan list and comparison must not materialize all saved source portfolio histories.
- Household state must be loaded and hashed at most once per operation.
- Plan generation must not return full portfolio history through the public CLI or WebUI response.
- Benchmark and document the updated list/compare wall-clock times without imposing environment-dependent timing assertions in CI.
- Existing report exports remain byte-for-byte reproducible.

Do not attempt to shrink existing database files during this package.

### BDD scenarios

```gherkin
Feature: Compact plan results for coding agents

Scenario: Listing plans returns concise summaries
  Given a household has twenty saved alternative plans
  When the agent lists the plans
  Then the response contains twenty compact summaries
  And the response is smaller than 128 KiB
  And no source portfolio histories are included

Scenario: Comparing alternatives avoids large financial payloads
  Given twenty plans share the same portfolio baseline
  When the agent compares those plans
  Then comparison returns their financial summary metrics
  And the response is smaller than 128 KiB
  And complete portfolio histories are omitted

Scenario: Plan generation returns a usable identifier
  Given a target portfolio is ready for planning
  When the agent generates a trade plan
  Then the response contains the saved plan ID and summary
  And detailed financial state is not included

Scenario: Full details remain available on request
  Given a saved plan exists
  When the agent requests that specific plan
  Then its complete original assumptions and proposed trades are available

Scenario: A changed portfolio makes a listed plan stale
  Given a plan was generated from an accepted portfolio
  When the accepted portfolio changes
  And the agent lists saved plans
  Then the plan is identified as stale
  And its original generated status remains available
```

Also cover:

- Different price assumptions.
- Different tax assumptions.
- Different analysis dates.
- Unknown tax estimates.
- Missing optional fields in legacy plans.
- CLI/WebUI parity.
- Report reproducibility.
- Invalid plan IDs.
- Empty plan list.

### Definition of Done

An agent can generate, list, and compare multiple plans efficiently without unnecessarily loading enormous portfolio histories into its context.

---

# 6. Package 2 — Classification Audit Enforcement

**Priority: P0**

**Dependencies: Package 1**

## 6.1 Problem

The existing `invest security classify` command correctly requires explicit confirmation and records classification provenance.

However, portfolio snapshot application contains another path that may upgrade an existing `OTHER` security to a supported classification.

This can bypass the dedicated confirmation and classification-history mechanism.

A financial-state change should not have different audit requirements depending on which command caused it.

## 6.2 Design Decision

**All classification changes to an existing canonical security must occur through the existing explicit classification workflow.**

The single authoritative path is:

```bash
invest security classify SECURITY_ID \
  --asset-type ETF \
  --source "Verified issuer documentation" \
  --confirm
```

Do not create another classification API or audit system.

### 6.3 Existing securities

When an incoming HTML snapshot identifies an existing `OTHER` security as a known type:

- Preserve the existing canonical `OTHER` classification.
- Do not upgrade it automatically.
- Do not change the classification of other positions.
- Report that the source suggests a different classification.
- Include the canonical security ID and suggested type in the reconciliation output.
- Instruct the agent to use the explicit classification command.
- Allow otherwise valid holdings updates to proceed.

The incoming snapshot must not create an unaudited classification-history entry.

### 6.4 New securities

When a snapshot introduces a genuinely new security:

- The initially accepted asset type may be stored as part of its original creation.
- This is initial classification, not a change to an established classification.
- Existing identity conflict validation remains mandatory.

Do not require a separate classification command for every newly imported security.

### 6.5 Existing known classifications

For an established security:

| Canonical type | Incoming type | Behavior |
|---|---|---|
| `OTHER` | `OTHER` | Preserve `OTHER` |
| `OTHER` | `ETF` | Preserve `OTHER`; flag for reviewed classification |
| `ETF` | `OTHER` | Preserve `ETF` |
| `ETF` | `ETF` | No change |
| `ETF` | `STOCK` | Reject contradictory known classification |

Apply the equivalent rules to other supported asset types.

A known-versus-known contradiction must reject the affected snapshot application atomically rather than silently reinterpret the security.

### 6.6 Reconciliation

Extend reconciliation with a structured classification review field:

```json
{
  "classification_reviews": [
    {
      "security_id": "CANONICAL_SECURITY_ID",
      "ticker": "VTI",
      "canonical_type": "OTHER",
      "observed_type": "ETF",
      "action_required": "EXPLICIT_CLASSIFICATION"
    }
  ]
}
```

Requirements:

- Present enough information for the agent to identify and correct the security.
- Do not silently modify canonical classification.
- Preserve existing position quantities, values, cash, cost basis, and tax lots.
- Do not persist raw HTML.
- Do not invent a verification source.

The existing WebUI reconciliation results must display the same information.

### 6.7 Confirmed corrections

Keep the existing `classify_security()` implementation as the only classification-correction mechanism.

It must continue to:

- Require an existing canonical security.
- Permit `OTHER` → supported type.
- Require nonempty provenance.
- Require explicit confirmation.
- Update current positions consistently.
- Record classification history.
- Preserve historical snapshots.
- Leave unrelated financial values unchanged.
- Cause affected saved plans to become stale.

Repeated identical corrections must remain idempotent.

### 6.8 Atomicity

Even if a snapshot contains multiple securities, an identity or known-classification conflict must not leave any partial writes.

All validations and canonical state mutations must remain inside the existing atomic application workflow.

### BDD scenarios

```gherkin
Feature: Audited security classifications

Scenario: A snapshot cannot silently upgrade an existing security
  Given VTI is stored with an unknown asset classification
  When a new holdings snapshot identifies VTI as an ETF
  Then reconciliation recommends an explicit classification correction
  And the canonical classification remains unknown
  And accepting the holdings does not classify VTI automatically

Scenario: An explicit correction is audited
  Given an existing security is classified as OTHER
  When the user confirms its ETF classification with verified provenance
  Then the security becomes an ETF
  And its classification history records the change
  And corresponding current positions use the new classification

Scenario: An unknown source classification preserves verified metadata
  Given VTI has a verified ETF classification
  When a new holdings snapshot omits the asset type
  Then VTI remains classified as an ETF

Scenario: A conflicting known classification rejects snapshot acceptance
  Given a security is verified as an ETF
  When a holdings snapshot identifies the same security as a stock
  Then snapshot application is rejected
  And no holdings, cash, or security metadata changes are committed

Scenario: Newly imported securities retain known classifications
  Given a security has never been imported
  When an explicitly accepted snapshot identifies it as an ETF
  Then it is created as an ETF
  And no classification correction is required
```

Also cover:

- Multiple affected accounts.
- Conflicting CUSIP/ISIN/FIGI values.
- Unknown-to-known reconciliation output.
- WebUI warning visibility.
- Idempotent classification.
- Historical snapshot preservation.
- Saved-plan staleness.
- Atomic rejection of a multi-security snapshot.

### Definition of Done

No existing security can change classification through snapshot application without using the explicit audited correction path.

---

# 7. Package 3 — Integration Regression and Documentation

**Priority: P1**

**Dependencies: Packages 1–2**

No new features should be introduced in this package.

## 7.1 Integration tests

Verify that the changes preserve:

- Portfolio import and reconciliation.
- Account metadata preservation.
- Snapshot freshness safeguards.
- Security registration and classification.
- Tax-lot calculations.
- Fund holdings and exposure analysis.
- Target portfolio management.
- Trade-plan generation.
- Plan staleness detection.
- Plan comparison.
- Saved report exports.
- WebUI dashboard and plan views.
- Prompt library functionality.

Pay particular attention to avoiding duplicate financial logic between CLI and WebUI.

## 7.2 Existing plan compatibility

Previously saved plans must remain readable.

Do not require users to regenerate their targets or existing plans.

Verify:

- Compact summaries work for existing plan records.
- Complete plan retrieval is unchanged.
- Report export remains reproducible.
- Current stale-status evaluation is correct.
- No database migration is required.

## 7.3 Documentation

Update only relevant existing documentation:

```text
README.md
AGENTS.md
docs/agent-usage.md
docs/plans.md
docs/data-model.md
docs/workflows.md
docs/inspection.md
docs/development.md
```

Document the recommended agent workflow:

```text
plan generate
    ↓
compact plan summary
    ↓
plan list / plan compare
    ↓
select interesting alternatives
    ↓
plan show OR report export
    ↓
human review
```

Make clear that `plan show` is intentionally a potentially large response.

For classification, explain the difference between:

- Initial security classification during creation.
- Unverified classifications suggested by imported snapshots.
- Explicitly confirmed corrections to existing securities.

Update `invest tools describe` contracts to reflect the compact plan output and classification reconciliation behavior.

Do not create a second documentation system.

## 7.4 Verification

Run:

```bash
uv run --locked pytest
uv run --locked ruff check --config pyproject.toml src tests
```

Also run the existing offline Docker CI workflow.

Validate the existing synthetic plan-storage benchmark and record its updated listing/comparison measurements.

### Definition of Done

All regression tests pass, financial state and saved plans remain unchanged by read-only commands, and documentation accurately describes the new behavior.

---

# 8. Global Acceptance Criteria

The PRD is complete when:

1. `invest plan list` returns compact plan summaries.
2. `invest plan compare` returns compact side-by-side results.
3. `invest plan generate` returns a compact confirmation and summary.
4. `invest plan show` retains complete plan retrieval.
5. Historical report exports remain reproducible.
6. Listing/comparing 20 synthetic plans stays below 128 KiB of JSON per response.
7. Plan listing does not repeatedly deserialize entire saved portfolio histories.
8. Stale plans are identified correctly.
9. Snapshots cannot silently change an existing security from `OTHER` to another type.
10. Classification suggestions are visible during reconciliation.
11. Known classification conflicts are rejected atomically.
12. Confirmed classification changes remain audited.
13. Existing portfolio, tax, target, and scenario calculations remain correct.
14. All BDD scenarios and regression tests pass.
15. CI and Ruff pass.
16. No new architectural complexity is introduced.

---

# 9. Explicitly Out of Scope

Do not implement:

- Saved-plan database compression or deduplication.
- A redesigned plan persistence model.
- Real brokerage HTML validation.
- Live FMP integration testing.
- Additional market-data subscriptions.
- New tax calculations.
- New portfolio optimization algorithms.
- New investment research features.
- Additional WebUI pages.
- Any agent execution framework.
- Automated trading.
- New infrastructure.

The measured database storage growth is acknowledged but remains outside this PRD. The immediate problem is unnecessary retrieval and transmission of large financial payloads.

---

# 10. Final Definition of Done

This stabilization effort is complete when the existing financial functionality remains green and the two targeted issues are demonstrably resolved.

The implementation should require only a focused set of changes to:

```text
src/invest/plans.py
src/invest/ledger.py
src/invest/cli.py
src/invest/contracts.py
src/invest/web.py
src/invest/static/app.js
tests/
docs/
```

Modify other files only when required for consistent behavior.

The final implementation must preserve:

- Deterministic financial calculations.
- Explicit human confirmation for financial state changes.
- Immutable historical plans and reports.
- Small, composable CLI tools.
- Browser-first research by the external agent.
- Human-only trade execution.

**After this PRD is complete, Investobot should be considered code-complete for the current MVP scope, with real-world brokerage and market-data validation remaining a separate release gate.**

## Guiding Principle

Investobot should give a coding agent exactly the information it needs for the current task—not dump its entire financial database into every conversation.

Detailed financial data must remain available when explicitly requested, while changes to authoritative financial state must be deliberate, traceable, and auditable.