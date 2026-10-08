# Investobot — Financial Correctness, Target Portfolios & Agent-First Planning

**Product Requirements Document — Version 2.0**

**Repository:** https://github.com/mdbecker/investobot  
**Baseline:** Existing MVP implementation, reviewed at commit `67555c4`  
**Development methodology:** Strict BDD (Red → Green → Refactor)  
**Primary interface:** CLI tools used by Codex, Claude Code, or another browser-equipped coding agent  
**Secondary interface:** Local WebUI for portfolio inspection, target management, plan comparison, and reusable prompts

---

## 1. Objective

Improve the existing Investobot implementation and extend it into a reliable, tax-aware household investment planning toolkit.

The system must allow an external AI agent to:

1. Maintain accurate portfolio state from manually supplied brokerage HTML.
2. Analyze holdings, tax lots, gains, losses, and household-wide exposures.
3. Research investment opportunities using its own browser and Investobot's structured CLI tools.
4. Create and maintain multiple hypothetical target portfolios.
5. Compare current holdings against proposed targets.
6. Generate account-aware, tax-conscious trade plans.
7. Simulate and compare alternative portfolios and their tax consequences.
8. Produce clear reports containing proposed trades for human review.
9. Reconcile actual portfolio changes after the human executes trades manually.

**The AI agent never executes trades. Investobot never authenticates with brokers or submits orders.**

The existing implementation is the foundation. Preserve working functionality and avoid unnecessary rewrites.

### Success criteria

A user should be able to ask their coding agent:

> Research ways to reduce my technology concentration while keeping realized long-term gains below $5,000. Create three target portfolios, generate tax-aware trade plans for each, and save reports I can compare.

The agent must be able to accomplish this using Investobot's CLI tools and its existing browser capabilities, without implementing new financial calculations itself.

---

## 2. Architecture Decisions

These decisions are fixed for this PRD.

### Preserve the existing architecture

- Python 3.12+
- `uv`
- Typer CLI (`invest`)
- Pydantic models
- SQLite using the standard `sqlite3` library
- Decimal for financial arithmetic
- Existing tax, ledger, analytics, market, bond, and scenario modules
- pytest + pytest-bdd
- Ruff
- Existing lightweight HTML/CSS/JavaScript WebUI

Do not introduce:

- React or another frontend framework
- an ORM
- MCP
- LLM API integrations
- broker APIs
- Plaid
- microservices
- cloud storage
- background workers
- message queues
- complex optimization frameworks
- a second implementation of existing financial calculations

Refactor existing code only where necessary to fix correctness problems, remove duplication, or support new functionality.

### CLI is authoritative

All functionality must be available through the CLI.

The WebUI must call the same domain functions and must never maintain a separate implementation of portfolio or tax logic.

Use JSON for successful CLI output and machine-readable errors.

### Browser-first research

The external agent uses Chrome for qualitative and current public research.

Investobot provides:

- persistent financial state
- tax calculations
- fund holdings comparisons
- exposure calculations
- structured market data
- portfolio simulation
- target portfolios
- trade planning
- reporting

Do not build news feeds, web scrapers, or an agent/chat interface into Investobot.

### Actual versus hypothetical state

Maintain strict separation among:

- **Actual portfolio:** confirmed holdings and balances.
- **Target portfolio:** desired allocation, independent of actual state.
- **Trade plan:** hypothetical trades intended to move actual holdings toward a target.
- **Confirmed activity:** an actual transaction explicitly supplied or confirmed by the user.

Neither creating a target nor generating a plan may modify actual portfolio state.

---

# 3. Mandatory BDD Development Process

Every work package below must follow this sequence:

1. Write all new BDD scenarios for that package.
2. Implement their pytest-bdd step definitions.
3. Run the scenarios and verify they fail for the expected missing or incorrect behavior.
4. Investigate unexpected passes or unrelated failures.
5. Only then implement production changes.
6. Run the scenarios until green.
7. Run the complete existing test suite.
8. Run Ruff.
9. Update affected documentation.
10. Commit the tested implementation.

All tests must describe observable financial or user behavior.

Example:

