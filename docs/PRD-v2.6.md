# Investobot — Agent Research Skills & Earnings Intelligence

**Product Requirements Document — Version 2.6**

**Repository:** https://github.com/mdbecker/investobot  
**Baseline:** V2.5 complete, commit `0f8578a`  
**Priority:** P1 — Research capability expansion  
**Methodology:** Strict BDD — Red → Green → Refactor  
**Architecture:** Agent Skills + Pydantic + SQLite + Typer  
**Database policy:** Fresh schema permitted; no legacy database migration required

---

# 1. Executive Summary

Investobot should evolve from a collection of deterministic investment tools into a structured research companion for external coding agents.

The research agent should be able to:

1. Discover an available research skill.
2. Execute the skill using its existing browser and research capabilities.
3. Produce structured, source-backed JSON.
4. Validate that JSON using Investobot.
5. Explicitly save the research to SQLite.
6. Retrieve historical research without repeating the original investigation.
7. Compare research across reporting periods.
8. Use researched facts and calculations to support human investment decisions.

This version implements that architecture for two research domains:

- **Executive political-contribution research:** Convert the existing V2.5 prompt into an installable agent skill and resolve three outstanding hardening issues.
- **Earnings and financial-statement research:** Introduce a new skill with structured financial metrics, management guidance, source references, immutable research history, and deterministic comparisons.

The implementation must remain small, local, auditable, and independent of any particular AI provider.

## Core principle

**Agent skills perform the research. Investobot validates, remembers, and calculates. Humans decide.**

No LLM runs inside Investobot.

---

# 2. Product Goals

## Goal A — Research skills instead of research prompts

Replace the bundled political-contribution research prompt with a standards-compatible agent skill.

Implement earnings research using the same skill architecture.

Skills should be available to Codex and Claude Code, without maintaining entirely separate instructions for each agent.

## Goal B — Structured research rather than unsearchable prose

Research outputs should contain machine-readable:

- Company identities.
- Reporting periods.
- Numeric facts.
- Evidence.
- Source references.
- Management guidance.
- Qualitative findings.
- Data limitations.
- Unresolved issues.

The database should support efficient queries and meaningful comparisons.

## Goal C — Preserve provenance and financial accuracy

Every financial observation must retain enough information to identify its original disclosure.

An agent's analysis must be clearly distinguished from an actual disclosed financial fact.

Unknown information remains unknown.

## Goal D — Reuse the architecture

Future skills such as company news, competitive research, valuation and management research should be able to reuse the same basic research-run and source infrastructure.

Do not build those future skills in this PRD.

---

# 3. Architectural Decisions

Keep:

- Python 3.12+
- Standard-library SQLite
- Pydantic validation
- Typer CLI
- Decimal-based financial arithmetic
- Existing `invest research` command group
- Existing portfolio, target and plan engines
- Existing local WebUI
- Offline pytest-bdd tests
- Ruff and Docker CI

Add:

- Two standardized Agent Skills.
- Minimal skill discovery and installation support.
- A new earnings JSON contract.
- A small shared research storage foundation.
- Earnings-specific relational tables.
- Deterministic earnings queries and comparisons.

Do not add:

- An embedded LLM.
- An agent execution engine.
- MCP.
- Autonomous browsing inside Investobot.
- A new ORM.
- Redis or PostgreSQL.
- Cloud services.
- Background workers.
- A full document search engine.
- Vector embeddings.
- Automated trading.
- A generalized plugin framework.

---

# 4. Agent Skill Architecture

## 4.1 Use the open Agent Skills standard

Each research skill must be a directory containing `SKILL.md`, using the standard YAML frontmatter format.

The file must declare:

- `name`
- `description`

Skills may also contain:

- `references/` for research procedures and financial definitions.
- `assets/` for JSON examples or templates.

Executable scripts are unnecessary for the initial release.

The canonical source layout should be:

```text
skills/
  investobot-political-contributions/
    SKILL.md
    references/
      research-method.md
      json-contract.md

  investobot-earnings/
    SKILL.md
    references/
      research-method.md
      accounting-rules.md
      json-contract.md
```

The complete input JSON schemas must remain authoritative in the Pydantic models.

If a JSON Schema file is bundled with a skill, it must be generated or verified against the actual model. Never manually maintain a second contradictory schema.

## 4.2 Skill discovery

Add:

```bash
invest research skills list
invest research skills show investobot-earnings
invest research skills show investobot-political-contributions
```

`list` returns concise JSON containing:

```json
{
  "skills": [
    {
      "name": "investobot-earnings",
      "description": "Research company earnings and SEC financial disclosures",
      "research_command": "research.earnings",
      "schema_version": "1.0"
    },
    {
      "name": "investobot-political-contributions",
      "description": "Research verified executive political contributions",
      "research_command": "research.political",
      "schema_version": "1.0"
    }
  ]
}
```

These descriptions are examples; final descriptions should identify when an agent should select each skill.

The CLI lists skills; it does not execute them.

## 4.3 Skill installation

Provide a minimal installation mechanism:

```bash
invest research skills install --agent codex --workspace .
invest research skills install --agent claude-code --workspace .
```

Copy skills into the relevant project-local skill directories:

```text
.agents/skills/
.claude/skills/
```

Requirements:

- Use the same canonical skill content.
- Install only when explicitly requested.
- Never alter agent settings globally.
- Do not execute downloaded code.
- No dependency installation.
- Do not overwrite locally modified skills without explicit confirmation.
- Report copied files and installed skill versions.
- Reject destination path traversal and unsafe symlink targets.
- No network connection is needed.

