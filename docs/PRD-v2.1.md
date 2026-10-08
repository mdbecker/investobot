# Investobot — Final MVP Stabilization PRD

**Version:** 2.1  
**Repository:** https://github.com/mdbecker/investobot  
**Baseline:** Commit `e3bdcbf`  
**Priority:** Financial correctness and data integrity  
**Development methodology:** Strict BDD — Red → Green → Refactor

## 1. Objective

Resolve the remaining issues identified in the Investobot code review while preserving the existing architecture, features, and agent-first workflow.

This PRD addresses:

1. Security classification corrections after incomplete HTML imports.
2. Account metadata being overwritten by routine portfolio snapshots.
3. Undated snapshots replacing newer, dated portfolio state.
4. Potential excessive database growth from storing historical state inside saved plans.
5. Regression tests and documentation for these changes.

**No additional product capabilities are required.**

The existing target portfolio, tax analysis, trade planning, reporting, prompt library, and WebUI functionality must continue working.

## 2. Non-Negotiable Design Decisions

Keep the current:

- Python, Typer, Pydantic, and SQLite architecture.
- `invest` CLI as the primary agent interface.
- Local WebUI as the secondary inspection interface.
- Existing ledger, tax, analytics, targets, plans, and reports modules.
- Explicit preview/confirmation behavior for changes to financial state.
- Immutable historical snapshots and saved trade plans.
- Human-only trade execution.

Do not introduce:

- New databases or ORM layers.
- New frameworks or background services.
- Broker APIs or account integrations.
- Additional market-data providers.
- Agent frameworks or LLM dependencies.
- New WebUI pages unless essential.
- Parallel implementations of existing calculations.

Prefer small changes to existing modules.

New code must follow the established conventions for JSON output, validation, error codes, financial precision, and audit history.

---

# 3. Required BDD Workflow

Every implementation package must follow this exact sequence:

1. Write all required BDD scenarios.
2. Implement their pytest-bdd step definitions.
3. Execute the scenarios and confirm they fail for the expected reason.
4. Investigate unexpected passes before proceeding.
5. Implement the minimum production changes needed.
6. Run the new scenarios until green.
7. Run the complete existing test suite.
8. Run Ruff.
9. Update relevant documentation.
10. Commit the tested changes.

Tests must describe observable financial behavior, not implementation details.

Use synthetic portfolio and HTML fixtures only.

Do not add live network dependencies to automated tests.

---

# 4. Implementation Order

| Order | Work package | Dependencies | Priority |
|---|---|---|---|
| 1 | Security classification correction | None | P0 |
| 2 | Account metadata preservation | Package 1 | P0 |
| 3 | Undated snapshot safeguards | Package 2 | P0 |
| 4 | Plan storage assessment | Packages 1–3 | P2 |
| 5 | Regression verification and documentation | Packages 1–4 | P1 |

Packages 1–3 must be completed before declaring the MVP financially stabilized.

---

# 5. Package 1 — Security Classification Correction

**Priority: P0**

**Dependencies: None**

## Problem

The generic HTML importer may store a security with `asset_type=OTHER` because the source HTML does not identify its type.

Once stored, the current security registration logic rejects changing the asset type.

This prevents a user or agent from correcting a security after researching and verifying its classification.

It can also prevent the security from participating in downstream fund exposure and trade planning calculations.

## Requirements

### 5.1 Explicit classification correction

Add the CLI command:

```bash
invest security classify SECURITY_ID \
  --asset-type ETF \
  --source "Verified issuer documentation" \
  --confirm
```

Supported classifications:

```text
STOCK
ETF
MUTUAL_FUND
TREASURY
BOND
OTHER
```

Rules:

- Only an existing security can be classified using this command.
- Changing `OTHER` to a supported classification is permitted.
- No classification change occurs without `--confirm`.
- Omitting `--confirm` returns a preview of the proposed change.
- A nonempty provenance source is required.
- Repeating the same classification is idempotent.
- Changing one known classification to a different known classification is rejected in MVP.
- Conflicting CUSIP, ISIN, or FIGI identities must never be merged.
- Changes must be atomic.

Do not use `invest security register` to bypass these controls.

### 5.2 Consistent current state

When a classification is confirmed:

- Update the canonical security record.
- Update the asset type of all corresponding current positions.
- Preserve quantities, values, basis, and tax lots.
- Preserve historical snapshots unchanged.
- Ensure portfolio summaries, exposure calculations, and planning use the corrected classification.
- Mark affected saved trade plans stale through the existing state-change detection mechanism.

A later HTML snapshot with an unknown asset type must not silently revert the verified classification to `OTHER`.

A source explicitly asserting a contradictory known classification must produce a conflict requiring review.

