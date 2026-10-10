# Investobot — News, Catalysts & Thesis-Change Research

Follow-up requirements are preserved in the [Research Continuity & Disputed-Claim
Addendum](PRD-v2.7-Addendum-Research-Continuity.md). The original PRD below remains unchanged.

**Product Requirements Document — Version 2.7**  
**Repository:** https://github.com/mdbecker/investobot  
**Baseline:** V2.6, commit `8722093` (verified on `main` October 10, 2026)  
**Priority:** P1 — Recurring company-research capability  
**Methodology:** Strict BDD — Red → Green → Refactor  
**Architecture:** Agent Skills + Pydantic + SQLite + Typer  
**Database policy:** Fresh schema permitted; no migration required for disposable development ledgers

---

## 1. Executive Summary

Add an installable **`investobot-news`** Agent Skill and deterministic `invest research news` commands for monitoring a company's material developments, upcoming catalysts, and changes to documented investment-thesis hypotheses.

The external Codex or Claude Code agent researches current sources and produces **strict, source-backed JSON**. Investobot validates it, previews an explicit import, saves an immutable research run, and calculates **what changed since a selected previous run**. The principal user experience is *incremental research*, not repeatedly producing a generic company summary.

Every event must retain its title, date or explicitly unknown date, category, original source, affected business segment, verified facts, potential business implications, uncertainty, and follow-up questions. Catalysts and thesis assessments are distinct structured records. All interpretations remain attributed to the research agent, not presented as verified company facts.

**Guiding principle:** The agent discovers and verifies developments; Investobot persists evidence and deterministically compares snapshots; the human evaluates the investment thesis and decides what to do.

## 2. Goals and Success Criteria

1. Research any identified company with a reusable, portable Agent Skill.
2. Reuse V2.6's skill discovery, safe installation, Pydantic schema discovery, shared `research_runs`/`research_sources`, and research-only mutation boundary.
3. Produce validated, structured JSON rather than only Markdown narratives.
4. Persist immutable run history and query individual events, catalysts, facts, and thesis assessments.
5. Identify **newly observed events, material updates, new corroborating sources, catalyst status/date changes, thesis-assessment changes, and unresolved follow-ups** between comparable runs.
6. Avoid treating duplicate articles, cosmetic rewriting, absent coverage, or older re-published news as newly occurred events.
7. Never alter holdings, prices, classifications, tax lots, targets, accepted thesis decisions, or saved-plan freshness.
8. Preserve source traceability, uncertainty, and historical reproducibility; run the complete suite offline.

**MVP success:** For a synthetic company, three successive research runs correctly show (a) an event newly discovered, (b) the same event updated with a new verified fact, (c) a catalyst postponed, and (d) a hypothesis assessment changed, without duplicating events or claiming a missing event was resolved.

## 3. Scope and Architecture

**In scope:** One canonical skill, news JSON schema, source-backed event/catalyst/thesis data, a small schema-6 expansion, CLI validation/import/inspection, baseline context for subsequent research, deterministic run comparisons, synthetic BDD tests, and documentation.

**Out of scope:** Investobot web scraping, RSS ingestion, a news provider subscription, background polling or alerts, news sentiment models, LLM execution, MCP, a vector database, a generic search crawler, price predictions, automated buy/sell signals, or integration of research into portfolio-planning calculations.

The existing political-contributions and earnings skills and CLI commands remain operational. Do not replace the V2.6 storage model or rewrite the existing research domains.

---

## 4. Agent Skill Package

Create the canonical skill:

```text
skills/investobot-news/
  SKILL.md
  references/
    research-method.md
    event-identity.md
    json-contract.md
    change-review.md
```

The `SKILL.md` must conform to the Agent Skills convention, including at least:

```yaml
---
name: investobot-news
description: Research source-backed company news, upcoming catalysts, and changes to investment-thesis hypotheses; produce structured JSON for Investobot comparison.
metadata:
  version: "1.0.0"
---
```

Register the skill with the existing `research_skills` registry and distribution packaging. Its version and supported input schema come from trusted bundled metadata, **not from agent-supplied JSON**. Avoid changing the versions or content hashes of unrelated skills unnecessarily; if the current global skill-version constant makes this impossible, make the smallest compatible adjustment for per-skill versions.

It must work with existing discovery/installation:

```sh
invest research skills list
invest research skills show investobot-news
invest research skills install --agent codex --workspace .
invest research skills install --agent claude-code --workspace .
```

Retain project-local installation, no unsolicited overwrites, symlink/traversal safeguards, and offline operation. The skill conducts research through the external agent's authorized tools. **The CLI does not execute the skill or browse websites.**

### 4.1 Required skill workflow

The skill shall instruct the agent to:

1. **Resolve entity and request.** Verify company name, ticker, optional CIK/security ID, operating segments, monitoring window, and research timestamp. Distinguish similarly named issuers and historic ticker changes.
2. **Load prior baseline.** Call `invest research news context --ticker TICKER` when prior research exists; review stable event keys, open catalysts, tracked theses, last covered window, and unresolved questions. If no run exists, begin an explicitly labeled initial baseline.
3. **Search the declared period.** Check official issuer/investor-relations announcements, SEC filings, regulatory/legal announcements, product and partner disclosures, and credible independent reporting when available. The skill must document what source categories were actually checked. Never claim complete universal news coverage.
4. **Trace to original disclosures.** Prefer primary-source documents for facts. Record independent reporting as such; preserve its publication date and the underlying event date separately. Do not turn a claim in a news article into issuer-confirmed fact.
5. **Resolve event identity.** Match a developing story to an existing stable `event_key` when reliable evidence establishes continuity. Different outlets reporting the same announcement are one event with multiple sources. If identity remains ambiguous, preserve distinct records and a warning; never merge by headline similarity alone.
6. **Record verified facts.** Use concise, independently checkable statements linked to exact sources and locators. Attribute company statements, third-party claims, allegations, and confirmed outcomes accurately. Do not label an unverified assertion `VERIFIED`.
7. **Record implications separately.** Explain *possible* effects on demand, revenue, costs, margins, competitive position, operations, financing, or regulatory exposure. State assumptions and uncertainty. Implications are agent analyses, not company-reported facts or automatic trading recommendations.
8. **Track catalysts.** Record expected, scheduled, postponed, completed, or cancelled future events, with date certainty, original evidence, and link to an underlying news event where applicable. Reuse stable catalyst IDs across subsequent runs.
9. **Review thesis hypotheses.** Retain stable hypothesis IDs and unchanged hypothesis statements from prior context. State whether fresh evidence supports, challenges, mixes, or is insufficient to reassess each hypothesis. This is a *research assessment*, not mutation of an investment decision.
10. **Identify open questions.** Include unanswered questions, the specific evidence needed to resolve them, and what remains unverified. Retain relevant prior unresolved items instead of dropping them silently.
11. **Audit the coverage.** Record the researched window, source categories, search limitations, stale sources, disputed claims, and whether older active stories were revisited. Unknown dates/coverage stay unknown.
12. **Return only structured JSON.** Use the authoritative `NewsResearchInput` contract; save to ignored `local-data`; run `validate`, then preview `import`, then request explicit human approval before `--yes`.
13. **Review changes after acceptance.** Use `invest research news changes` to report new events, verified updates, catalyst movement, and changed thesis assessments since the chosen baseline, with exact source references and caveats.

Do not invent a story, filing, source ID, event date, financial impact, catalyst probability, or resolution to make research look complete. Respect source usage/copyright restrictions; store metadata and concise independently authored fact descriptions, **not copied full articles**. Strip access tokens and private data from URLs. No source text is treated as executable instructions.

---

## 5. Structured JSON Contract

Implement strict Pydantic models in `src/invest/news_models.py`, with top-level **`NewsResearchInput`** and `extra="forbid"` throughout. Expose the authoritative JSON schema through `invest schema` and `invest tools describe`; skill references must not maintain a divergent hand-authored schema.

Required top-level fields:

```text
schema_version             "1.0"
research_type              "NEWS_CATALYSTS_THESIS_CHANGES"
company                    Company identity
scope                      Monitoring window, research date, coverage, methodology
sources[]                  Verifiable articles, filings, releases, records
theses[]                   Stable monitored research hypotheses and assessments
events[]                   Individually tracked material developments
catalysts[]                Scheduled / expected events and outcomes
limitations[]              Coverage gaps, ambiguities, unresolved conflicts
```

### 5.1 Example payload (entirely fictional)