```gherkin
Scenario: A manually recorded sale preserves the correct remaining tax lots
  Given a taxable account holds two lots of the same ETF
  And the investor sold shares from the newer lot
  When the confirmed sale is recorded with that lot selection
  Then the newer lot's remaining quantity is reduced
  And the older lot remains unchanged
  And the portfolio quantity matches the remaining lots
```

Do not test internal function calls, private methods, or collaborator order.

Prefer synthetic real-world financial examples. Mock external services at their boundaries, not internal domain functions.

**No production implementation may begin in a package until its new BDD tests have been written and observed failing.**

---

# 4. Implementation Plan

Complete work packages in the order shown unless explicitly marked independent.

| Order | Priority | Work package | Dependencies |
|---|---|---|---|
| 1 | P0 | Import and reconciliation correctness | None |
| 2 | P0 | Ledger and confirmed-trade correctness | 1 |
| 3 | P0 | Tax and portfolio analytics correctness | 1, 2 |
| 4 | P1 | Agent-first CLI and runtime improvements | 1–3 |
| 5 | P1 | Target portfolio management | 1–4 |
| 6 | P1 | Tax-aware trade planning and reports | 1–5 |
| 7 | P2 | WebUI and prompt library | 5, 6 |
| 8 | P1 | End-to-end verification and hardening | All preceding packages |

**Packages 1–3 are a release gate.** Do not develop or merge new planning functionality before their correctness requirements are satisfied.

Packages should minimize overlapping file changes. Extend existing modules where appropriate rather than creating parallel implementations.

---

# 5. Package 1 — Import and Reconciliation Correctness

**Priority: P0**

**Dependencies: None**

## Problem

The existing import/reconciliation flow can produce incorrect or incomplete portfolio state.

Known issues include:

- Multiple tax-lot rows for one security can produce incorrect aggregate cost basis.
- Reconciliation does not fully report valuation-only changes.
- Partial snapshots can replace more complete existing state.
- Stale snapshots may overwrite newer information.
- Generic HTML parsing is not validated against real institution pages.
- Missing lot information is not always distinguished from intentionally removed lots.

These issues must be fixed before trusting downstream financial calculations.

## Requirements

### 5.1 Correct aggregation

When multiple source rows represent lots of the same security:

- Aggregate position quantities and values correctly.
- Aggregate known cost basis correctly.
- Preserve each distinct tax lot.
- Preserve available security identifiers.
- Reject inconsistent duplicate rows rather than silently dropping them.

Do not combine rows belonging to different securities merely because names or tickers appear similar.

### 5.2 Snapshot completeness

Extend normalized snapshots with explicit completeness information:

```text
positions_complete
lots_complete
cash_known
```

All fields are booleans.

A generic HTML import must default to incomplete coverage unless the user explicitly confirms completeness.

Rules:

- An incomplete positions snapshot updates only explicitly observed positions.
- Missing positions in incomplete snapshots must not be deleted.
- Missing lots must not delete previously known lots unless complete lot coverage is explicitly confirmed.
- A complete snapshot may replace the relevant account inventory after validation.
- Changes that make position quantities inconsistent with retained lot information must mark tax-lot state unresolved until reconciled.

Do not infer transactions from changes in holdings.

### 5.3 Reconciliation

Reconciliation must detect:

- added/removed positions;
- quantity changes;
- price changes;
- market-value changes;
- aggregate cost-basis changes;
- lot changes;
- cash changes;
- account classification changes;
- missing or inconsistent data.

The result must distinguish:

```text
CONFIRMED_VALUE
CHANGED_VALUE
UNKNOWN_VALUE
CONFLICT
```

where applicable.

### 5.4 Snapshot freshness

Maintain source and import timestamps separately.

An older snapshot must not overwrite newer state without an explicit override and recorded justification.

A source page without a known date must be marked as having an unknown source timestamp; its import timestamp is not proof of valuation freshness.

Applying an identical snapshot twice must not create duplicate state transitions.

### 5.5 Import safety

Maintain the existing preview → reconcile → apply workflow.

Reject dangerous or contradictory imports before applying any changes.

All mutations must remain atomic.

Raw HTML must not be persisted in SQLite or application logs.

## BDD coverage

At minimum:

- Multiple lots with different cost bases.
- Price-only changes.
- Market-value-only changes.
- Partial snapshot missing an existing position.
- Missing lot table.
- Complete snapshot removing a position.
- Older snapshot.
- Duplicate import.
- Conflicting identifiers.
- Unsupported HTML table.
- Invalid account classification.
- Failed application leaves database unchanged.

## Done when

The system can import successive account snapshots without silently losing holdings, basis, lot history, or valuation changes.

---

# 6. Package 2 — Ledger and Confirmed-Trade Correctness

**Priority: P0**

**Dependencies: Package 1**

## Problem

Manual activity recording currently has correctness risks.

In particular:

- Sales can consume FIFO lots even when different lots were actually sold.
- Position values can be repriced incorrectly using a transaction's execution price.
- Duplicate activity submissions can apply twice.
- Sales can leave inconsistent lot inventories.
- Cash transfers and transaction classifications require stronger validation.

## Requirements

### 6.1 Recorded trades

Require a unique `activity_id` for every confirmed activity.

Recording the same `activity_id` with identical content twice must be a no-op.

Reusing an existing `activity_id` with different content must produce a conflict error.

### 6.2 Lot selection

Confirmed taxable sales must support explicit executed lot allocations.

Do not silently substitute FIFO when the actual broker lot selection is unknown.

If the user cannot supply lot information:

- Record the confirmed activity.
- Update confirmed position quantity and cash where sufficient information exists.
- Mark the affected lot/basis state unresolved.
- Prevent subsequent tax calculations from treating unresolved lots as authoritative.

When explicit allocations are supplied, update exactly those lots and reject inconsistent quantities.

### 6.3 Valuation correctness

An executed trade price is not automatically the market price for the remaining position.

Separate:

```text
transaction_execution_price
position_market_price
position_market_value
```

Recording a transaction must not silently revalue all remaining shares at the transaction execution price.

Position values can subsequently be refreshed by accepted snapshots or explicit valuation updates.

### 6.4 Transfers

Distinguish:

- cash movement within an account;
- transfers between accounts;
- security transfers;
- retirement contributions/rollovers.

For MVP, do not simulate unrestricted transfers between accounts with different tax treatments.

Require the user/agent to classify a cross-account movement explicitly.

Do not implement contribution-limit or rollover eligibility calculations in this package. Unsupported or unclassified movements must be rejected or marked as requiring review.

### 6.5 Audit history

Preserve:

- confirmed activities;
- unique IDs;
- timestamps;
- source of confirmation;
- affected account/security;
- lot allocations where known;
- reconciliations against later snapshots.

Do not create fictional activity records from differences between snapshots.

## BDD coverage

- Explicit lot sale.
- Partial-lot sale.
- Sale with unknown lot selection.
- Sale exceeding available shares.
- Duplicate activity submission.
- Conflicting duplicate activity ID.
- Buy at a price different from latest market valuation.
- Transaction with fees.
- Insufficient cash.
- Cross-account movement requiring classification.
- Subsequent snapshot confirms recorded activity.
- Failed activity leaves state unchanged.

## Done when

Confirmed trades cannot silently corrupt positions, cash, or tax-lot state.

---

# 7. Package 3 — Tax and Exposure Accuracy

**Priority: P0**

**Dependencies: Packages 1 and 2**

## Problem

The existing tax and exposure tools are useful but need stronger data-consistency guarantees before being used for trade planning.

## Requirements

### 7.1 Tax analysis prerequisites

Before tax calculations, verify:

- account tax classification;
- available lot quantities;
- acquisition dates;
- cost basis;
- consistency with position quantities;
- source freshness;
- known household history completeness.

If critical information is unavailable, return `INSUFFICIENT_DATA`.

Do not invent tax basis or assume incomplete history is complete.

### 7.2 Tax calculations

Preserve FIFO, LIFO, HIFO, SPECIFIC and MIN_TAX selection.

Ensure:

- short- and long-term gain/loss calculations are correct;
- selected-lot quantities are exact;
- sale fees are handled consistently;
- reported tax estimates disclose assumptions;
- non-taxable account trades do not create fictional taxable gains;
- account-specific tax treatment is respected.