The feature should also work when users copy skill directories manually.

### Important distinction

Installing a skill does not execute research.

After installation, the external agent recognizes the research workflow and uses its browser and authorized tools.

Investobot continues to handle only deterministic CLI operations.

## 4.4 Versioning

Each research JSON contract has a `schema_version`.

A saved research run also records the skill name and version.

Research output must be validated against the matching supported contract.

Changing a skill's wording must not silently reinterpret previously accepted financial data.

Use a stable skill version identifier tied to the bundled skill package, not an agent-generated string.

## 4.5 Existing prompt library

Keep the existing general-purpose Markdown Prompt Library.

Do not convert every old prompt into an agent skill under this PRD.

Convert the bundled executive political-contribution prompt specifically.

Remove that bundled prompt from `prompt_defaults` once its skill is available.

Do not delete user-created prompts or custom overrides.

Update documentation so users invoke the political research skill through Codex or Claude Code, not by copying a legacy prompt.

---

# 5. Package 1 — V2.5 Political Research Hardening

**Priority:** P0  
**Dependencies:** None

Resolve the three known issues before adding earnings research.

## 5.1 Preserve verifiable source locations

Problem:

The current political source URL normalization removes every query parameter.

Although this protects against accidentally storing credentials, some public source links use query parameters to identify individual filings or records.

Required behavior:

- Preserve safe, meaningful public record identifiers.
- Continue removing credentials, authentication parameters, tokens and fragments containing sensitive information.
- Reject unsafe or ambiguous URLs.
- Allow a separate structured source-record locator where query parameters cannot safely be retained.
- Keep the original evidence record independently identifiable.

Prefer a narrow allowlist of public locator fields over a broad URL-sanitization framework.

Never store access tokens or API keys.

### Acceptance

An evidence URL identifying a specific disclosure remains resolvable after normalization, without retaining credentials.

## 5.2 Validate company/security identity

Problem:

Political research can reference an existing canonical `security_id` without sufficiently verifying that the security corresponds to the researched company.

Required behavior:

- Verify that the referenced security exists.
- If a ticker is supplied, require it to match the canonical ticker or an explicitly verified accepted alias.
- Reject contradictory identities.
- Do not use company-name similarity alone.
- Allow null security IDs for private or unregistered companies.
- Never automatically create securities or change accepted security classifications.

### Acceptance

Research for one company cannot be attached to an unrelated Investobot security through a mistaken security ID.

## 5.3 Include candidates in recipient summaries

Extend political research summary output to include, where verified:

```json
{
  "recipient_id": "recipient-1",
  "recipient_name": "Example Campaign Committee",
  "recipient_type": "CANDIDATE_COMMITTEE",
  "committee_id": "EXAMPLE_COMMITTEE_ID",
  "candidate_id": "EXAMPLE_CANDIDATE_ID",
  "candidate_name": "Example Candidate",
  "recipient_party": "DEMOCRATIC",
  "transactions": []
}
```

Preserve the existing distinction between candidate committees, PACs, joint fundraising committees and party committees.

Never infer a donor's personal party affiliation from the recipients of their contributions.

## 5.4 Regression tests

```gherkin
Feature: Political research hardening

Scenario: A public disclosure remains individually verifiable
  Given a public disclosure URL with a permitted record locator
  And an unrelated credential-bearing query parameter
  When the source is normalized
  Then the public record locator is preserved
  And the credential is removed

Scenario: Research cannot be linked to an unrelated security
  Given a registered security with an accepted ticker
  When political research supplies its ID with a contradictory ticker
  Then the research import is rejected
  And no research record is saved

Scenario: Candidate recipients retain verified identities
  Given an accepted contribution to a verified candidate committee
  When the political research summary is requested
  Then candidate name and candidate ID are included
  And no personal political affiliation is assigned to the executive
```

Keep all existing source-permission restrictions in force.

### Definition of Done

The three V2.5 review issues are closed with focused BDD tests and no political research schema redesign unless strictly necessary.

---

# 6. Package 2 — Convert Political Research to an Agent Skill

**Priority:** P1  
**Dependencies:** Package 1

## 6.1 Create the skill

Create:

```text
skills/investobot-political-contributions/SKILL.md
```

Move the existing step-by-step methodology into the skill.

Retain all important instructions concerning:

- Company and executive identity.
- Historical executive roles.
- Source-use permissions.
- FEC restrictions.
- Disclosed contributions.
- Candidate and committee identities.
- Deduplication.
- Refunds.
- Unresolved matches.
- Evidence references.
- JSON output.
- Human review.

The skill must teach the agent how to generate a JSON file conforming to `PoliticalResearchInput`.

Do not copy the old prompt verbatim if references and schema material are better maintained in separate skill files.

## 6.2 Preserve political research commands

Keep:

```bash
invest research political validate FILE
invest research political import FILE
invest research political import FILE --yes
invest research political list
invest research political show RUN_ID
invest research political summary RUN_ID
```

These commands are still necessary.

The agent skill conducts the research; the commands validate, store and query it.

Do not combine them into one agent-powered CLI command.

## 6.3 Skill integration

The external agent should follow this procedure:

1. Read the installed political research skill.
2. Gather authorized evidence.
3. Produce structured JSON.
4. Save it under ignored `local-data`.
5. Call `invest research political validate`.
6. Review validation findings.
7. Preview import.
8. Obtain explicit human authorization.
9. Confirm import.
10. Retrieve the persisted summary.