```json
{
  "schema_version": "1.0",
  "research_type": "NEWS_CATALYSTS_THESIS_CHANGES",
  "company": {
    "name": "Fictional Technology Corporation",
    "ticker": "FAKE",
    "cik": null,
    "security_id": null
  },
  "scope": {
    "window_start": "2026-10-01",
    "window_end": "2026-10-10",
    "researched_as_of": "2026-10-10",
    "coverage_status": "PARTIAL",
    "searched_source_types": ["ISSUER_RELEASE", "REGULATORY_FILING", "NEWS_REPORT"],
    "coverage_notes": "Issuer releases and selected publications checked; not exhaustive."
  },
  "sources": [
    {
      "id": "s-release",
      "source_type": "ISSUER_RELEASE",
      "publisher": "Fictional Technology Corporation",
      "url": "https://example.invalid/fictional-announcement",
      "published_at": "2026-10-06",
      "accessed_at": "2026-10-10",
      "source_locator": "Announcement, opening paragraphs"
    }
  ],
  "theses": [
    {
      "thesis_id": "enterprise-demand",
      "statement": "Enterprise adoption remains a material growth driver.",
      "assessment": "INSUFFICIENT_EVIDENCE",
      "rationale": "One announcement is insufficient to establish company-wide demand.",
      "related_event_keys": ["fictional-product-announcement"],
      "uncertainty": "No verified revenue contribution or customer adoption figures."
    }
  ],
  "events": [
    {
      "event_key": "fictional-product-announcement",
      "title": "Fictional Corporation announces an enterprise product",
      "category": "PRODUCT",
      "event_date": "2026-10-06",
      "date_status": "CONFIRMED",
      "event_status": "ANNOUNCED",
      "affected_segments": ["Enterprise Software"],
      "primary_source_id": "s-release",
      "source_ids": ["s-release"],
      "facts": [
        {
          "fact_key": "launch-announced",
          "statement": "The company announced the new enterprise product.",
          "source_id": "s-release",
          "source_locator": "Opening paragraph",
          "verification_status": "VERIFIED"
        }
      ],
      "implications": [
        {
          "id": "demand-possibility",
          "area": "DEMAND",
          "statement": "The product could expand customer demand if adoption materializes.",
          "assumptions": "Requires customer uptake and commercial availability.",
          "uncertainty": "Adoption and financial contribution are unknown."
        }
      ],
      "follow_up_questions": [
        {
          "id": "uptake-data",
          "question": "Has the company disclosed customer uptake?",
          "status": "OPEN"
        }
      ]
    }
  ],
  "catalysts": [
    {
      "catalyst_id": "fictional-product-release",
      "title": "Expected product availability",
      "related_event_key": "fictional-product-announcement",
      "scheduled_date": null,
      "date_status": "UNKNOWN",
      "status": "EXPECTED",
      "source_id": "s-release",
      "source_locator": "Product availability section",
      "qualifiers": "No firm date disclosed."
    }
  ],
  "limitations": [
    "Entirely synthetic example; no real issuer or event is asserted."
  ]
}
```

### 5.2 Identity and time rules

- `company.security_id`, if present, must pass the existing `verify_company` security/ticker/CIK checks. Null is permitted for unregistered or private companies.
- `window_start <= window_end <= researched_as_of`. `researched_as_of` cannot be in the future. Separate source publication dates, event occurrence/announcement dates, upcoming catalyst dates, and run import timestamps.
- Event date must be ISO `YYYY-MM-DD` if known; null is allowed only with `date_status=UNKNOWN`. Estimated or expected dates must be labeled and must not be represented as confirmed occurrences.
- A catalyst may have a future scheduled date. A source's `published_at` may be unknown; `accessed_at` must be known and not after `researched_as_of`.
- Events describing an earlier development may appear in a later run when they remain relevant; label them *previously occurring, newly observed* rather than newly occurring.
- The reporting window covers research publication/discovery, not a guarantee that every event occurred during that window. The distinction must appear in documentation and output.

### 5.3 Event and evidence rules

Event categories (minimum): `EARNINGS`, `PRODUCT`, `CUSTOMER`, `PARTNERSHIP`, `MERGER_ACQUISITION`, `LEADERSHIP`, `REGULATORY`, `LITIGATION`, `CYBERSECURITY`, `CAPITAL_ALLOCATION`, `OPERATIONS`, `SUPPLY_CHAIN`, `MACRO_EXPOSURE`, `OTHER`.

Event lifecycle: `ANNOUNCED`, `DEVELOPING`, `CONFIRMED`, `RESOLVED`, `RETRACTED`, `UNKNOWN`.

Facts carry `VERIFIED` or `DISPUTED` status. **Only `VERIFIED` facts may be described as confirmed in summaries.** Conflicting source reports remain separately attributed and unresolved, never silently reconciled. Every fact requires a valid source and specific locator. A verified fact needs evidence beyond an unsupported agent assertion.

`event_key` is a stable, source-grounded identity for one underlying development. Prefer an authoritative announcement/filing/case/document identifier; when none exists, retain a consistent manually reviewed key across runs. Never generate event identity from title, date, or similarity alone. Preserve the same key when new reporting expands the same story; use a new key for independent events. A run cannot contain duplicate keys.

Affected segments are explicit strings; do not guess segment attribution. Facts must not include unsolicited personal information. Source URLs use the existing credential-safe normalization; do not discard safe public document locators.

### 5.4 Interpretations, follow-ups and thesis rules