Tax estimates must distinguish:

```text
realized_short_term_gain_loss
realized_long_term_gain_loss
estimated_current_tax_effect
potential_wash_sale_conflict
tax_data_completeness
```

Estimated current tax effects are not guaranteed tax savings. Maintain the existing conservative treatment of wash sales.

### 7.3 Household wash-sale checks

Inspect known same-security purchases across all relevant loaded accounts, including retirement accounts.

Continue warning about:

- unknown outside accounts;
- incomplete transaction histories;
- future replacement purchases;
- substantially-identical securities that are not identical tickers.

Do not implement a full tax-filing engine or automatic wash-sale basis adjustments.

### 7.4 Security identity normalization

Use one consistent identity-resolution mechanism for fund comparison and household look-through.

Resolve using strong identifiers when available:

```text
CUSIP
ISIN
FIGI
```

Ticker matching may be used only when unambiguous and must be marked as lower confidence.

Never merge conflicting strong identities because their tickers match.

### 7.5 Look-through correctness

Direct and indirect holdings of the same security must aggregate properly.

Unknown or unresolved holdings must remain visible in reported exposure.

Preserve:

- source;
- as-of date;
- percentage of fund holdings represented;
- unresolved exposure;
- identifier confidence.

### 7.6 Data integrity

Review fund weight normalization, history alignment, total-return assumptions, and exposure calculations against synthetic known-answer examples.

Do not add new market-data providers.

## BDD coverage

- A specific-lot sale generates the expected ST/LT gain.
- Missing lots prevent reliable tax estimation.
- An IRA purchase creates a potential wash-sale conflict.
- Unknown household history produces a warning.
- A sale containing both winning and losing lots reports each correctly.
- Direct AAPL and ETF-owned AAPL aggregate correctly.
- Conflicting identifiers remain separate.
- Partial fund holdings produce unknown exposure.
- Stale market data is disclosed.
- Simulations with unavailable tax data never report guaranteed tax savings.

## Done when

Tax and exposure calculations produce internally consistent, conservative results suitable for human-reviewed planning.

---

# 8. Package 4 — Agent-First CLI Improvements

**Priority: P1**

**Dependencies: Packages 1–3**

## Objective

Make Investobot especially easy for Codex, Claude Code and other coding agents to discover and operate correctly.

## Requirements

### 8.1 Native CLI

Support local execution as the preferred agent interface:

```bash
uv sync --locked
uv run invest portfolio summary
```

Preserve Docker for users who want the WebUI or isolated execution.

Docker must not be required for ordinary CLI usage.

Ensure native and Docker configurations can explicitly point to the same database without accidentally creating divergent ledgers.

### 8.2 Structured command discovery

Extend the existing `invest schema` functionality.

Support:

```bash
invest tools list
invest tools describe portfolio.simulate
```

Return machine-readable descriptions of:

- command purpose;
- required inputs;
- supported options;
- JSON input schema;
- output schema or documented output contract;
- whether the command mutates persistent state.

Use existing Pydantic models as the schema source where possible.

Do not introduce a second manually maintained schema system.

### 8.3 Agent instructions

Update `AGENTS.md` and `docs/agent-usage.md`.

Specify:

- when to use CLI versus browser;
- correct import/reconciliation workflow;
- how to verify data freshness;
- how to manage unknown financial information;
- how to simulate without committing;
- how to create and compare plans;
- how to generate reports;
- mandatory human execution.

### 8.4 Consistent error behavior

All CLI tools must return standardized errors and exit codes.

Failed commands must not produce partial successful output or unintended financial mutations.

## BDD coverage

- Agent discovers available commands.
- Agent retrieves a command schema.
- Native CLI uses configured database.
- Read-only commands do not change portfolio state.
- Invalid inputs produce structured errors.
- Mutating commands are explicitly identified.

## Done when

An agent can use the tools reliably without reverse-engineering Python implementation details.

---

# 9. Package 5 — Target Portfolio Management

**Priority: P1**

**Dependencies: Packages 1–4**

## Objective

Introduce persistent target portfolios independent of actual holdings.

## Requirements

### 9.1 Target model

A target portfolio contains:

```text
id
name
description
version
status
created_at
updated_at
target_allocations
planning_constraints
```

Statuses:

```text
DRAFT
ACTIVE
ARCHIVED
```

Only one target may be active at a time.

Target allocations are household-level target weights for canonical security IDs plus cash.

Weights must total 100% within a small explicit decimal tolerance.

MVP targets are defined using actual investable securities, not vague classifications such as "growth" or "moderate risk."

Target edits create new immutable versions.

### 9.2 Account eligibility

A target is household-wide. Individual account restrictions belong in its planning constraints.

The planner must not assume that every asset can be bought in every account.

Store:

- accounts eligible for planning;
- permitted securities or fund choices where accounts are restricted;
- positions excluded from trading;
- cash minimums;
- target tolerance;
- tax-gain budgets.

Unknown account trading eligibility must not be interpreted as unrestricted trading.

### 9.3 CLI

Implement:

```bash
invest target save target.json
invest target list
invest target show TARGET_ID
invest target activate TARGET_ID
invest target archive TARGET_ID
invest target diff TARGET_ID
```

`target diff` calculates current-versus-target allocation and dollar differences.

It does not propose or execute trades.

### 9.4 Persistence

Add minimal SQLite tables for targets and target versions.

Use the existing explicit migration mechanism.

Do not introduce a new persistence architecture.

## BDD coverage

- Create valid target.
- Reject weights not totaling 100%.
- Create multiple hypothetical targets.
- Edit creates a new version.
- Activate one target.
- Activate another target.
- Compare actual holdings to target.
- Restrict unavailable investments by account.
- Archiving a target preserves historical plans.
- Target changes never modify actual holdings.

## Done when

The user and agent can create, save, version, activate, and compare multiple target portfolios.

---

# 10. Package 6 — Tax-Aware Trade Planning and Reports

**Priority: P1**

**Dependencies: Packages 1–5**

This is the main new product capability.

## Objective

Generate realistic proposed trades to move a household portfolio toward a target while considering account restrictions, tax impact, and user-defined constraints.

## Requirements

### 10.1 Planning input

The planner accepts:

```text
target portfolio version
current portfolio snapshot
market price assumptions
eligible accounts
trade restrictions
minimum cash balances
realized gain budgets
allocation tolerance
```

The planner must use canonical portfolio state and existing deterministic analysis functions.

### 10.2 Planning strategy

Use a deterministic, explainable heuristic.

Do not introduce a general-purpose mathematical optimization solver for MVP.

Planning sequence:

1. Calculate target dollar allocations.
2. Identify current overweight and underweight securities.
3. Exclude unavailable, restricted, or unresolved positions.
4. Consider eligible tax-advantaged account reallocations first where doing so can reduce taxable realizations.
5. Consider eligible taxable sales using known tax lots and estimated tax costs.
6. Respect short-term and long-term realized-gain budgets separately.
7. Fund candidate purchases using available account cash and proposed same-account sale proceeds.
8. Apply account-specific trade increments and cash restrictions.
9. Simulate the entire resulting action list using the existing scenario engine.
10. Report achieved allocation and remaining drift.

Do not assume the target can always be reached.

Prefer an explicitly incomplete plan over one that violates constraints or invents missing data.

The heuristic is not claimed to produce a globally optimal portfolio.

### 10.3 Asset support

Automatically generated trade plans initially support:

- stocks;
- ETFs;
- mutual funds;
- cash allocations.

Support fractional mutual-fund units where account rules allow them. Use configurable trade increments; default stocks and ETFs to whole shares unless fractional eligibility is known.

Individual bonds remain available for portfolio valuation, exposure and explicit scenario analysis, but must not receive automatically generated trade instructions without verified security-specific pricing and trading increments.

Restricted 401(k) holdings must only use explicitly permitted investments.

### 10.4 Plan persistence

Persist immutable plans with:

```text
id
name
target_version_id
source_snapshot_ids
created_at
market_data_as_of
assumptions
proposed_actions
tax_analysis
exposure_analysis
remaining_target_drift
warnings
status
```

Statuses:

```text
DRAFT
REVIEW_REQUIRED
READY_FOR_HUMAN_REVIEW
STALE
```