The agent must not automatically approve restricted FEC contributor data.

The existing independently reviewed source-policy mechanism remains mandatory.

## 6.4 BDD acceptance

```gherkin
Feature: Political research agent skill

Scenario: Political research uses a bundled skill
  Given Investobot research skills are installed for Codex
  When the available skills are inspected
  Then investobot-political-contributions has valid SKILL.md metadata
  And its instructions reference the authoritative political JSON contract
  And its documented CLI commands exist

Scenario: Skill migration preserves political research behavior
  Given a valid synthetic political research package
  When the political research skill workflow is followed
  Then validation, preview, confirmation and summary work as before
  And accepted holdings and saved plans are unchanged
```

### Definition of Done

Political-contribution research is distributed as a reusable agent skill rather than a bundled copy-and-paste prompt.

---

# 7. Package 3 — Earnings & Financial Statement Research Skill

**Priority:** P0 for the new earnings feature  
**Dependencies:** Package 2

## 7.1 Objective

Enable an external agent to research a public company's financial disclosures, normalize the results into strict JSON, and save an immutable record that Investobot can query and compare over time.

The skill should prioritize primary sources.

For U.S. public companies, the default research sources are:

- SEC Form 10-K.
- SEC Form 10-Q.
- Relevant Form 8-K earnings exhibits.
- SEC XBRL company facts.
- Company earnings releases.
- Official investor presentations.
- Earnings-call transcripts where available and permitted.

Do not treat third-party financial summaries as authoritative when primary filings are available.

## 7.2 Skill file

Create:

```text
skills/investobot-earnings/SKILL.md
```

Suggested frontmatter:

```yaml
---
name: investobot-earnings
description: Research a public company's quarterly or annual earnings, financial statements, guidance, segment results, and material accounting changes. Produce source-backed JSON for deterministic validation and storage in Investobot.
---
```

The skill should refer to:

```text
references/research-method.md
references/accounting-rules.md
references/json-contract.md
```

## 7.3 Required step-by-step research procedure

The skill must instruct the agent to perform the following.

### Step 1 — Identify the company

Confirm:

- Legal company name.
- Ticker.
- SEC CIK where applicable.
- Relevant reporting entity.
- The specific fiscal reporting period.

Do not assume the ticker uniquely identifies the reporting entity across time.

### Step 2 — Locate primary disclosures

Retrieve the relevant filing, earnings release and supporting materials.

Record:

- SEC accession number when applicable.
- Filing type.
- Filing date.
- Filing acceptance date if available.
- Fiscal period.
- Period start/end.
- URL.
- Date accessed.

Use a direct filing reference whenever possible.

### Step 3 — Extract reported financial metrics

Capture available, relevant figures:

- Revenue.
- Gross profit.
- Operating income.
- Net income.
- Diluted EPS.
- Operating cash flow.
- Capital expenditures.
- Free cash flow when reported or supported by an explicit definition.
- Diluted weighted-average shares.
- Other material company-specific metrics.

Financial amounts must be exact decimal strings.

Do not use binary floating-point values.

Keep source units and normalized units explicit.

### Step 4 — Research segment results

Record significant business segments and their reported metrics.

Examples:

- Cloud revenue.
- Advertising revenue.
- Geographic segment revenue.
- Product-line revenue.
- Segment operating income.

Use reported segment names and disclose structural changes.

Do not assume segment definitions are consistent across different companies or periods.

### Step 5 — Distinguish GAAP and non-GAAP

Never silently treat adjusted measures as GAAP results.

For each measure, record:

- Accounting basis.
- Exact metric definition.
- Source filing or presentation.
- Whether reconciliation was disclosed, if applicable.

A reported non-GAAP measure may be stored but must be labeled as such.

Do not invent reconciliation adjustments.

### Step 6 — Capture management guidance

When guidance is disclosed, record:

- Metric.
- Forecast period.
- Lower bound.
- Upper bound.
- Units.
- Accounting basis.
- Date issued.
- Source.
- Qualifiers and assumptions.

Qualitative guidance should be stored as a clearly labeled finding rather than fabricated numeric bounds.

### Step 7 — Identify changes and risks

Document:

- Guidance changes.
- Important business developments.
- Material accounting changes.
- Restatements.
- Significant one-time items.
- Customer concentration.
- Debt or liquidity developments.
- Changes in segment reporting.
- Management explanations for material changes.

Separate facts from interpretations.

### Step 8 — Compare periods carefully

Only compare metrics with compatible:

- Reporting entities.
- Accounting bases.
- Period lengths.
- Definitions.
- Units.
- Consolidation scopes.

Quarter-to-date, year-to-date and full-year metrics are not interchangeable.

Do not label a year-to-date cash-flow figure as an individual quarter.

Do not invent fourth-quarter results by subtracting nine months from annual figures. Such a calculation, if added later, must be explicit and reproducible.

### Step 9 — Review data quality

Identify:

- Missing metrics.
- Ambiguous disclosures.
- Restated figures.
- Amended filings.
- Unavailable source documents.
- Unreconciled non-GAAP measures.
- Possible inconsistencies between documents.
- Unsupported comparisons.

If the evidence is insufficient, mark coverage as partial.

### Step 10 — Produce JSON

The agent must output a single JSON object conforming to `EarningsResearchInput`.