Implications must identify an `area` (`DEMAND`, `REVENUE`, `MARGINS`, `COSTS`, `COMPETITION`, `OPERATIONS`, `LIQUIDITY`, `REGULATORY`, `OTHER`), a possible effect, its assumptions, and uncertainty. These are interpretations only; they cannot be promoted to reported financial metrics.

Follow-up questions have stable IDs and `OPEN`, `ANSWERED`, or `CLOSED_WITHOUT_ANSWER` statuses. Answered questions require a source-backed fact or a clear limitation explaining closure.

Theses have stable `thesis_id`, immutable statement per identity, `assessment` (`SUPPORTED`, `CHALLENGED`, `MIXED`, `INSUFFICIENT_EVIDENCE`), a rationale, uncertainty, and related event keys. Do **not** interpret an assessment as a trading signal, an official company fact, or a change to a human-accepted investment decision. Reusing one ID for a different thesis statement is an incompatible comparison, not an automatic rename.

Catalyst statuses: `EXPECTED`, `SCHEDULED`, `DELAYED`, `OCCURRED`, `CANCELLED`, `UNKNOWN`. Require cited evidence for dates and for any claimed completion, delay or cancellation. A disappearing catalyst does not mean it occurred or was cancelled.

### 5.5 Validation boundary

Pydantic checks types, lengths, enumerations, source references, same-run event/catalyst/thesis links, duplicate IDs, date consistency, and contradictions. SQLite enforces integrity. **Neither proves that a web source truly supports a claim.** Agents and humans must inspect the cited original evidence. Reject cross-company event reuse, secret-bearing source URLs, unsupported dates, and invalid references atomically.

---

## 6. SQLite Persistence — Schema 6

Initialize **SQLite `PRAGMA user_version=6`** for new ledgers. Refuse older, nonempty databases with a deliberate reset message; never auto-delete. Since earlier schema upgrades deliberately reset disposable data, no migration is required by this PRD. Do not reset a user's private ledger without an explicit decision and backup.

Reuse the existing V2.6 `research_runs` and `research_sources`. `research_runs.research_type` is `NEWS_CATALYSTS_THESIS_CHANGES`, with earnings-only fiscal fields null and `period_end=window_end`. Store `skill_name='investobot-news'`, independently pinned version, schema version, compact `summary_json`, and canonical immutable `package_json`.

**Small shared addition:** add nullable `published_at TEXT` and `source_locator TEXT` to the fresh schema definition of `research_sources` for news citations, without changing earnings source semantics. Existing earnings inserts should supply nulls/defaults for these fields. News source rows use the same run-scoped foreign keys.

Create the following five narrowly scoped relational tables, in addition to reused shared tables:

### 6.1 `research_news_scopes`

```sql
CREATE TABLE research_news_scopes (
    run_id TEXT PRIMARY KEY,
    window_start TEXT NOT NULL,
    window_end TEXT NOT NULL,
    coverage_status TEXT NOT NULL
        CHECK (coverage_status IN ('COMPLETE_WITHIN_DECLARED_SCOPE','PARTIAL','BLOCKED')),
    searched_source_types_json TEXT NOT NULL,
    coverage_notes TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES research_runs(id)
);
```

### 6.2 `research_news_events`

```sql
CREATE TABLE research_news_events (
    run_id TEXT NOT NULL,
    event_key TEXT NOT NULL,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    event_date TEXT,
    date_status TEXT NOT NULL,
    event_status TEXT NOT NULL,
    affected_segments_json TEXT NOT NULL,
    primary_source_id TEXT NOT NULL,
    source_ids_json TEXT NOT NULL,
    implications_json TEXT NOT NULL,
    follow_up_questions_json TEXT NOT NULL,
    material_fingerprint TEXT NOT NULL,
    PRIMARY KEY (run_id,event_key),
    FOREIGN KEY (run_id) REFERENCES research_runs(id),
    FOREIGN KEY (run_id,primary_source_id)
        REFERENCES research_sources(run_id,source_id)
);
CREATE INDEX research_news_event_key_idx
    ON research_news_events(event_key,run_id);
```

`material_fingerprint` is an internally calculated fingerprint of normalized, domain-significant event fields; the untrusted agent cannot choose it. Exclude purely editorial title changes, array order, and incidental source metadata. Material changes include verified factual claims, event lifecycle, date, affected segment, and declared implications; source-only additions receive a separate classification.

### 6.3 `research_news_facts`

```sql
CREATE TABLE research_news_facts (
    run_id TEXT NOT NULL,
    event_key TEXT NOT NULL,
    fact_key TEXT NOT NULL,
    statement TEXT NOT NULL,
    verification_status TEXT NOT NULL
        CHECK (verification_status IN ('VERIFIED','DISPUTED')),
    source_id TEXT NOT NULL,
    source_locator TEXT NOT NULL,
    PRIMARY KEY (run_id,event_key,fact_key),
    FOREIGN KEY (run_id,event_key)
        REFERENCES research_news_events(run_id,event_key),
    FOREIGN KEY (run_id,source_id)
        REFERENCES research_sources(run_id,source_id)
);
```