### 5.3 Audit information

Store a classification history on the existing security record containing:

```text
previous_type
new_type
source
changed_at
```

Use a small JSON history field. Do not introduce an additional database table.

### BDD scenarios

```gherkin
Feature: Correcting unknown security classifications

Scenario: A verified ETF classification replaces an unknown type
  Given VTI was imported as an OTHER security
  And its identity has been verified
  When the user confirms classifying VTI as an ETF
  Then VTI is classified as an ETF
  And all current VTI positions retain their original quantities and basis

Scenario: Classification preview does not change financial state
  Given VTI is classified as OTHER
  When an ETF classification is previewed
  Then VTI remains classified as OTHER

Scenario: A later incomplete import preserves verified classification
  Given VTI has a verified ETF classification
  When a new snapshot lists VTI without an asset type
  Then VTI remains classified as an ETF

Scenario: Conflicting known classifications are rejected
  Given a security has a verified ETF classification
  When it is submitted as a stock
  Then the change is rejected
  And the security and positions remain unchanged
```

Also test idempotency, missing provenance, identity conflicts, stale-plan detection, and audit history.

### Definition of Done

An agent can safely correct an imported unknown asset type, and the corrected classification is consistently used throughout Investobot.

---

# 6. Package 2 — Account Metadata Preservation

**Priority: P0**

**Dependencies: Package 1**

## Problem

Routine snapshot application currently replaces the stored account record with metadata included in the incoming snapshot.

This can overwrite previously confirmed:

- Account type.
- Tax status.
- Institution.
- Account name.
- Transaction-history completeness.
- Currency and other account settings.

A copied holdings page is evidence of positions and valuations, not necessarily evidence of account configuration.

## Requirements

### 6.1 Separate account configuration from holdings observations

For an existing account, routine snapshot application must preserve its authoritative account metadata.

Incoming snapshots may update:

- Positions.
- Known balances.
- Known tax lots.
- Associated observation timestamps.

They must not independently update:

- `account_type`
- `tax_status`
- `history_complete`
- `currency`
- `institution`
- `name`
- `active`

For a genuinely new account, the initial explicitly accepted account metadata becomes the authoritative configuration.

### 6.2 Explicit account metadata changes

Add:

```bash
invest account update ACCOUNT_ID --file changes.json
```

Default behavior: preview only.

Commit with:

```bash
invest account update ACCOUNT_ID \
  --file changes.json \
  --yes
```

The JSON file contains only fields to change, plus a required nonempty `reason` and `source`.

Rules:

- Account identity (`id`) is immutable.
- Updates are atomic.
- Unsupported fields are rejected.
- Changing `tax_status`, `account_type`, or `history_complete` requires explicit confirmation.
- Currency changes are rejected for accounts with existing positions or cash balances; currency conversion is outside scope.
- Repeating an identical change is a no-op.
- Confirmed changes append an audit entry to the existing account record.
- Changes affecting financial assumptions mark saved plans stale.

No new account metadata database table is necessary.

### 6.3 Reconciliation behavior

When incoming snapshot metadata differs from stored metadata:

- Report the discrepancy.
- Explain that account configuration will not be changed by snapshot application.
- Continue allowing otherwise valid holdings updates.
- Direct the agent to the explicit account-update command.

Do not silently ignore contradictory metadata without reporting it.

Because generic snapshots may contain default values, the discrepancy alone must not prevent normal holdings reconciliation.

### 6.4 WebUI behavior

The existing import and reconciliation interface must show account metadata discrepancies and explain that they do not alter account configuration.

No new account-management page is required.

### BDD scenarios

```gherkin
Feature: Preserving account configuration

Scenario: A routine import does not change a verified retirement account
  Given an account is configured as a Roth IRA
  And its transaction history is marked complete
  When a new holdings snapshot is accepted
  Then the account remains a Roth IRA
  And its transaction-history setting remains unchanged
  And the holdings reflect the new snapshot

Scenario: A metadata conflict is visible
  Given an account is configured as tax deferred
  When an incoming snapshot identifies it as taxable
  Then reconciliation reports an account metadata conflict
  And applying the snapshot does not change its tax status

Scenario: A confirmed tax-status correction updates account configuration
  Given an existing account is incorrectly classified as taxable
  When a tax-status correction is confirmed with a reason
  Then its tax status changes
  And the correction is recorded
  And previously generated plans become stale
```

Also cover unknown accounts, previews, idempotency, currency changes, unsupported fields, atomic rollback, and initial account creation.

### Definition of Done

Routine portfolio imports can no longer unintentionally change established account configuration or tax treatment.

---

# 7. Package 3 — Undated Snapshot Safeguards