A plan may not receive `READY_FOR_HUMAN_REVIEW` if critical tax, price, account eligibility or quantity data is unresolved.

All plans still require a human decision.

A change to actual portfolio state marks affected plans stale. Recalculation creates a new plan rather than silently modifying the original.

### 10.5 Scenario and plan comparison

Support several plans based on the same source portfolio snapshot.

Compare:

- achieved allocation;
- remaining target drift;
- account-level changes;
- trade count;
- total turnover;
- realized short-term gains/losses;
- realized long-term gains/losses;
- estimated current tax effect;
- cash remaining;
- concentration/exposure changes;
- unresolved risks.

Comparisons must indicate when plans use different source snapshots or price assumptions.

Do not conceal non-comparable assumptions behind a single ranking score.

### 10.6 CLI

Implement:

```bash
invest plan generate --target TARGET_ID
invest plan list
invest plan show PLAN_ID
invest plan compare PLAN_A PLAN_B
invest report export PLAN_ID --format markdown --output report.md
invest report export PLAN_ID --format json --output report.json
```

Report export writes to the requested file and emits a JSON confirmation containing the path and content hash.

### 10.7 Trade report

Each trade plan report must include:

1. Target portfolio and rationale/description.
2. Source portfolio snapshot date.
3. Market data assumptions and timestamps.
4. Current versus proposed allocation.
5. Proposed manual trades, organized by account.
6. Specific lots proposed for taxable sales.
7. Estimated realized ST/LT gains and losses.
8. Estimated tax effects where rates are configured.
9. Known wash-sale concerns and limitations.
10. Cash balances before and after.
11. Remaining target drift.
12. Missing information and unresolved constraints.
13. Explicit statement that trades are not executed automatically.

Provide concise tables in Markdown.

The agent may separately add current-news research and qualitative investment reasoning to the final user-facing discussion.

Do not add PDF export in this package.

## BDD coverage

- Target achievable entirely in an IRA without realizing taxable gains.
- Target requires taxable sale with specified lots.
- Tax budget prevents a proposed sale.
- Insufficient cash prevents a proposed purchase.
- Restricted retirement account prevents an unavailable fund purchase.
- Multiple accounts require coordinated planning.
- Target cannot be fully achieved.
- Missing basis produces review-required plan.
- Changing source portfolio makes an existing plan stale.
- Two plans compare correctly.
- A plan simulation never changes actual state.
- Generated report matches persisted plan inputs and calculations.

## Done when

An agent can generate, persist, explain, compare, and export multiple tax-aware trade plans for human review.

---

# 11. Package 7 — WebUI and Prompt Library

**Priority: P2**

**Dependencies: Packages 5 and 6**

## Objective

Make the existing WebUI a useful companion dashboard without competing with the external AI agent.

Preserve the existing static HTML/CSS/JavaScript architecture and local HTTP server.

Do not introduce a frontend framework or chatbot.

## Requirements

### 11.1 Navigation

Organize the WebUI into five primary areas:

```text
Overview
Targets
Plans
Prompt Library
Import & Reconcile
```

Existing deterministic analysis functionality may remain accessible from a secondary analysis area.

### 11.2 Overview

Display:

- household portfolio value;
- account balances;
- allocations;
- current versus active target;
- allocation drift;
- major concentrations;
- unresolved exposure;
- data freshness;
- available cash;
- tax-lot data warnings.

Do not replace calculation outputs with browser-side approximations.

### 11.3 Targets

Allow users to:

- inspect saved targets;
- create/edit draft targets;
- activate a target;
- compare a target with current holdings;
- review historical target versions.

All writes must invoke the same domain validation used by the CLI.

### 11.4 Plans

Display:

- saved plans;
- target allocation comparisons;
- proposed trades;
- tax impact summaries;
- remaining drift;
- warnings;
- source snapshot information;
- downloadable reports.

No order execution controls.

### 11.5 Prompt Library

Add a lightweight local prompt library.

Built-in prompts should cover:

- tax-loss harvesting;
- portfolio concentration;
- ETF/mutual-fund comparisons;
- stock research;
- bond research;
- target portfolio generation;
- tax-aware rebalancing;
- comparing alternative portfolios;
- reviewing recent investment developments.