### 6.4 `research_news_catalysts`

```sql
CREATE TABLE research_news_catalysts (
    run_id TEXT NOT NULL,
    catalyst_id TEXT NOT NULL,
    title TEXT NOT NULL,
    related_event_key TEXT,
    scheduled_date TEXT,
    date_status TEXT NOT NULL,
    status TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_locator TEXT NOT NULL,
    qualifiers TEXT NOT NULL,
    PRIMARY KEY (run_id,catalyst_id),
    FOREIGN KEY (run_id) REFERENCES research_runs(id),
    FOREIGN KEY (run_id,related_event_key)
        REFERENCES research_news_events(run_id,event_key),
    FOREIGN KEY (run_id,source_id)
        REFERENCES research_sources(run_id,source_id)
);
```

### 6.5 `research_news_theses`

```sql
CREATE TABLE research_news_theses (
    run_id TEXT NOT NULL,
    thesis_id TEXT NOT NULL,
    statement TEXT NOT NULL,
    assessment TEXT NOT NULL
        CHECK (assessment IN (
            'SUPPORTED','CHALLENGED','MIXED','INSUFFICIENT_EVIDENCE'
        )),
    rationale TEXT NOT NULL,
    uncertainty TEXT NOT NULL,
    related_event_keys_json TEXT NOT NULL,
    PRIMARY KEY (run_id,thesis_id),
    FOREIGN KEY (run_id) REFERENCES research_runs(id)
);
```

All arrays stored as JSON in dedicated columns must be validated using the authoritative Pydantic model and checked against same-run references before insertion. Do not add a generalized entity/graph subsystem. `research_news_theses` stores the agent's historical research assessment, not a mutable portfolio thesis.

### 6.6 Persistence requirements

- Research imports are atomic, immutable, idempotent, and content-addressed using the existing research hash design, extended to news collection names and stable IDs.
- Sorting JSON objects or source arrays differently does not change a run ID. Rewording a material fact or adding new corroborating evidence produces a distinct immutable run, though it need not produce a *material event delta*.
- The store must never update `positions`, `lots`, `accounts`, `securities`, `market_data_cache`, `targets`, `plans`, or planning baselines.
- List and context queries select compact relational projections; they must not deserialize unrelated large `package_json` payloads. Show retrieves one complete run.
- Source and event references are run-scoped. A source or catalyst from another run cannot be linked by accident.
- Existing V2.6 political and earnings research remains intact on a fresh schema-6 ledger.

---

## 7. Deterministic Change Detection — Primary Feature

### 7.1 Explicit comparison and convenient latest comparison

Provide two modes:

```sh
invest research news compare RUN_OLD RUN_NEW
invest research news changes --ticker TICKER
```

`compare` compares **exactly** the two immutable specified runs, regardless of import order, and labels which is old/new. `changes --ticker` selects the two most recent compatible accepted runs of that company, ordered deterministically by `researched_as_of`, then `imported_at`, then ID. Return a structured missing-baseline result if fewer than two exist; never invent a previous baseline.

Comparisons require the same company, relying on nonconflicting CIK and canonical `security_id` where present, or conservative ticker + verified name matching when both strong identifiers are unavailable. Refuse contradictory identifiers. State each run's monitoring window and coverage. Flag gaps, incomplete or nonoverlapping searches, and incompatible thesis identities.

### 7.2 Change categories

The result must contain structured arrays and counts for:

| Category | Rule |
| --- | --- |
| `new_events` | Event key appears only in the newer run; label **newly observed**, not necessarily newly occurred |
| `updated_events` | Same key; verified facts, status, date, segments, or implications materially changed |
| `new_evidence_only` | Same event and material facts, with new source/corroboration links only |
| `catalyst_changes` | Same catalyst ID, but date/status/qualifiers changed, or new catalyst added |
| `thesis_changes` | Same thesis ID and statement, but research assessment or rationale changed; include source-linked events |
| `follow_up_changes` | Open, answered, or closed questions changed; do not equate editorial rewording with business change |
| `not_reobserved` | Event, catalyst, or thesis present previously but absent from the later snapshot; **never** infer resolved, cancelled, retracted, disproven, or completed |
| `warnings` | Missing coverage, identity conflicts, uncertainty, disputed facts, inconsistent windows or insufficient evidence |

A lifecycle transition to `RESOLVED`, `RETRACTED`, `OCCURRED`, or `CANCELLED` requires an **explicit, source-backed status** in the newer run. Absence is not a transition. Same title with different keys does not imply equality; surface possible ambiguous duplicates for human review rather than silently coalescing them.