No Markdown wrapper or commentary should appear around the JSON intended for import.

The agent saves it to an ignored local file.

### Step 11 — Validate and persist

Use the earnings CLI commands.

No research is saved without explicit confirmation.

---

# 8. Earnings Structured JSON Contract

Introduce:

```python
EarningsResearchInput
```

The model must be authoritative and use `extra="forbid"`.

The top-level structure is:

```text
schema_version
research_type
company
reporting_period
researched_as_of
coverage_status
sources[]
metrics[]
guidance[]
findings[]
limitations[]
```

## 8.1 Example JSON

All company and financial values below are fictional.

```json
{
  "schema_version": "1.0",
  "research_type": "EARNINGS_FINANCIAL_STATEMENTS",
  "company": {
    "name": "Fictional Technology Corporation",
    "ticker": "FAKE",
    "cik": "0000000001",
    "security_id": null
  },
  "reporting_period": {
    "fiscal_year": 2026,
    "fiscal_period": "Q2",
    "period_end": "2026-06-30"
  },
  "researched_as_of": "2026-10-10",
  "coverage_status": "PARTIAL",
  "sources": [
    {
      "id": "source-10q",
      "source_type": "SEC_10_Q",
      "url": "https://example.invalid/fictional-filing",
      "accession_number": "SYNTHETIC-ACCESSION",
      "filed_at": "2026-08-01",
      "accessed_at": "2026-10-10",
      "publisher": "Fictional Technology Corporation"
    }
  ],
  "metrics": [
    {
      "id": "revenue-q2",
      "metric_code": "REVENUE",
      "metric_label": "Consolidated revenue",
      "value": "1250000000.00",
      "unit": "USD",
      "accounting_basis": "GAAP",
      "measurement_type": "REPORTED",
      "period_type": "DURATION",
      "period_start": "2026-04-01",
      "period_end": "2026-06-30",
      "fiscal_year": 2026,
      "fiscal_period": "Q2",
      "scope": "CONSOLIDATED",
      "segment_name": null,
      "source_id": "source-10q",
      "source_locator": "Financial statements; consolidated revenue",
      "xbrl_taxonomy": null,
      "xbrl_concept": null
    }
  ],
  "guidance": [],
  "findings": [
    {
      "id": "finding-1",
      "category": "MANAGEMENT_EXPLANATION",
      "statement": "Fictional example: management attributed growth to higher demand.",
      "source_id": "source-10q",
      "source_locator": "Management discussion",
      "limitations": []
    }
  ],
  "limitations": [
    "Synthetic example; no real financial disclosure was reviewed.",
    "Only one reporting metric is represented."
  ]
}
```

## 8.2 Required financial rules

### Numbers

- Monetary and share values must use decimal strings.
- Reject NaN and infinity.
- Preserve all significant decimal digits.
- Units must be explicit.
- No automatic currency conversion.
- Report unavailable values as absent/null, never zero.

### Reporting periods

Distinguish:

- `INSTANT`: Balance-sheet values measured at a date.
- `DURATION`: Income and cash-flow values measured over a period.

For duration facts, both start and end dates are mandatory.

For instant facts, an end date is mandatory and start date must be null.

`fiscal_period` alone is never sufficient to establish the actual reporting duration.

### Accounting basis

Allowed values:

```text
GAAP
NON_GAAP
IFRS
OTHER
```

Do not compare metrics across bases without an explicit explanation.

### Measurement type

For the initial release, earnings metrics should contain **reported values**, not agent-calculated estimates.

Allowed:

```text
REPORTED
```

Derived growth rates, margins and comparisons belong in Investobot's deterministic calculations.

This avoids saving two conflicting versions of the same financial calculation.

### Source identification

Every metric requires:

- A valid source ID.
- A source locator identifying the relevant section or fact.
- Period information.
- Metric definition.
- Units and accounting basis.

For SEC XBRL facts, retain taxonomy and concept where available, together with the filing accession number and relevant fact period.

### Standardized metric codes

Support:

```text
REVENUE
GROSS_PROFIT
OPERATING_INCOME
NET_INCOME
DILUTED_EPS
OPERATING_CASH_FLOW
CAPITAL_EXPENDITURES
FREE_CASH_FLOW
DILUTED_WEIGHTED_AVERAGE_SHARES
SEGMENT_REVENUE
SEGMENT_OPERATING_INCOME
OTHER
```

`OTHER` requires an explicit metric label.

Do not manufacture metrics when a company does not report them.

## 8.3 Guidance contract

Numeric guidance uses structured entries:

```json
{
  "id": "guidance-1",
  "metric_code": "REVENUE",
  "period_start": "2026-07-01",
  "period_end": "2026-09-30",
  "lower_value": "1300000000",
  "upper_value": "1400000000",
  "unit": "USD",
  "accounting_basis": "NON_GAAP",
  "guidance_status": "ISSUED",
  "source_id": "source-earnings-release",
  "source_locator": "Outlook section",
  "qualifiers": "Synthetic example; excludes specified adjustments."
}
```

Allowed guidance statuses:

```text
ISSUED
REVISED
REAFFIRMED
WITHDRAWN
```

At least one bound must be present for numeric guidance, except when documenting withdrawn guidance with an explicit prior-guidance reference.

If both bounds exist, lower must not exceed upper.

Do not silently replace earlier guidance.

## 8.4 Findings contract

Qualitative findings must be classified as:

```text
VERIFIED_FACT
MANAGEMENT_EXPLANATION
ANALYST_INTERPRETATION
RISK
UNRESOLVED
```