**Priority: P0**

**Dependencies: Package 2**

## Problem

The existing snapshot freshness guard rejects older dated snapshots unless explicitly overridden.

However, a snapshot without a source date can replace newer, dated state without passing through the same protection.

Import time is not evidence of when the underlying financial values were accurate.

## Requirements

### 7.1 Conservative freshness policy

Use the following rules:

| Existing account state | Incoming snapshot | Behavior |
|---|---|---|
| No previous snapshot | Undated | Accept with unknown-date warning |
| Existing undated state | Undated | Accept with unknown-date warning |
| Existing dated state | Newer dated | Accept |
| Existing dated state | Same-date | Accept subject to normal reconciliation |
| Existing dated state | Older dated | Require explicit override |
| Existing dated state | Undated with changes | Require explicit override |
| Identical previously applied snapshot | Any | Idempotent no-op |

An incoming undated snapshot with changes must not supersede dated state automatically.

### 7.2 Override mechanism

Reuse the existing `allow_older` and `justification` domain interface rather than adding a second override mechanism.

Extend it to cover both:

- Older dated snapshots.
- Undated snapshots that would supersede existing dated state.

For CLI usage, retain the existing override flag and require a reason.

The resulting audit record must distinguish:

```text
OLDER_SOURCE_OVERRIDE
UNKNOWN_SOURCE_DATE_OVERRIDE
```

Do not treat the override as evidence that an undated source is current.

### 7.3 Reconciliation output

Before application, reconciliation must report:

```text
source_date_status
latest_known_source_date
override_required
```

Allowed status values:

```text
KNOWN_CURRENT
OLDER_THAN_ACCEPTED
UNKNOWN_SOURCE_DATE
NO_PRIOR_DATED_STATE
```

The result must explicitly warn when an undated snapshot may replace more trustworthy dated observations.

### 7.4 WebUI behavior

The current import interface must:

- Display unknown or older source-date warnings.
- Block ordinary acceptance when an override is required.
- Offer a deliberate override with a required explanation.
- Never auto-populate the source date from the import date.

Reuse existing interface elements where possible.

### 7.5 Plan freshness

Applying an authorized snapshot must use the existing saved-plan stale detection.

The new snapshot must never be silently substituted into an existing immutable plan.

### BDD scenarios

```gherkin
Feature: Protecting dated portfolio state

Scenario: An undated snapshot cannot replace newer known holdings
  Given an account has accepted holdings dated October 8
  When an undated snapshot reports a different quantity
  Then reconciliation requires an override
  And ordinary application is rejected
  And the accepted holdings remain unchanged

Scenario: An explicitly reviewed undated snapshot can be accepted
  Given an account has accepted dated holdings
  And an undated snapshot contains updated positions
  When the user accepts it with an override justification
  Then the updated positions become accepted state
  And the audit history records the unknown-date override
  And the positions are not marked as freshly dated

Scenario: An identical import remains idempotent
  Given an account has an accepted snapshot
  When the same snapshot is imported again
  Then no duplicate state transition is recorded
```

Also cover first undated import, same-date updates, older dated updates, missing justification, WebUI parity, and stale-plan detection.

### Definition of Done

No incomplete date information can silently replace better-established portfolio state.

---

# 8. Package 4 — Saved Plan Storage Assessment

**Priority: P2**

**Dependencies: Packages 1–3**

## Problem

Saved plans currently retain the portfolio state used during planning, including historical snapshot information.

This supports reproducibility but may duplicate increasing amounts of data as the number of saved plans grows.

This is a potential maintenance issue, not a confirmed performance defect.

## Requirements

### 8.1 Measure first

Create a deterministic synthetic performance fixture with:

- 10 accounts.
- 1,000 total positions.
- 2,000 tax lots.
- 20 snapshots per account.
- 20 saved alternative plans.

Measure:

- Database size before and after saving plans.
- Average serialized plan size.
- Time to list plans.
- Time to retrieve a saved plan.
- Time to export a Markdown report.

Record the results in `docs/development.md`.

No real account data or external APIs are required.

### 8.2 Preserve reproducibility

The following requirements are mandatory regardless of storage size:

- Historical reports must reproduce the same output after the live portfolio changes.
- Plan assumptions remain immutable.
- Source snapshot identifiers remain available.
- Existing plans remain readable after database migrations.

### 8.3 Avoid premature optimization

Do not introduce compression, separate storage services, or generalized data deduplication.

For this PRD, retain the current plan-storage design and document the observed cost.

Storage optimization is deferred unless the synthetic benchmark reveals an actual operational failure, such as failed exports or impractically slow plan retrieval. If that occurs, report the failure rather than initiating an unscoped schema redesign.