Prompts are plain Markdown stored locally.

Users can:

- view;
- copy;
- create;
- edit;
- delete user-created prompts.

Bundled defaults remain recoverable and are not modified in place.

Use filenames or stable slugs as identifiers. Do not add a database schema or plugin system for prompts.

Prompt content is displayed as text, not executed by Investobot.

**No chat UI, model selector, agent runner, or agent execution endpoint.**

### 11.6 Local security

Keep the WebUI loopback-only.

Preserve existing request validation, same-origin protections, payload limits, and no-raw-HTML-persistence behavior.

Prompt file operations must reject path traversal and access outside configured prompt directories.

## BDD coverage

- Dashboard displays accepted portfolio values.
- Target activation updates the displayed comparison.
- Saved plan displays expected trades and tax values.
- Stale plan is visibly identified.
- Copying a prompt returns its full text.
- User creates and edits a prompt.
- Bundled prompt remains unchanged.
- Invalid prompt path is rejected.
- WebUI never executes agent commands or trades.
- CLI and WebUI display identical domain calculations.

## Done when

The WebUI is a practical portfolio dashboard, planning viewer, and prompt library—not another AI agent interface.

---

# 12. Package 8 — End-to-End Validation and Hardening

**Priority: P1**

**Dependencies: Packages 1–7**

## Objective

Verify the complete product using realistic workflows and ensure it is maintainable by another developer.

No major new functionality should be introduced.

## Requirements

### 12.1 Realistic import validation

Obtain anonymized representative HTML samples for supported institutions.

Validate import behavior against actual table shapes.

The project must not claim confirmed institution support until representative samples pass tests.

At minimum, cover:

- standard brokerage holdings;
- tax-lot details;
- retirement account holdings;
- mutual funds;
- bank/cash balances;
- partial HTML pages.

Preserve synthetic fixtures for tests. Never commit private account data.

### 12.2 Structured data integration

Validate live FMP behavior manually using test credentials.

CI remains fully offline with deterministic fixtures.

Confirm fund-holdings coverage, pricing formats, metadata, caching and error behavior.

Do not assume vendor responses match synthetic fixtures without verification.

### 12.3 CI

Add a minimal GitHub Actions workflow running:

```bash
uv sync --locked
uv run pytest
uv run ruff check src tests
```

Use Python 3.12.

No credentials or external network data calls are required for tests.

### 12.4 Documentation

Update:

```text
README.md
AGENTS.md
docs/agent-usage.md
docs/data-model.md
docs/tax-limitations.md
docs/data-sources.md
docs/workflows.md
docs/inspection.md
```

Add concise documentation for targets, plans, and reports.

The README should begin with the agent-first CLI workflow rather than Docker/WebUI setup.

Include working examples for:

- import and reconciliation;
- tax-loss harvesting;
- ETF comparison;
- target creation;
- target-to-trades planning;
- comparing alternative plans;
- report generation;
- confirmation of actual manual trades.

### 12.5 Regression and migration safety

Verify:

- existing ledger data survives migrations;
- existing historical snapshots remain readable;
- errors do not cause partial commits;
- previously confirmed activities remain intact;
- targets and plans never alter actual holdings;
- old reports remain reproducible;
- sensitive financial data never enters logs.

### 12.6 Code quality

Keep modules focused.

Avoid introducing abstraction layers unless at least two real consumers require them.

Prefer extending existing Pydantic models and domain functions to copying their logic into new services.

Remove dead code and unused dependencies discovered during implementation.

Do not perform an unrelated rewrite.

## Done when

The entire repository test suite passes, documentation matches actual behavior, and the acceptance workflows below work against representative fixtures.

---

# 13. End-to-End Acceptance Workflows

The product is complete when all four workflows succeed.

## Workflow A — Portfolio synchronization

**User request:**

> Here is the latest HTML from my accounts. Update my portfolio.

Expected behavior:

1. Agent imports and previews HTML.
2. Reconciliation identifies changes, including quantities, valuations, cash, and lots.
3. Ambiguous or incomplete information is reported.
4. User or explicitly authorized workflow accepts the snapshot.
5. Actual ledger updates without losing unrelated historical information.
6. Previous plans become stale when relevant state changes.