Do not compare free-form article summaries or LLM-generated sentiment to create a change score. Use stable IDs and normalized structured facts. Differences caused only by ordering, whitespace normalization, formatting, or title edits do not count as material events.

### 7.3 Materiality and thesis limits

No artificial market-impact score or price prediction. `updated_events` may be further subtyped `FACT_ADDED`, `FACT_REVISED`, `STATUS_CHANGED`, `DATE_CHANGED`, `SEGMENT_CHANGED`, or `IMPLICATION_CHANGED`, with before/after facts. These describe changes **in recorded evidence**, not a claim that the company's intrinsic value changed.

A thesis change records `old_assessment`, `new_assessment`, the unchanged hypothesis statement, relevant event keys, supporting source IDs, and uncertainty. A missing or rephrased hypothesis is `NOT_REASSESSED` or `INCOMPATIBLE`, not automatic thesis rejection. Do not modify a human's portfolio target or create a trade proposal.

### 7.4 Example delta output (fictional)

```json
{
  "company": "Fictional Technology Corporation",
  "from_run_id": "RUN_OLD",
  "to_run_id": "RUN_NEW",
  "coverage_comparable": false,
  "new_events": [],
  "updated_events": [
    {
      "event_key": "fictional-product-announcement",
      "change_types": ["FACT_ADDED"],
      "added_facts": ["Commercial availability was confirmed."],
      "source_ids": ["s-new-release"]
    }
  ],
  "new_evidence_only": [],
  "catalyst_changes": [
    {
      "catalyst_id": "fictional-product-release",
      "old_status": "EXPECTED",
      "new_status": "DELAYED",
      "old_date": null,
      "new_date": null,
      "source_ids": ["s-new-release"]
    }
  ],
  "thesis_changes": [
    {
      "thesis_id": "enterprise-demand",
      "old_assessment": "INSUFFICIENT_EVIDENCE",
      "new_assessment": "MIXED",
      "related_event_keys": ["fictional-product-announcement"]
    }
  ],
  "follow_up_changes": [],
  "not_reobserved": [],
  "warnings": [
    "Monitoring windows differ; missing stories cannot be considered resolved."
  ]
}
```

The precise contract is authoritative in source code; examples must remain visibly synthetic.

### 7.5 Prior-run context for the agent

Add:

```sh
invest research news context --ticker TICKER
```

Return one compact machine-readable baseline: latest run ID, coverage window, unresolved event keys and statuses, pending catalysts, currently tracked thesis IDs/statements, and open follow-up questions. Never load entire historical research packages for this routine query. If no saved run exists, return an explicit `baseline_available: false` with an empty context. The skill must instruct the agent to revisit this prior context while searching new sources.

---

## 8. CLI Commands and Discovery

```sh
invest research news validate FILE
invest research news import FILE
invest research news import FILE --yes
invest research news list [--ticker TICKER]
invest research news show RUN_ID
invest research news summary RUN_ID
invest research news context --ticker TICKER
invest research news compare RUN_OLD RUN_NEW
invest research news changes --ticker TICKER
```

- `validate`: Check input shape, source references, identities, dates, facts, status evidence, and limitations; **read-only**, never create a persistent ledger.
- `import` without `--yes`: Return compact preview, content hash, counts and warnings. Never write.
- `import --yes`: Explicitly accept an immutable run in one transaction. Repeat identical imports as no-ops.
- `list`: Compact run metadata including company, researched date, coverage, counts; optionally filter by ticker.
- `show`: One complete saved package, source links, and trusted skill identity.
- `summary`: Concise event timeline, current catalysts, thesis assessments, unresolved follow-ups, and known coverage limitations. Do not present disputed statements as verified facts.
- `context`: Focused input for a follow-on research agent, with no unrelated company data.
- `compare` / `changes`: Deterministic JSON deltas as defined in §7.

All successful output is structured JSON; errors remain structured stderr with existing exit codes. Extend `invest schema`, `invest tools list`, and `invest tools describe research.news.import` with the actual Pydantic input contract and mutation scope `research`. Read-only operations must not modify files or database state, and must not initialize a new on-disk database when none exists.

---

## 9. Example End-to-End Agent Workflow

```sh
# Existing Docker-only workflow; install skills project-locally.
docker compose build
docker compose run --rm -T app invest research skills list
docker compose run --rm -T app invest research skills install --agent codex --workspace /app

# Optional baseline for a follow-on research pass.
docker compose run --rm -T app invest research news context --ticker EXAMPLE
```

Ask Codex or Claude Code:

> Use the `investobot-news` skill to research material developments concerning Example Corporation between October 1 and October 10, 2026. Read the previously saved news-research context, revisit open catalysts and hypotheses, verify primary sources, preserve stable event IDs, and produce the authoritative JSON contract. Do not write to the Investobot database until I approve the preview.

Then:

```sh
docker compose run --rm -T app invest research news validate /app/local-data/news.json
docker compose run --rm -T app invest research news import /app/local-data/news.json
# After human review:
docker compose run --rm -T app invest research news import /app/local-data/news.json --yes

docker compose run --rm -T app invest research news list --ticker EXAMPLE
docker compose run --rm -T app invest research news summary RUN_ID
docker compose run --rm -T app invest research news changes --ticker EXAMPLE
# Or select the exact baseline and latest run:
docker compose run --rm -T app invest research news compare RUN_OLD RUN_NEW
```

The example is an instruction template, not a claim that these commands already exist in V2.6.

---

## 10. Mandatory BDD — Red → Green → Refactor

Every package requires a failing BDD test for the intended behavior before implementing the corresponding code. Synthetic companies, fake URLs, and fictional evidence only; no external browsing or credentials during tests.

### Skill discovery and source handling

```gherkin
Feature: Portable news research skill
  Scenario: Install a source-backed company news skill
    Given Investobot's bundled research skills
    When the skills are installed for Codex or Claude Code
    Then investobot-news has valid SKILL.md metadata and referenced guidance
    And the existing political and earnings skills remain unchanged
    And project-local installation does not overwrite modified user files

  Scenario: Reject credential-bearing unsafe source references
    Given a fictional news source with a credential and a public record locator
    When source normalization occurs
    Then the credential is removed or the input is rejected
    And the public evidence locator remains verifiable when safe
```

### Research storage and identity

```gherkin
Feature: Immutable news research
  Scenario: Import a verified source-backed event
    Given a synthetic news package with valid company, source, event and fact IDs
    When the package is previewed
    Then the ledger is not changed
    When the package is explicitly accepted
    Then the event and its facts are persisted atomically
    And an identical repeated import creates no duplicate run

  Scenario: Reject an unrelated security association
    Given a registered security for a different company
    When news research refers to that security ID with conflicting identity
    Then validation or import fails
    And no research is saved
```

### Change detection

```gherkin
Feature: News changes since the previous run
  Scenario: Repeated reporting does not create a new event
    Given a prior saved event with a stable event key
    And a later research run citing another article about the same facts
    When the two runs are compared
    Then the event is not classified as new or materially updated
    And newly corroborating evidence is identified separately

  Scenario: New verified facts update an existing story
    Given the same stable event key in two immutable runs
    And the later run contains a newly verified source-backed fact
    When the runs are compared
    Then the event is reported under updated_events with FACT_ADDED
    And the earlier facts remain unchanged in the original run

  Scenario: Missing coverage is not a resolved event
    Given a prior run with an ongoing lawsuit event
    And a later partial run that does not mention it
    When changes are calculated
    Then the lawsuit is listed as not_reobserved
    And it is not marked resolved, dismissed or disproven

  Scenario: A catalyst changes date and status
    Given an expected product event with a stable catalyst ID
    And a later sourced disclosure explicitly postpones it
    When changes are calculated
    Then the old and new status and dates are returned
    And supporting source references are included

  Scenario: Reassessment of a thesis is visible but not actionable
    Given a tracked thesis statement and its prior assessment
    And a later assessment based on new events
    When changes are calculated
    Then the old and new assessments and evidence are shown
    And neither portfolio targets nor saved plans are modified

  Scenario: Cosmetic JSON changes are not material developments
    Given two runs with identical event facts and lifecycle
    And their arrays, source order or article title formatting differ
    When changes are calculated
    Then no material event update is reported
```

### Research boundaries

```gherkin
Feature: Conservative research reporting
  Scenario: Conflicting claims cannot become confirmed facts
    Given contradictory fictional reporting with no resolving evidence
    When news input is validated and summarized
    Then the conflict remains disputed or unresolved
    And no unverified fact is presented as confirmed

  Scenario: Research import does not invalidate a financial plan
    Given accepted holdings and a saved portfolio plan
    When an immutable news run is imported
    Then financial planning inputs and saved-plan stale status are unchanged
    And the new research is retrievable independently
```

### Additional regression tests