Every factual finding requires source provenance.

Interpretations must not be represented as independently verified company disclosures.

Unresolved findings may record missing evidence explicitly.

---

# 9. Package 4 — Structured SQLite Research Storage

**Priority:** P0  
**Dependencies:** Package 3

## 9.1 Database version

Initialize SQLite schema version **5**.

As previously agreed, existing development databases are disposable.

No schema 4 migration is required.

Do not automatically delete an existing database. Incompatible database versions must receive deliberate-reset instructions.

Existing portfolio, tax, planning and political research functionality must work correctly on a fresh schema 5 database.

## 9.2 Shared research tables

Add two reusable tables.

### `research_runs`

```sql
CREATE TABLE research_runs (
    id TEXT PRIMARY KEY,
    research_type TEXT NOT NULL,
    skill_name TEXT NOT NULL,
    skill_version TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    company_name TEXT NOT NULL,
    ticker TEXT,
    security_id TEXT,
    cik TEXT,
    fiscal_year INTEGER,
    fiscal_period TEXT,
    period_end TEXT,
    researched_as_of TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    coverage_status TEXT NOT NULL,
    summary_json TEXT NOT NULL,
    package_json TEXT NOT NULL,
    FOREIGN KEY (security_id)
        REFERENCES securities(id)
);

CREATE INDEX research_runs_lookup_idx
ON research_runs (
    research_type,
    ticker,
    researched_as_of DESC
);
```

The `id` is the SHA-256 hash of the canonical validated research package and its contract identity.

Identical packages must produce the same ID.

Different accepted research results produce different immutable runs.

`summary_json` contains compact indexed information used for listing.

`package_json` contains the complete normalized research evidence necessary for historical reproduction.

Do not store entire filings or copied webpages.

### `research_sources`

```sql
CREATE TABLE research_sources (
    run_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    publisher TEXT NOT NULL,
    url TEXT NOT NULL,
    accession_number TEXT,
    filed_at TEXT,
    accessed_at TEXT NOT NULL,
    PRIMARY KEY (run_id, source_id),
    FOREIGN KEY (run_id)
        REFERENCES research_runs(id)
);
```

Source identities are scoped to the research run.

Preserve safe, specific evidence locators without storing credentials.

Do not introduce a general-purpose document crawler.

## 9.3 Earnings-specific tables

Create three earnings-specific tables.

### `research_earnings_metrics`

```sql
CREATE TABLE research_earnings_metrics (
    run_id TEXT NOT NULL,
    metric_id TEXT NOT NULL,
    metric_code TEXT NOT NULL,
    metric_label TEXT NOT NULL,
    value_text TEXT NOT NULL,
    unit TEXT NOT NULL,
    accounting_basis TEXT NOT NULL,
    period_type TEXT NOT NULL,
    period_start TEXT,
    period_end TEXT NOT NULL,
    fiscal_year INTEGER NOT NULL,
    fiscal_period TEXT NOT NULL,
    measurement_type TEXT NOT NULL,
    scope TEXT NOT NULL,
    segment_name TEXT,
    source_id TEXT NOT NULL,
    source_locator TEXT NOT NULL,
    xbrl_taxonomy TEXT,
    xbrl_concept TEXT,
    PRIMARY KEY (run_id, metric_id),
    FOREIGN KEY (run_id)
        REFERENCES research_runs(id),
    FOREIGN KEY (run_id, source_id)
        REFERENCES research_sources(run_id, source_id)
);

CREATE INDEX earnings_metric_lookup_idx
ON research_earnings_metrics (
    metric_code,
    fiscal_year,
    fiscal_period
);
```

The authoritative Pydantic contract must validate metric enumerations, Decimal strings, period consistency, units, GAAP/non-GAAP classification, and source references.

SQLite must additionally enforce foreign keys and record identity.

For example, a separate segment-revenue observation must remain distinguishable from consolidated revenue.

Do not aggregate unrelated segments automatically.

### `research_earnings_guidance`

```sql
CREATE TABLE research_earnings_guidance (
    run_id TEXT NOT NULL,
    guidance_id TEXT NOT NULL,
    metric_code TEXT NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    lower_value TEXT,
    upper_value TEXT,
    unit TEXT NOT NULL,
    accounting_basis TEXT NOT NULL,
    guidance_status TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_locator TEXT NOT NULL,
    qualifiers TEXT NOT NULL,
    PRIMARY KEY (run_id, guidance_id),
    FOREIGN KEY (run_id)
        REFERENCES research_runs(id),
    FOREIGN KEY (run_id, source_id)
        REFERENCES research_sources(run_id, source_id)
);
```

Guidance is evidence of management's stated outlook, not a verified future outcome.

### `research_earnings_findings`

```sql
CREATE TABLE research_earnings_findings (
    run_id TEXT NOT NULL,
    finding_id TEXT NOT NULL,
    category TEXT NOT NULL,
    statement TEXT NOT NULL,
    source_id TEXT,
    source_locator TEXT,
    limitations_json TEXT NOT NULL,
    PRIMARY KEY (run_id, finding_id),
    FOREIGN KEY (run_id)
        REFERENCES research_runs(id),
    FOREIGN KEY (run_id, source_id)
        REFERENCES research_sources(run_id, source_id)
);
```

Facts and interpretations remain explicitly labeled.

## 9.4 Shared versus specialized storage

The shared tables cover:

- Run identity.
- Research metadata.
- Source provenance.
- Immutable package persistence.
- Compact summaries.

The specialized tables cover:

- Financial metrics.
- Earnings guidance.
- Earnings findings.

Do not move the existing political research into these generic tables in V2.6.

Its specific relational design already works and handles different concepts.

The shared foundation applies to new earnings research and future skills where appropriate.

Do not build a generalized entity-attribute-value database.

## 9.5 Atomicity and immutability

Import must be transactional:

1. Validate the entire JSON package.
2. Verify company identity and source references.
3. Canonicalize and calculate the content hash.
4. Return an idempotent result if already saved.
5. Begin a transaction.
6. Insert the run.
7. Insert source records.
8. Insert metrics, guidance and findings.
9. Commit all changes together.

Any failure must leave no partial research run.

Accepted runs are immutable.

Correcting research creates a new run rather than rewriting historical facts.

---

# 10. Package 5 — Earnings CLI Commands

**Priority:** P0  
**Dependencies:** Package 4

Add:

```bash
invest research earnings validate FILE
invest research earnings import FILE
invest research earnings import FILE --yes
invest research earnings list
invest research earnings list --ticker TICKER
invest research earnings show RUN_ID
invest research earnings summary RUN_ID
invest research earnings compare RUN_A RUN_B
```

## 10.1 Validate

Read-only operation.

Checks:

- JSON structure.
- Company identity.
- Dates.
- Reporting periods.
- Source references.
- Numeric precision.
- Duplicates.
- Internal contradictions.
- Metric definitions.
- Units.
- Guidance bounds.
- Disclosure limitations.

Return structured errors and warnings.

Validation confirms structural consistency, not the factual truth of external documents.

## 10.2 Import

Preview by default.

```bash
invest research earnings import earnings.json
```

Return:

```json
{
  "status": "PREVIEW",
  "committed": false,
  "research_run_id": "CONTENT_HASH",
  "company": "Fictional Technology Corporation",
  "reporting_period": "2026-Q2",
  "metric_count": 12,
  "guidance_count": 2,
  "finding_count": 5,
  "warning_count": 3,
  "mutation_scope": "research"
}
```

Explicit acceptance:

```bash
invest research earnings import earnings.json --yes
```

The confirmed operation writes research records only.

It cannot modify holdings, activity, tax lots, market data, targets or saved plans.

## 10.3 List

Return compact research-run metadata.

Never load complete research packages merely to list available runs.

Support ticker filtering and newest-first ordering.

## 10.4 Show

Return the full normalized immutable research package, including provenance and original reporting periods.

This can be larger than list/summary results.

## 10.5 Summary

Calculate a deterministic earnings summary.

Example:

```json
{
  "research_run_id": "RUN_ID",
  "company": "Fictional Technology Corporation",
  "ticker": "FAKE",
  "fiscal_year": 2026,
  "fiscal_period": "Q2",
  "period_end": "2026-06-30",
  "metrics": {
    "revenue": {
      "value": "1250000000.00",
      "unit": "USD",
      "basis": "GAAP",
      "source_id": "source-10q"
    }
  },
  "guidance_count": 0,
  "findings_count": 1,
  "coverage_status": "PARTIAL",
  "warnings": [
    "Insufficient verified comparable periods for year-over-year growth."
  ]
}
```

This is illustrative, not real research.

Summaries should be calculated from saved facts, not agent-generated totals.

When comparable financial metrics are unavailable, return null and a warning.

## 10.6 Compare

Support:

```bash
invest research earnings compare RUN_A RUN_B
```

Compare saved metric observations only when their:

- Reporting entities match.
- Metric definitions match.
- Accounting bases match.
- Units match.
- Consolidation and segment scopes match.
- Reporting durations are comparable.
- Source periods support the requested comparison.

Calculate absolute changes and percentage changes using Decimal.

Never compare a quarterly revenue figure with a year-to-date value as though they represent the same duration.

Never compare GAAP with adjusted earnings without explicit labeling and separation.

Return an incompatibility warning rather than inventing a comparison.

If an amended filing supersedes an earlier reported value, preserve both historical observations and clearly disclose the relationship.

No ranking or investment score.

## 10.7 Tool discovery

Update:

```bash
invest tools list
invest tools describe research.earnings.validate
invest tools describe research.earnings.import
invest tools describe research.earnings.summary
invest schema
```

Reuse the authoritative Pydantic models for input schemas.

`research.earnings.import` must explicitly declare mutation scope `research`.

Read-only commands must declare no financial mutation.

---

# 11. Data Integrity and Source Provenance

These rules apply across the new earnings implementation.

## 11.1 SEC filing identifiers

For SEC filings, retain the CIK and accession number when available.

A filing source must identify the actual reporting entity.

Do not silently substitute a similarly named issuer.

## 11.2 XBRL limitations

SEC Company Facts provides useful standardized XBRL observations, but it does not include every company-specific disclosure or segment dimension.

An agent must consult the original filing for omitted or company-specific information.

For XBRL observations preserve the applicable:

- Taxonomy.
- Concept.
- Unit.
- Reporting duration or instant date.
- Filing accession.
- Source filing.
- Fiscal context.

Do not choose a financial value merely because it is the most recent response.

## 11.3 Reporting period correctness

Prevent these common errors:

- Comparing different fiscal quarters.
- Treating nine-month cash flow as third-quarter cash flow.
- Mixing trailing-twelve-month metrics with annual reporting.
- Treating balance-sheet values as duration values.
- Comparing differing currencies without conversion.
- Combining consolidated and segment values incorrectly.
- Using current restated data while claiming it was available before the restatement.

## 11.4 Filing amendments and restatements

Preserve:

- Original filing reference.
- Amended filing reference.
- Source reporting date.
- Research retrieval date.
- Which financial values differ, when known.

A new research run may reference an amendment or restatement.

Do not overwrite historical results.

## 11.5 Non-GAAP metrics

Keep non-GAAP results distinct.

If a company does not disclose the reconciliation needed to understand an adjusted measure, explicitly report the limitation.

Do not automatically accept management's adjustments as economically equivalent to GAAP.

## 11.6 Research freshness

Financial statements represent specified reporting periods.

A recent retrieval does not make an old financial result current.

Retain both the period covered and research timestamp.

## 11.7 External research trust boundary

A skill's research output is untrusted until validated.

Pydantic and SQLite can check structural validity, but cannot prove that a cited source actually supports the value.

The agent must be instructed to verify the original disclosures.

Unknown and conflicting information must remain visible.

Do not allow imported earnings research to silently overwrite accepted household data or FMP market observations.

---

# 12. Complete Agent Workflow

A typical workflow should be:

### Step 1 — Install the skills

```bash
invest research skills install --agent codex --workspace .
```

### Step 2 — Ask the agent to research earnings

Example agent instruction:

> Use the investobot-earnings skill to research the latest quarterly earnings for Microsoft. Verify SEC filings and company disclosures. Produce the required structured JSON, distinguish GAAP from non-GAAP, and record missing or conflicting data.

### Step 3 — Agent uses the skill

The external agent:

- Identifies the company.
- Reviews filings.
- Extracts facts.
- Verifies dates and units.
- Prepares structured JSON.
- Saves the file locally.

### Step 4 — Validate

```bash
invest research earnings validate \
  /app/local-data/msft-earnings.json
```

### Step 5 — Preview

```bash
invest research earnings import \
  /app/local-data/msft-earnings.json
```

### Step 6 — Explicit acceptance

```bash
invest research earnings import \
  /app/local-data/msft-earnings.json --yes
```

### Step 7 — Retrieve saved research

```bash
invest research earnings list --ticker MSFT
invest research earnings summary RUN_ID
```

### Step 8 — Compare across periods

```bash
invest research earnings compare RUN_A RUN_B
```

### Step 9 — Use the results in broader research

The agent may use the verified financial figures, historical comparisons and source-backed findings when forming an investment thesis.

The human decides whether those findings warrant a change to portfolio targets.

Investobot does not make trades based on research results.

---

# 13. Mandatory BDD Requirements

All new behavior must follow strict Red → Green → Refactor.

Use only fictional or explicitly synthetic financial data in automated tests.

No live SEC, FMP or brokerage access is required.

## 13.1 Skill integration

```gherkin
Feature: Discoverable investment research skills

Scenario: Earnings and political research use agent skills
  Given Investobot's bundled research skills
  When they are installed for Codex
  Then both skills are discoverable
  And both have valid SKILL.md metadata
  And both reference their authoritative JSON contracts

Scenario: Installing skills preserves user modifications
  Given a user-modified installed skill exists
  When installation is requested without overwrite permission
  Then the existing skill is not overwritten
  And no unrelated files are changed
```

## 13.2 Financial data validation

```gherkin
Feature: Accurate earnings research

Scenario: Accept a source-backed quarterly revenue figure
  Given a fictional company has a verified quarterly filing
  And revenue has an exact Decimal value and reporting period
  When earnings research is validated
  Then the revenue observation is accepted
  And its original source and reporting period are retained

Scenario: Reject unsupported financial observations
  Given a financial metric lacks valid source evidence
  When earnings research is validated
  Then validation fails
  And no research data is persisted

Scenario: Prevent period confusion
  Given a nine-month operating cash-flow disclosure
  When earnings research is submitted as standalone third-quarter cash flow
  Then the unsupported quarterly representation is rejected
```

## 13.3 GAAP and non-GAAP

```gherkin
Feature: Financial metric comparability

Scenario: GAAP and adjusted earnings remain distinct
  Given a GAAP EPS observation and a non-GAAP EPS observation
  When earnings research is summarized
  Then both observations retain their original accounting basis
  And they are not silently combined

Scenario: Incompatible reporting periods cannot produce growth rates
  Given annual revenue and quarterly revenue observations
  When those observations are compared
  Then no percentage growth is calculated
  And an incompatible-period warning is returned
```

## 13.4 Guidance

```gherkin
Feature: Saved earnings guidance

Scenario: Management guidance is preserved historically
  Given a fictional company has issued a sourced revenue guidance range
  When that research is accepted
  And a later research run contains revised guidance
  Then the original guidance remains unchanged
  And the later guidance is stored separately
```

## 13.5 Immutability

```gherkin
Feature: Immutable company research

Scenario: Identical research imports are idempotent
  Given an earnings research package has been accepted
  When the identical package is imported again
  Then no duplicate run or metric records are created

Scenario: Partial import failure rolls back
  Given an earnings package with multiple related records
  When one record fails a database constraint
  Then no partial research run is persisted

Scenario: Earnings research does not modify the financial ledger
  Given accepted holdings and a saved investment plan
  When earnings research is imported
  Then accepted holdings and tax lots remain unchanged
  And the plan's stale status is unchanged
```

