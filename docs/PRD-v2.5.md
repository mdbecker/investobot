# Investobot — Executive Political-Contribution Research

**Product Requirements Document — Version 2.5**

**Baseline:** Investobot V2.4 complete\
**Priority:** P2 — Optional investment research capability\
**Methodology:** BDD — Red → Green → Refactor\
**Architecture:** SQLite + Pydantic + Typer + external research agents

## 1. Objective

Add a small, auditable, structured research capability that allows Investobot to retain verified information about political contributions associated with a company's publicly identified senior executives.

External AI coding agents perform research using browser-accessible and otherwise authorized sources.

Investobot validates, stores, queries, summarizes, and exports the resulting evidence.

The system must clearly distinguish:

1. The company being researched.
2. Its verified executives.
3. Political recipients and their documented affiliations.
4. Verified monetary transactions.
5. Underlying evidence and source permissions.
6. Ambiguous findings and incomplete coverage.

This feature is for research context, not political profiling or automated investment decision-making.

## 2. Non-Negotiable Requirements

Keep:

- Local SQLite.
- Deterministic calculations.
- Strict Pydantic input validation.
- Structured JSON CLI output.
- Agent-first research.
- Immutable accepted research runs.
- Source URLs and provenance.
- Strict BDD development.

Do not introduce:

- Embedded AI.
- Automated political web scraping.
- A built-in FEC API client.
- Commercial data subscriptions.
- A vector database.
- A graph database.
- Political ideology or donor-preference scoring.
- Trading signals derived automatically from donation history.
- New portfolio optimization rules.

Political research must remain separate from authoritative household financial state.

## 3. Source-Use and Privacy Gate

**This package must not assume that publicly available personal-contribution records are freely reusable.**

The FEC restricts individual-contributor information from its disclosures for commercial purposes and fundraising solicitation.

Because Investobot supports investment research, permissible uses of FEC-derived named contributor records must be reviewed before importing them.

Requirements:

- Record source origin and applicable use restrictions.
- Permit named contribution imports only when a permissible source-use basis has been documented.
- Do not allow agent-supplied `rights_basis` text alone to authorize import.
- Do not allow `--yes` to override blocked-source restrictions.
- Treat FEC-derived individual-contributor records as restricted unless a separate reviewed policy explicitly allows the intended use.
- Do not bypass restrictions through third-party copies of the same records.
- Do not collect donor addresses, ZIP codes, private contact details or unrelated identifiers.
- No fundraising, solicitation, advertising, resale or donor-list exports.
- Retain only necessary senior-executive identity and verified transaction evidence.
- If permissions are unresolved, allow the research to be saved without person-attributed contribution records, with `BLOCKED` or `PARTIAL` coverage.

The MVP does not require a general source-licensing framework.

A small documented, locally configured reviewed-source policy is sufficient. The importer must enforce it independently of the agent-produced JSON.

Sources requiring legal interpretation remain disabled until that interpretation has been documented.

Relevant official references:

- [https://www.fec.gov/updates/sale-or-use-contributor-information/](https://www.fec.gov/updates/sale-or-use-contributor-information/)
- [https://www.fec.gov/updates/use-of-contributor-information/](https://www.fec.gov/updates/use-of-contributor-information/)
- [https://api.open.fec.gov/developers/](https://api.open.fec.gov/developers/)

## 4. User Workflow

### Step 1 — Select a company

The user asks an external agent:

> Research the disclosed political contributions associated with senior executives of Company X between January 1, 2024 and December 31, 2026.

### Step 2 — Load the bundled prompt

```
invest prompt show executive-political-contributions
```

The user copies the Markdown prompt into Codex or Claude Code.

Investobot does not execute the prompt.

### Step 3 — Research

The agent:

- Identifies executives.
- Verifies roles.
- Checks permitted sources.
- Finds eligible public contribution evidence.
- Resolves recipients.
- Reviews ambiguities, refunds, duplicate records and source restrictions.
- Produces structured JSON.

### Step 4 — Validate the result

```
invest research political validate \
  /app/local-data/political-research.json
```

The validator returns:

- Schema validity.
- Executive identity status.
- Missing recipient metadata.
- Invalid source references.
- Duplicate transactions.
- Source-use restrictions.
- Unresolved or excluded findings.
- Overall readiness.

It performs no writes.

### Step 5 — Preview and explicitly import

```
invest research political import \
  /app/local-data/political-research.json
```

Default: preview.

Then:

```
invest research political import \
  /app/local-data/political-research.json --yes
```

Accepted research becomes an immutable research run.

### Step 6 — Query or summarize

```
invest research political list --ticker EXAMPLE
invest research political show RUN_ID
invest research political summary RUN_ID
```

The agent may use the returned evidence in a broader investment research report.

No portfolio balances, targets or trade plans are modified.

---

# 5. SQLite Schema

Use SQLite schema version **4**.

Consistent with the previously agreed disposable-database development policy, a deliberate database reset is acceptable. Do not silently delete an existing database.

Create six narrowly scoped research tables.

## 5.1 `research_political_runs`

One immutable accepted research package.

```
CREATE TABLE research_political_runs (
    id TEXT PRIMARY KEY,
    company_name TEXT NOT NULL,
    ticker TEXT,
    security_id TEXT,
    jurisdiction TEXT NOT NULL
        CHECK (jurisdiction = 'US_FEDERAL'),
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    researched_as_of TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    coverage_status TEXT NOT NULL
        CHECK (coverage_status IN (
            'COMPLETE_WITHIN_DECLARED_SCOPE',
            'PARTIAL',
            'BLOCKED'
        )),
    rights_status TEXT NOT NULL
        CHECK (rights_status IN (
            'APPROVED',
            'PENDING_REVIEW',
            'BLOCKED'
        )),
    limitations_json TEXT NOT NULL,
    unresolved_matches_json TEXT NOT NULL,
    FOREIGN KEY (security_id)
        REFERENCES securities(id)
);

CREATE INDEX research_political_company_idx
ON research_political_runs (
    ticker,
    researched_as_of DESC
);
```

Use a SHA-256 hash of the normalized research package as the run ID.

Re-importing identical research must be idempotent.

Changing the research produces a new immutable run.

`security_id` may be null for companies that are private, unregistered in Investobot or otherwise not associated with a canonical security.

## 5.2 `research_political_sources`

Source provenance and reviewed use status.

```
CREATE TABLE research_political_sources (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    url TEXT NOT NULL,
    publisher TEXT NOT NULL,
    source_type TEXT NOT NULL,
    published_at TEXT,
    accessed_at TEXT NOT NULL,
    individual_contributor_data INTEGER NOT NULL
        CHECK (individual_contributor_data IN (0, 1)),
    rights_basis TEXT NOT NULL,
    FOREIGN KEY (run_id)
        REFERENCES research_political_runs(id),
    UNIQUE (run_id, url)
);
```

Keep source metadata, not copied pages of contributor information.

The importer must reject unsupported or blocked source uses based on trusted configuration, not on this table's descriptive metadata alone.

Strip credentials and API keys from URLs before storage.

## 5.3 `research_political_executives`

Public corporate identities within a research run.

```
CREATE TABLE research_political_executives (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL,
    role_start TEXT,
    role_end TEXT,
    role_source_id TEXT NOT NULL,
    identity_status TEXT NOT NULL
        CHECK (identity_status = 'VERIFIED'),
    FOREIGN KEY (run_id)
        REFERENCES research_political_runs(id),
    FOREIGN KEY (role_source_id)
        REFERENCES research_political_sources(id)
);
```

Only publicly verified corporate officers and directors may be included.

The person's political party must not be stored or inferred.

## 5.4 `research_political_recipients`

Recipients of political contributions.

```
CREATE TABLE research_political_recipients (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    name TEXT NOT NULL,
    recipient_type TEXT NOT NULL
        CHECK (recipient_type IN (
            'CANDIDATE_COMMITTEE',
            'PARTY_COMMITTEE',
            'PAC',
            'JOINT_FUNDRAISER',
            'OTHER_COMMITTEE'
        )),
    committee_id TEXT,
    candidate_id TEXT,
    candidate_name TEXT,
    recipient_party TEXT NOT NULL
        CHECK (recipient_party IN (
            'DEMOCRATIC',
            'REPUBLICAN',
            'OTHER',
            'NONPARTISAN',
            'UNKNOWN'
        )),
    party_basis TEXT NOT NULL,
    election_cycle INTEGER,
    party_source_id TEXT NOT NULL,
    FOREIGN KEY (run_id)
        REFERENCES research_political_runs(id),
    FOREIGN KEY (party_source_id)
        REFERENCES research_political_sources(id)
);
```

Requirements:

- Prefer official candidate and committee IDs.
- Verify candidate-to-committee relationships.
- Keep PACs and joint fundraising committees distinct from candidate campaigns.
- Do not assign a recipient to a party based solely on its name or perceived ideology.
- Preserve the documented affiliation for the relevant election period.
- Use `UNKNOWN` where affiliation cannot be verified.

## 5.5 `research_political_contributions`

Verified transactions only.

```
CREATE TABLE research_political_contributions (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    executive_id TEXT NOT NULL,
    recipient_id TEXT NOT NULL,
    transaction_date TEXT NOT NULL,
    amount_usd TEXT NOT NULL,
    transaction_kind TEXT NOT NULL
        CHECK (transaction_kind IN (
            'CONTRIBUTION',
            'REFUND',
            'REATTRIBUTION',
            'REDESIGNATION',
            'MEMO',
            'OTHER'
        )),
    channel TEXT NOT NULL
        CHECK (channel IN (
            'DIRECT',
            'EARMARKED',
            'COMMITTEE',
            'UNKNOWN'
        )),
    source_system TEXT NOT NULL,
    source_record_id TEXT NOT NULL,
    underlying_transaction_key TEXT,
    countable INTEGER NOT NULL
        CHECK (countable IN (0, 1)),
    notes TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (run_id)
        REFERENCES research_political_runs(id),
    FOREIGN KEY (executive_id)
        REFERENCES research_political_executives(id),
    FOREIGN KEY (recipient_id)
        REFERENCES research_political_recipients(id),
    UNIQUE (
        run_id,
        source_system,
        source_record_id
    ),
    CHECK (
        countable = 0
        OR underlying_transaction_key IS NOT NULL
    )
);

CREATE UNIQUE INDEX research_political_counted_once_idx
ON research_political_contributions (
    run_id,
    underlying_transaction_key
)
WHERE countable = 1;

CREATE INDEX research_political_executive_idx
ON research_political_contributions (
    executive_id,
    transaction_date
);
```

Rules:

- Only verified identities may produce accepted contribution records.
- Financial values use validated Decimal strings.
- Countable contributions are positive amounts.
- Countable refunds are negative amounts.
- Adjustment and memo records must not silently affect totals.
- An earmarked contribution must not be counted twice from conduit and final recipient filings.
- An unresolved underlying transaction cannot be designated `countable=true`.
- Dates and amounts must be evidence-backed.
- Source record identifiers must not be fabricated.

Validate all referenced IDs belong to the same research run.

## 5.6 `research_political_evidence`

Links transaction records to their supporting sources.

```
CREATE TABLE research_political_evidence (
    contribution_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    PRIMARY KEY (contribution_id, source_id),
    FOREIGN KEY (contribution_id)
        REFERENCES research_political_contributions(id),
    FOREIGN KEY (source_id)
        REFERENCES research_political_sources(id)
);
```

Every imported transaction requires at least one permitted source reference.

Use additional source links when independent corroboration is available.

No raw HTML, scraped page archives, contributor addresses or donor contact information should be stored.

---

# 6. Structured JSON Contract

Add the Pydantic model:

```
PoliticalResearchInput
```

Reuse the complete JSON contract provided in the bundled agent prompt.

Its main collections are:

```
company
scope
sources[]
executives[]
recipients[]
contributions[]
unresolved_matches[]
limitations[]
```

Required validation:

1. Reject unknown fields.
2. Validate all dates and date ranges.
3. Use Decimal for amounts.
4. Reject nonfinite numerical values.
5. Resolve all cross-references.
6. Validate corporate identity evidence.
7. Require verified identity for accepted transactions.
8. Require documented recipient affiliations.
9. Reject duplicate contribution records.
10. Reject double-counted underlying transactions.
11. Reject restricted-source imports without documented permission.
12. Reject unnecessary personal data fields.
13. Reject records outside the research period.
14. Reject internal inconsistencies atomically.

Pydantic should be authoritative for JSON input validation.

Use SQLite constraints as additional integrity protection.

Do not create two parallel schema registries.

---

# 7. Deterministic Research Summaries

Implement:

```
invest research political summary RUN_ID
```

Return structured JSON resembling:

```
{
  "research_run_id": "RUN_ID",
  "company": "Example Corporation",
  "period_start": "2024-01-01",
  "period_end": "2026-10-09",
  "coverage_status": "PARTIAL",
  "rights_status": "APPROVED",
  "executives_reviewed": 6,
  "verified_transactions": 12,
  "totals_by_recipient_party": {
    "DEMOCRATIC": "5000.00",
    "REPUBLICAN": "4000.00",
    "OTHER": "0",
    "NONPARTISAN": "0",
    "UNKNOWN": "1000.00"
  },
  "totals_by_recipient_type": {
    "CANDIDATE_COMMITTEE": "7000.00",
    "PARTY_COMMITTEE": "2000.00",
    "PAC": "1000.00",
    "JOINT_FUNDRAISER": "0",
    "OTHER_COMMITTEE": "0"
  },
  "unresolved_match_count": 2,
  "warnings": [
    "This is a partial disclosure-based view, not a complete record of political activity."
  ]
}
```

All numbers above are illustrative.

Summaries are calculated from eligible, counted transactions, not accepted from agent-generated totals.

Requirements:

- Net refunds only when correctly linked.
- Avoid counting conduit and recipient duplicates.
- Do not infer a party from a PAC's spending or candidate associations.
- Do not infer executives' personal political identities.
- Do not calculate a political leaning or ideological alignment score.
- Never interpret absence of disclosed donations as evidence of no donations.
- Clearly label incomplete reporting periods and research limitations.

Add the ability to inspect verified contributions grouped by executive and recipient, with transaction-level source references.

Party and recipient categories must remain separate.

---

# 8. CLI Integration

Add a small Typer command group:

```
invest research political validate FILE
invest research political import FILE
invest research political import FILE --yes
invest research political list
invest research political list --ticker TICKER
invest research political show RUN_ID
invest research political summary RUN_ID
```

Behavior:

- `validate`: Read-only schema, evidence, and permissions check.
- `import`: Preview by default; `--yes` explicitly accepts.
- `list`: Small research-run summaries, no full evidence objects.
- `show`: Full structured research package with source references.
- `summary`: Deterministic aggregate results.

All stdout remains JSON.

Update:

```
invest tools list
invest tools describe research.political.validate
invest tools describe research.political.import
invest schema
```

Document that import mutates the research database only, never actual financial holdings, security classifications, targets or saved plans.

Research imports must not alter financial planning-state fingerprints or stale existing plans.

---

# 9. Prompt Library Integration

Bundle:

```
src/invest/prompt_defaults/executive-political-contributions.md
```

The existing WebUI Prompt Library automatically makes the Markdown prompt readable and copyable.

Do not execute research through the WebUI.

Do not introduce a dedicated political research dashboard as part of this PRD.

The CLI and existing reporting workflow are sufficient for the initial release.

---

# 10. Mandatory BDD Scenarios

Use synthetic fictional companies, executives, recipients and transaction records.

No real political contributor data is needed for automated tests.

### Research and identity

```
Feature: Verified political research

Scenario: Import documented executive contributions
  Given a fictional company's executives have verified public roles
  And permissible synthetic contribution sources exist
  When a validated research package is explicitly accepted
  Then its executives, recipients, contributions and sources are saved
  And actual portfolio holdings remain unchanged

Scenario: Reject ambiguous contributor identity
  Given a name-only match to a fictional executive
  When a transaction is submitted as verified without evidence
  Then validation rejects the attribution
  And no contribution is accepted
```

### Monetary accounting

```
Feature: Contribution accounting

Scenario: Earmarked donations are counted once
  Given a fictional contribution appears in conduit and recipient records
  When the accepted research is summarized
  Then the underlying contribution is counted once

Scenario: Refunds reduce verified contribution totals
  Given a verified contribution and its documented refund
  When research totals are calculated
  Then the refund reduces the appropriate recipient total
  And the source transaction history remains available
```

### Attribution

```
Feature: Recipient attribution

Scenario: PAC contributions are not attributed to unrelated candidates
  Given a contribution to a PAC
  When the research is summarized
  Then the transaction remains associated with the PAC
  And no candidate contribution is invented

Scenario: Recipient party is not donor party
  Given a verified contribution to a Democratic candidate committee
  When the research is displayed
  Then the recipient party is Democratic
  And no political affiliation is assigned to the executive
```

### Source compliance

```
Feature: Restricted research sources

Scenario: A restricted donor source cannot be imported
  Given a research package contains individually attributable restricted FEC data
  And no permissible source-use basis has been approved
  When import is attempted with confirmation
  Then import is rejected
  And no restricted contribution details are persisted
```

### Idempotence and financial isolation

```
Feature: Immutable political research

Scenario: Repeated research imports are idempotent
  Given a political research package has been accepted
  When the identical package is imported again
  Then no duplicate research run or transaction is created

Scenario: Research does not invalidate trade plans
  Given an immutable saved portfolio plan exists
  When political research is imported
  Then accepted holdings are unchanged
  And the saved portfolio plan's financial stale status is unchanged
```

Additional required tests:

- Invalid JSON.
- Incorrect date ranges.
- Duplicate source identifiers.
- Invalid source references.
- Same-name executive collisions.
- Unknown party affiliations.
- Unknown committee/candidate relationships.
- Amendments and memo-only records.
- Rejected permission overrides.
- Cross-run foreign-key violations.
- SQLite transaction rollback.
- Empty research results.
- Large but valid JSON input.
- Compact listing performance.
- Independent research-run reproducibility.

All tests run offline.

---

# 11. Implementation Packages

## Package 1 — Schema and Models

- Add schema version 4 tables.
- Add Pydantic research input models.
- Add source-use enforcement.
- Add BDD coverage for validation and privacy.

## Package 2 — Research Import

- Implement preview/confirmation workflow.
- Normalize sources, executives, recipients and transactions.
- Enforce referential integrity and deduplication.
- Save immutable research packages atomically.
- Add BDD coverage for identity and audit safety.

## Package 3 — Queries and Summaries

- Implement list, show and summary commands.
- Calculate verified net totals by recipient and party.
- Handle adjustments and unresolved findings.
- Add machine-readable contracts.
- Add BDD coverage for accounting and attribution.

## Package 4 — Prompt and Documentation

- Bundle the step-by-step research prompt.
- Update prompt library documentation.
- Update agent usage instructions.
- Document source-use restrictions.
- Update database documentation.
- Run complete CI, Ruff, and regression tests.

Every package follows Red → Green → Refactor.

---

# 12. Out of Scope

Do not implement:

- Real-time campaign monitoring.
- Background data collection.
- Automated FEC ingestion.
- Campaign contribution alerts.
- State and local campaign finance adapters.
- Bulk donor-list construction.
- Donation solicitation tools.
- Personal political preference prediction.
- Political ideology scoring.
- Automatic investment recommendations based on political donations.
- Tax, portfolio planning or trading engine changes.

Future state/local coverage requires explicitly identified disclosure sources, legal review, and additional source-specific normalization.

---

# 13. Definition of Done

V2.5 is complete when:

1. The bundled research prompt is available in Investobot.
2. An external agent can produce valid structured JSON.
3. Invalid and ambiguous identities are rejected.
4. Recipient attribution is supported by evidence.
5. Permitted verified transactions can be stored.
6. Restricted-source data cannot bypass the compliance gate.
7. Duplicates, conduits, refunds and adjustments are handled conservatively.
8. Research summaries are calculated deterministically.
9. Imported research remains immutable and auditable.
10. Political research is completely isolated from portfolio financial state.
11. New and existing BDD tests pass.
12. Ruff and Docker CI pass.
13. No unnecessary infrastructure or automation is introduced.

## Guiding Principle

**Research externally. Verify identities. Preserve evidence. Store only permitted, trustworthy facts. Calculate descriptive results deterministically.**

Investobot should provide transparent research context without inferring political beliefs or turning personal donations into automated investment decisions.

---

## Implementation notes

The requirements above preserve the attached V2.5 specification. Its baseline
statement does not establish a remote GitHub Actions result; local offline Docker
verification and the unverified remote acceptance gate remain distinct.

The implementation adds optional `original_contribution_id` to the contribution
contract so counted refunds can be linked explicitly to the original counted
contribution in the same research package. A role biography alone cannot support
transaction attribution. The operating guide documents the independent reviewed
source-policy format and `INVEST_RESEARCH_POLICY` configuration:
[political-research.md](political-research.md).

Schema 4 rejects earlier ledgers deliberately. No migration or automatic deletion
is provided. Development and verification use disposable synthetic databases;
private ledger resets require a separate deliberate decision and preserve prompts.