## Workflow B — Tax-loss harvesting

**User request:**

> Find potential tax-loss-harvesting opportunities and suitable replacement ETFs. Research recent conditions before recommending anything.

Expected behavior:

1. Agent retrieves known loss lots.
2. Tax tools analyze proposed sales and household wash-sale risks.
3. Structured tools compare ETF holdings, overlap and historical correlation.
4. Agent uses Chrome for current fund research.
5. Agent generates hypothetical replacement scenarios.
6. Human receives a report with proposed trades, lots, tax estimates, and warnings.

No trades execute automatically.

## Workflow C — Target portfolio planning

**User request:**

> Create a 65% equities, 30% bonds, 5% cash portfolio using appropriate ETFs and mutual funds. Minimize taxable gains.

Expected behavior:

1. Agent researches suitable securities.
2. Agent creates a draft target whose investable security weights total 100%.
3. Investobot calculates current-versus-target differences.
4. Planner generates account-aware trades.
5. Planner respects trading restrictions and gain budgets.
6. Simulator calculates the resulting portfolio and tax impact.
7. Human receives a saved, reviewable plan.

If a complete plan is infeasible, the report clearly describes the remaining drift and constraints.

## Workflow D — Alternative portfolio comparison

**User request:**

> Compare a conservative, balanced and growth-oriented target portfolio. Show what each would cost in taxes and how much trading each requires.

Expected behavior:

1. Agent creates three candidate targets.
2. Each is planned against the same source portfolio snapshot.
3. Investobot generates three separate plans.
4. All plans preserve their assumptions and input data.
5. Agent compares tax impacts, turnover, allocations, exposure and remaining drift.
6. WebUI displays the alternatives.
7. Human may activate one target without executing any trade.

---

# 14. Global Safety and Correctness Requirements

These apply to every package.

### Financial correctness

- Never invent missing basis or acquisition dates.
- Never infer a transaction solely from a position change.
- Never assume cross-account transfers are unrestricted.
- Never treat tentative plans as actual holdings.
- Never claim wash-sale safety when relevant information is missing.
- Never claim a portfolio plan is globally optimal.
- Never silently use stale prices as current prices.

### Reproducibility

Every persisted plan must identify the actual portfolio state, target version, relevant prices, tax assumptions, and restrictions used to generate it.

### Privacy

- Local SQLite database only.
- No telemetry.
- No brokerage credentials.
- No raw HTML persistence.
- No accidental publication of the WebUI.
- No sensitive data in logs or test fixtures.

### Human control

- No broker execution APIs.
- No trade submission.
- No automatic target adoption.
- No automatic application of simulated transactions.
- Explicit confirmation for actual state changes.

---

# 15. Final Definition of Done

This PRD is complete only when:

1. Existing financial correctness defects are resolved and regression-tested.
2. Portfolio imports cannot silently destroy known state.
3. Confirmed manual activities preserve accurate cash, positions and lot integrity.
4. Tax and look-through calculations handle missing information conservatively.
5. The CLI remains the primary and fully capable integration surface.
6. Users can create, activate, version and compare target portfolios.
7. The system can generate account-aware, tax-conscious trade plans from targets.
8. Multiple plans can be compared against a common portfolio baseline.
9. Reports contain sufficient details for manual trade review.
10. The WebUI presents portfolios, targets, plans and reusable prompts without embedding an agent.
11. Every package was developed using failing BDD scenarios before implementation.
12. All tests and linting pass.
13. Documentation accurately describes supported behavior and limitations.
14. The application remains a small, understandable, local Python codebase.

---

# 16. Guiding Principle

**Investobot supplies reliable financial facts, calculations, scenarios, persistent targets, and proposed trade plans.**

**The external AI agent supplies intelligence, research, creativity, and conversation.**

**The human supplies investment decisions and trade execution.**

Do not blur these responsibilities.

The goal is not to build the most sophisticated portfolio-management software possible. It is to build the smallest reliable set of financial tools that makes an already-capable AI agent an effective, tax-aware investment copilot.