- Missing/duplicate event keys, catalyst IDs, fact keys, source IDs and thesis IDs.
- Same title with different source event identities; same event from multiple outlets.
- Invalid dates, future catalysts, null dates with wrong certainty, source publication/retrieval order.
- Multiple companies with similar names, ticker changes and contradictory CIK/security IDs.
- Source-to-event/fact/catalyst cross-run foreign-key attempts and atomic rollback.
- Absent, conflicting, unreviewed, amended and retracted evidence.
- Stable follow-up-question identity, duplicate question keys and explicit closure.
- Statement changed under an existing thesis ID: incompatible, not silently equivalent.
- Initial run with no baseline; multiple runs with equal `researched_as_of`; deterministic latest ordering.
- Nonoverlapping windows, partial coverage and zero events (not proof of no news).
- Reference-safe and secret-safe URL normalization.
- Canonicalized content hashes independent of JSON ordering.
- Summary/list/context bounded outputs and SQL traces proving no `package_json` scans.
- Existing political/earnings skill installation and research commands after schema-6 initialization.
- JSON schema discovery and stderr error semantics.
- All tests offline inside Docker; Ruff clean; GitHub Actions green on the final pushed commit.

---

## 11. Implementation Packages

| Package | Deliverable | Tests before code |
| --- | --- | --- |
| 1 — Contract & skill | New `investobot-news` skill, Pydantic input models, trusted registry metadata, source safety | Agent discovery, JSON validation, identity/evidence failures |
| 2 — Schema & import | Fresh schema 6, shared source publication metadata, news relational tables, atomic preview/confirmed imports | Immutable import, referential integrity, idempotence, rollback, no portfolio mutation |
| 3 — Read paths & baseline | List/show/summary/context with compact SQL projections and source provenance | CLI discovery, correct baseline state, no full JSON loading |
| 4 — Deterministic deltas | Explicit run comparison plus latest-two shortcut, stable-key matching and conservative classifications | New/repeat/updated stories, catalysts, thesis assessments, missing coverage, ambiguity |
| 5 — Documentation & release | Full skill workflow, JSON examples, schema/reset docs, agent usage, CI evidence | End-to-end fictional three-run test and all existing regression tests |

Follow **Red → Green → Refactor** in each package; record separate meaningful commits. Prefer minimal domain modules: `news_models.py`, `news.py`, `news_queries.py`, and a small news-specific canonicalization helper. Reuse existing research infrastructure rather than creating an unrelated command registry or new persistent generic framework.

---

## 12. Documentation

Add `docs/PRD-v2.7.md` and `docs/news-research.md`. Update `README.md`, `AGENTS.md`, `docs/research-skills.md`, `docs/data-model.md`, `docs/development.md`, and `docs/agent-usage.md`.

Documentation must explain:

- Agent Skill versus deterministic research CLI command.
- Initial research baseline versus follow-on incremental research.
- Stable event, catalyst, question and thesis identities.
- Actual event date versus source publication/access dates.
- Verified facts versus allegations, interpretations and business implications.
- Why added sources and renamed headlines are not material developments.
- Why absent events are **not** automatically closed or resolved.
- Exact CLI validation, preview, confirmation, context, changes and compare commands.
- Immutable history, schema-6 deliberate reset, and research isolation.
- Source permissions and copyright limits; no copied full articles.
- Synthetic CI evidence versus manually verified live research.

Do not overwrite historical V2.5/V2.6 PRDs or claim real-news accuracy from synthetic tests.

## 13. Out of Scope and Future Work

V2.7 does not provide scheduled news checks, notifications, automated issuer news fetching, market reaction measurements, earnings prediction, proprietary news feeds, automated sentiment, or live financial forecasts. A future version may implement explicit scheduling or source adapters only after the manual agent-driven research process demonstrates real value and repeatable source quality.

## 14. Final Definition of Done

V2.7 is complete when:

1. `investobot-news` installs and works as a portable Codex/Claude Code Agent Skill.
2. The agent can follow a precise primary-source-first research procedure.
3. `NewsResearchInput` is authoritative, strict, and discoverable from the CLI.
4. Source-backed events preserve title, category, date, source, segment, facts, implications, uncertainty and questions.
5. Catalyst timelines and research thesis assessments have stable IDs and explicit evidence.
6. Schema-6 fresh initialization is safe; old databases require deliberate reset, never deletion at startup.
7. Research imports are previewed, explicitly confirmed, immutable, atomic and idempotent.
8. `context` gives the agent a compact prior-run baseline.
9. `compare` and `changes` show **what changed** without conflating repeated articles, missing coverage, editorial changes and verified real-world updates.
10. All changes include before/after identifiers and verifiable source links; disputed and missing evidence remain visible.
11. No research operation alters financial holdings, plans, market caches, classifications or trading behavior.
12. Political and earnings research functionality and installed skills remain intact.
13. Complete synthetic BDD, unit and integration tests pass offline; Ruff passes; final GitHub Actions CI is green.
14. Documentation and the skill examples are accurate and directly usable by a coding agent.

**Guiding principle:** *An agent identifies and investigates developments. Investobot preserves source-backed observations and deterministically reports what changed. A human interprets the investment significance.*