## 13.6 Required unit and integration tests

Also cover:

- Unknown company/security identity.
- Multiple share classes and ticker aliases.
- Missing CIK.
- Duplicate metric IDs.
- Conflicting values for the same reported fact.
- Different segment scopes.
- Invalid units.
- Missing duration dates.
- Invalid instant/duration combinations.
- Invalid guidance ranges.
- Invalid source identifiers.
- SEC accession references.
- Amended filings.
- Restated financial results.
- Empty but explicitly partial research packages.
- Decimal precision beyond the default context.
- Idempotence despite JSON property or collection ordering.
- CLI JSON schema discovery.
- Compact listing without full package reads.
- Safe skill installation paths.
- Historical research reproducibility.
- Political research regression tests.

---

# 14. Implementation Packages and Order

| Order | Package | Priority | Deliverable |
|---|---|---|---|
| 1 | Political research hardening | P0 | Three focused fixes and tests |
| 2 | Agent Skills foundation | P1 | Portable skill format, discovery, installation, political migration |
| 3 | Earnings skill and JSON models | P0 | Step-by-step skill and validated financial contract |
| 4 | Research persistence | P0 | Schema 5, shared research tables, earnings-specific tables |
| 5 | Earnings CLI and calculations | P0 | Validate, preview, import, list, show, summary, compare |
| 6 | Integration, documentation and CI | P1 | End-to-end regression and release verification |

Each package must be committed only after new BDD scenarios are made to fail for the intended reason, production changes make them pass, and the relevant regression tests are green.

Do not combine unrelated code changes merely to reduce the number of commits.

---

# 15. Documentation

Update:

```text
README.md
AGENTS.md
docs/agent-usage.md
docs/data-model.md
docs/development.md
docs/political-research.md
docs/prompts.md
```

Add:

```text
docs/research-skills.md
docs/earnings-research.md
```

Document:

- The difference between agent skills and CLI commands.
- Installing skills for Codex and Claude Code.
- How skills are discovered and invoked.
- The required earnings JSON format.
- SEC source references and XBRL limitations.
- Reporting periods and financial metric definitions.
- The research preview and acceptance process.
- How research history is preserved.
- Why research imports do not alter portfolio facts.
- Schema 5 reset instructions.
- The difference between completed synthetic tests and unverified live research.

Do not claim that SEC parsing or institution integration has been validated against real data merely because synthetic tests pass.

---

# 16. Explicitly Out of Scope

This PRD does not include:

- Automatic SEC fetching inside Investobot.
- A full EDGAR client.
- A built-in earnings-calendar service.
- Background research scheduling.
- Continuous news monitoring.
- Management insider trading research.
- Competitor analysis.
- Valuation models.
- DCF calculations.
- Analyst estimates.
- Market consensus forecasts.
- Alternative-data subscriptions.
- Embedding or semantic search.
- Research-generated automatic trades.
- New portfolio construction strategies.
- Automatic financial data reconciliation against brokerage holdings.
- Conversion of all existing general-purpose prompts into skills.

Future skills may reuse the shared research infrastructure, but they require their own explicit scopes and financial contracts.

---

# 17. Acceptance Workflow

The final release demonstration should use a fictional SEC-reporting company.

An external agent receives:

> Research this company's quarterly earnings using Investobot's earnings skill. Prepare structured financial JSON, validate it, and present the results for acceptance.

Expected result:

1. The agent discovers and reads the installed skill.
2. The agent identifies the company and reporting period.
3. The agent produces source-backed structured JSON.
4. Investobot rejects invalid periods, measurements and references.
5. Valid research is previewed without writes.
6. Explicit confirmation saves immutable research.
7. Research summaries retrieve the saved values.
8. A subsequent reporting period creates a separate research run.
9. Comparisons use only compatible metrics.
10. Financial changes are calculated deterministically using Decimal.
11. The original results and evidence remain reproducible.
12. The investment ledger, tax lots, targets and plans remain untouched.
13. The political-contribution skill continues to work.
14. All tests and CI checks pass.

---

# 18. Final Definition of Done

Investobot V2.6 is complete when:

1. The three V2.5 political research hardening issues are resolved.
2. Political-contribution research uses an installable agent skill.
3. Earnings research uses an installable agent skill.
4. Both skills follow the open `SKILL.md` format.
5. Both skills work with the existing deterministic CLI architecture.
6. Skills can be installed for Codex and Claude Code without running embedded AI.
7. Financial research JSON is validated using authoritative Pydantic models.
8. Earnings metrics preserve exact values, periods, units, accounting basis and source identifiers.
9. Guidance and findings are stored separately from reported historical facts.
10. Research imports are atomic, immutable and idempotent.
11. SQLite can efficiently retrieve individual reports and financial metrics.
12. Earnings comparisons use deterministic financial arithmetic.
13. Incompatible periods or metrics cannot silently produce misleading calculations.
14. Imported research has no effect on accepted portfolio state or saved-plan freshness.
15. All BDD and regression tests pass.
16. Ruff passes.
17. Offline Docker CI passes.
18. The existing WebUI and general Prompt Library remain functional.
19. Documentation accurately describes skill installation, research workflow and database reset requirements.

## Guiding Principle

**An agent skill defines the research method. Structured JSON defines the evidence contract. SQLite preserves the research. Deterministic Python calculates the results. The human makes the investment decision.**

This should become the standard Investobot architecture for future research capabilities, without turning Investobot itself into an AI application.