### BDD coverage

- A saved plan remains readable after later snapshots.
- Exporting a saved plan produces identical content after ledger changes.
- Multiple plans preserve their independent assumptions.
- Plans can be listed and retrieved under the synthetic workload.

### Definition of Done

The project's storage characteristics are measured, historical reproducibility is regression-tested, and no unnecessary architecture is added.

---

# 9. Package 5 — Regression Verification and Documentation

**Priority: P1**

**Dependencies: Packages 1–4**

## Requirements

### 9.1 Full regression suite

Run:

```bash
uv run --locked pytest
uv run --locked ruff check --config pyproject.toml src tests
```

Also validate through the existing Docker CI environment.

All previously passing tests must remain green.

### 9.2 Cross-feature regression coverage

Verify that the changes do not break:

- HTML import and reconciliation.
- Manual trade recording.
- Position and lot valuation.
- Tax analysis.
- Wash-sale warnings.
- Fund look-through exposure.
- Security identity resolution.
- Target creation and activation.
- Trade-plan generation.
- Plan comparison.
- Report export.
- WebUI inspection and prompt library.

Use synthetic fixtures and offline tests.

### 9.3 Documentation

Update the relevant existing files:

```text
README.md
AGENTS.md
docs/agent-usage.md
docs/data-model.md
docs/workflows.md
docs/tax-limitations.md
docs/inspection.md
docs/development.md
```

Document:

- How an agent corrects an unknown security classification.
- How account metadata is updated safely.
- Which fields HTML snapshots are permitted to change.
- How unknown-date snapshot overrides work.
- Which operations require explicit confirmation.
- How classification and account changes affect saved plans.
- The results of the synthetic plan-storage assessment.

Update CLI examples and machine-readable tool descriptions to reflect the new commands.

Do not duplicate extensive documentation across files.

### 9.4 Compatibility

Preserve the current SQLite database versioning and migrate existing data as needed.

Existing account, security, snapshot, target, and plan records must remain readable.

New audit fields must have safe defaults for older records.

Do not discard existing portfolio state or require users to rebuild their databases.

### Definition of Done

All tests pass, CI is green, documentation matches behavior, and existing ledger data remains usable.

---

# 10. Final Acceptance Criteria

This PRD is complete when all of the following are demonstrated using synthetic fixtures.

**Security classification**

An imported ETF initially classified as `OTHER` can be explicitly corrected to `ETF`. Subsequent imports preserve that classification, and existing holdings and plans remain consistent.

**Account metadata**

A Roth IRA retains its verified account type and tax treatment after subsequent holdings imports. Changes to account configuration require a separate, confirmed action.

**Snapshot freshness**

An undated holdings page cannot silently overwrite newer dated holdings. Any override is explicitly justified and audited.

**Tax and planning integrity**

Correcting a security classification or changing an account's tax treatment causes affected plans to become stale. New plans use updated authoritative information without changing actual holdings.

**Plan reproducibility**

Existing plans and reports remain reproducible after unrelated portfolio changes. Storage behavior is measured without introducing unnecessary infrastructure.

**Regression safety**

All existing and new BDD scenarios pass, Ruff passes, and GitHub Actions reports a successful run.

---

# 11. Explicitly Out of Scope

Do not implement as part of this PRD:

- Testing against real brokerage HTML.
- Testing against live FMP responses.
- Adding institution-specific import profiles.
- New investment research tools.
- News APIs.
- New portfolio optimization algorithms.
- Additional bond features.
- Additional tax-law modeling.
- New WebUI sections.
- MCP or LLM integration.
- Broker authentication or order execution.
- Generalized plan-storage redesign.
- Any architectural rewrite unrelated to the identified issues.

These exclusions are intentional. The purpose of this PRD is stabilization.

---

# 12. Definition of Done

All five packages are complete when:

1. The identified data-integrity problems are fixed.
2. New BDD tests were written and observed failing before production changes.
3. All new and existing tests pass.
4. CLI and WebUI behavior remain consistent.
5. Financial calculations use corrected canonical state.
6. Actual holdings and historical records remain protected.
7. Existing targets, plans, reports, and prompts continue working.
8. Migrations preserve existing data.
9. Documentation reflects implemented behavior.
10. No unnecessary architectural complexity has been introduced.

**Once these conditions are satisfied, Investobot can be considered code-complete for the current MVP scope, with real-world data validation tracked separately.**

## Guiding Principle

Fix the remaining financial correctness issues with the smallest possible changes.

Do not use a stabilization effort as an opportunity to redesign working systems or expand the product.

Investobot should remain a small, deterministic, agent-first toolkit that maintains trustworthy investment data and supports human-reviewed investment decisions.