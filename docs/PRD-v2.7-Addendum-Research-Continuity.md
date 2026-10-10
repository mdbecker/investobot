# Investobot — V2.7 Addendum: Research Continuity & Disputed-Claim Deltas

**Addendum to:** `docs/PRD-v2.7.md` — *News, Catalysts & Thesis-Change Research*  
**Baseline:** V2.7 implementation at `aeead0f` (October 10, 2026)  
**Priority:** P1 continuity fix; P2 disputed-claim visibility  
**Methodology:** Strict BDD — Red → Green → Refactor  
**Architecture:** Existing `investobot-news` Agent Skill + Pydantic + SQLite + Typer  
**Database:** Preserve schema version **6** unless a demonstrably necessary constraint/index cannot be added otherwise

## 1. Purpose

Address two follow-up findings from the V2.7 review without expanding the architecture or changing the original research contract unnecessarily:

1. **P1 — Preserve historical research continuity.** An unresolved event, pending catalyst, open question, or tracked thesis must not vanish from the context supplied to a subsequent agent simply because an intervening run did not observe it.
2. **P2 — Surface disputed-claim changes explicitly.** Newly disputed, revised, and reclassified claims must be visible in deterministic change output, without treating those allegations as verified facts or material business outcomes.

The feature's primary output remains **what changed since the previous research run**, with an auditable distinction between real new developments, previously known developments, missing coverage, and changes to evidence.

**Unchanged principle:** The agent researches; Investobot stores verified structure and calculates deltas; humans judge investment significance. No embedded AI, background monitoring, news sentiment scoring, or trading automation.

---

## 2. P1 — Historical Continuity Across More Than Two Runs

### 2.1 Current behavior and problem

`src/invest/news_queries.py::context()` currently projects records from only the latest accepted run. `compare()` compares the two selected snapshots.

Example:

- **Run A:** A company faces an ongoing lawsuit; the event key is `issuer-litigation-123`.
- **Run B:** A partial search omits the lawsuit. A-versus-B correctly reports `NOT_REOBSERVED`.
- **Run C:** Before conducting new research, the agent calls `invest research news context --ticker TICKER`. The latest snapshot contains no lawsuit, so the agent loses its stable key and unresolved questions.
- **Run C result:** Rediscovery risks being mislabeled `NEWLY_OBSERVED` even though the event was already tracked in Run A.

This violates the intended incremental-research workflow.

### 2.2 Required historical-context behavior

Update the existing command, **without renaming it**:

```sh
invest research news context --ticker TICKER
```

Return a compact **effective research context** reconstructed from compatible accepted historical runs, not just the latest run.

Rules:

1. Select the latest accepted run using the existing deterministic order (`researched_as_of`, then `imported_at`, then run ID), and identify that run explicitly as the baseline.
2. Walk earlier **same-company** news runs as necessary to recover previously tracked records. Preserve existing conservative CIK, `security_id`, ticker, and name-matching rules. Never carry records across ambiguous or contradictory issuers.
3. For each stable `event_key`, choose its most recent *actual observation*. Carry forward unresolved events that the latest run omits. Explicitly resolved or retracted events, supported by their own recorded status evidence, need not remain in the active event context; retain their historical records.
4. Similarly carry forward pending catalysts (`EXPECTED`, `SCHEDULED`, `DELAYED`, `UNKNOWN`), unanswered follow-up questions, and tracked theses that have not been explicitly superseded. A missing thesis becomes `NOT_REASSESSED`, not rejected.
5. Mark inherited records as **historical context**, never as facts freshly verified by the latest run.
6. Provide `last_observed_run_id`, `last_observed_as_of`, and `observation_status` (`OBSERVED_IN_BASELINE` or `NOT_REOBSERVED`) for carried records. Continue to include stable IDs and existing status, with compact source provenance as needed for follow-up.
7. Keep `baseline_available`, the latest run metadata, coverage window, limitations, and warnings. An incomplete/empty later run does **not** close anything by silence—even if its search window is declared complete.
8. Preserve records with unknown event dates without inventing an occurrence date. No automatic expiry or silent pruning of unresolved history.
9. `context` must read indexed/projection columns and **must not scan `package_json`**, download source documents, or mutate SQLite.

The context represents the most recent *recorded knowledge*, including its staleness; it is not proof that the event is still ongoing today.

### 2.3 Expected context shape (fictional)

```json
{
  "baseline_available": true,
  "research_run_id": "RUN_B",
  "ticker": "FAKE",
  "events": [
    {
      "event_key": "issuer-litigation-123",
      "title": "Fictional company lawsuit",
      "event_status": "DEVELOPING",
      "observation_status": "NOT_REOBSERVED",
      "last_observed_run_id": "RUN_A",
      "last_observed_as_of": "2026-10-01",
      "source_ids": ["source-court-record"]
    }
  ],
  "catalysts": [],
  "theses": [],
  "open_follow_up_questions": [
    {
      "event_key": "issuer-litigation-123",
      "id": "case-outcome",
      "question": "Has the court issued a final ruling?",
      "status": "OPEN",
      "observation_status": "NOT_REOBSERVED",
      "last_observed_run_id": "RUN_A"
    }
  ],
  "warnings": [
    "Some active context comes from older runs and has not been reverified."
  ]
}
```

The example extends the existing context response; keep established fields and compatibility wherever possible.

### 2.4 Reobserved events must not appear as new discoveries

In addition to the existing `new_events`, `updated_events`, and `not_reobserved` arrays, add **`reobserved_events`** to the delta output and its `counts` object.

For an explicit `compare RUN_OLD RUN_NEW`:

- If an event exists in `RUN_NEW` but not `RUN_OLD`, search **only compatible runs at or before the selected old baseline in chronological research order**. Do not use observations made after the selected baseline; avoid future-information leakage.
- If the stable `event_key` was observed earlier, classify it under `reobserved_events`, **not** `new_events`.
- Include the earlier `last_observed_run_id`, the new run ID, before/after records, and source provenance. Record fact/status differences where applicable; a reappearance can also contain new verified facts. Do not call those updates a newly created event.
- If there is no earlier compatible observation, retain the existing `new_events` behavior, including `PREVIOUSLY_OCCURRING_NEWLY_OBSERVED` where relevant.
- If historical identity is uncertain, preserve separate event keys and an ambiguity warning; never merge based solely on title similarity.
- Preserve the existing `not_reobserved` semantics for records missing from `RUN_NEW`.

For `invest research news changes --ticker TICKER`, use this same historical-aware logic with the automatically selected latest two compatible runs.

**Example: A → B → C**

| Run | Observed event | Required interpretation |
| --- | --- | --- |
| A | `issuer-litigation-123` | Previously tracked event |
| B | Not present; partial coverage | `not_reobserved`, never `RESOLVED` |
| C | Same stable key appears again | `reobserved_events`, not `new_events` |

An identical repeated import must remain idempotent, including for companies without tickers.

---

## 3. P2 — Structured Changes to Disputed Claims

### 3.1 Problem

The current comparison intentionally extracts only `VERIFIED` facts for material event updates. This correctly avoids treating an allegation as a confirmed business development, but it can bury a newly reported disputed claim in a general warning.

A user reviewing litigation, cybersecurity, regulatory investigations, or contested reporting needs a separately labeled record of **what disputed evidence changed**.

### 3.2 New delta field

Add the array **`disputed_claim_changes`** to `compare` / `changes`, with a matching count. This is an additive read-output change; the existing `NewsFact` fields (`fact_key`, `statement`, `source_id`, `source_locator`, `verification_status`) remain authoritative.

Detect, by stable event and fact keys:

- `DISPUTED_ADDED`: Newly recorded disputed claim.
- `DISPUTED_REVISED`: Existing disputed claim's checkable statement has changed materially.
- `DISPUTED_TO_VERIFIED`: A previously disputed proposition is now presented as verified with fresh supporting evidence.
- `VERIFIED_TO_DISPUTED`: A previously verified proposition is now contested or its verification is withdrawn; remove it from confirmed-fact treatment.
- `DISPUTED_NOT_REOBSERVED`: Previously disputed claim absent in the newer snapshot; **not** proof it was false, withdrawn, or resolved.

A change in source-only corroboration for an unchanged disputed claim may be reported as evidence-only rather than a new allegation. Ignore superficial whitespace, ordering, and editorial headline changes.

Each entry must include:

- `event_key`, `fact_key`, `change_type`.
- `before` and `after` fact objects, as applicable.
- `from_run_id` and `to_run_id`.
- Source IDs, source URLs, and locators sufficient to verify the before/after record.
- An explicit caveat that `DISPUTED` is not a verified company fact.

If a claim changes from `DISPUTED` to `VERIFIED`, it may additionally appear as a verified fact update under `updated_events`; avoid implying two distinct real-world developments or double-counting a single claim in headline totals. Conversely, `VERIFIED_TO_DISPUTED` must visibly withdraw verified-fact treatment without asserting the claim is disproven.

### 3.3 Expected delta excerpt (fictional)

```json
{
  "from_run_id": "RUN_A",
  "to_run_id": "RUN_B",
  "new_events": [],
  "reobserved_events": [],
  "updated_events": [],
  "disputed_claim_changes": [
    {
      "event_key": "issuer-litigation-123",
      "fact_key": "damages-allegation",
      "change_type": "DISPUTED_ADDED",
      "before": null,
      "after": {
        "fact_key": "damages-allegation",
        "statement": "A third party alleges damages; the company disputes the claim.",
        "verification_status": "DISPUTED",
        "source_id": "source-filing",
        "source_locator": "Complaint, allegation section"
      },
      "from_run_id": "RUN_A",
      "to_run_id": "RUN_B",
      "sources": [
        {
          "source_id": "source-filing",
          "url": "https://example.invalid/fictional-court-record"
        }
      ],
      "warning": "An allegation is not a verified company fact."
    }
  ],
  "counts": {
    "new_events": 0,
    "reobserved_events": 0,
    "updated_events": 0,
    "disputed_claim_changes": 1
  }
}
```

This is an excerpt: **retain all existing delta arrays and counts** (`new_evidence_only`, `catalyst_changes`, `thesis_changes`, `follow_up_changes`, `not_reobserved`, and `warnings`).

---

## 4. Implementation Boundaries

**Primary files:**

```text
src/invest/news_queries.py
src/invest/news_models.py          # only if required; preserve JSON v1.0 if possible
skills/investobot-news/SKILL.md
skills/investobot-news/references/research-method.md
skills/investobot-news/references/change-review.md
docs/news-research.md
docs/PRD-v2.7.md                     # link to this addendum; do not rewrite history
```

**No new general infrastructure.** Reuse `research_runs`, `research_news_events`, `research_news_facts`, `research_news_catalysts`, and `research_news_theses`, along with their existing indexes and run-scoped source references.

- Keep **SQLite schema 6**, unless a narrowly justified indexed lookup or integrity constraint requires a version bump. Do not reset existing schema-6 research just for these read-side fixes.
- Prefer read-side historical projections and minimal deterministic logic over storing copied forward state in new rows.
- Preserve immutable accepted research runs, content hashes, idempotent imports, and source evidence.
- Preserve existing `invest research news validate`, `import`, `list`, `show`, `summary`, `context`, `compare`, and `changes` CLI signatures.
- New arrays and metadata must be documented as **additive output-contract changes**; update `invest tools describe` / schema discovery where applicable.
- Existing earnings and political research skills and commands must not change behavior.
- No automatic web collection, scheduled monitoring, embedded LLM, sentiment score, investment thesis mutation, or trade planning changes.

**Skill update:** Instruct the agent to treat carried-forward events as historical and explicitly re-check them; reuse earlier stable IDs when rediscovered; never turn an absent event or unsupported allegation into an outcome. Clarify that disputed claims are research leads requiring verification, not facts or trading signals.

---

## 5. Mandatory BDD — Red → Green → Refactor

Use only fictional issuers, claims, sources, and dates. All tests run offline and do not use real market or campaign-finance data.

### Scenario A — Context persists across an omitted run

```gherkin
Feature: Research continuity

Scenario: An unresolved event survives a partial intervening research run
  Given Run A records an unresolved fictional lawsuit with a stable event key
  And Run B is a later partial run that does not observe the lawsuit
  When context is requested for the company before Run C
  Then the lawsuit is included as NOT_REOBSERVED
  And its last observed run is Run A
  And its open follow-up question remains available
  And no resolution is inferred
```

### Scenario B — Reobservation is not discovery

```gherkin
Scenario: A previously tracked event returns after missing coverage
  Given Run A records an ongoing fictional product recall
  And Run B omits it
  And Run C reobserves the same source-grounded event key
  When Run B is compared with Run C
  Then the event appears under reobserved_events
  And not under new_events
  And the prior observation and current source links are included
```

### Scenario C — Explicit resolution stops active carry-forward

```gherkin
Scenario: A sourced resolution remains historical but not active
  Given Run A records an ongoing fictional lawsuit
  And Run B explicitly marks that event RESOLVED with valid outcome evidence
  And Run C does not mention it
  When active research context is requested after Run C
  Then the event is not presented as an unresolved active issue
  And its Run A and Run B history remains retrievable
```

### Scenario D — New disputed allegation is visible, not confirmed

```gherkin
Feature: Disputed claim deltas

Scenario: A newly disputed allegation is reported separately
  Given Run A contains a verified event without an allegation
  And Run B records a new DISPUTED claim under the same event key
  When the two runs are compared
  Then disputed_claim_changes includes DISPUTED_ADDED with source provenance
  And updated_events does not call the allegation a newly verified fact
  And no event-level resolution or investment conclusion is inferred
```

### Scenario E — Dispute state transitions preserve uncertainty

```gherkin
Scenario: A confirmed fact becomes disputed
  Given Run A contains a VERIFIED fictional fact
  And Run B preserves the fact key but changes its status to DISPUTED
  When the runs are compared
  Then disputed_claim_changes includes VERIFIED_TO_DISPUTED
  And the later summary does not list the claim under verified facts
  And the comparison does not state that the claim was disproven
```

### Additional regression tests

- Carry forward pending catalysts, open questions, and unchanged thesis IDs across multiple omitted runs.
- Select latest actual observation per stable key; do not duplicate a record carried through multiple gaps.
- Do not cross company boundaries or accept ambiguous strong identities.
- Out-of-order imported or explicitly selected runs do not leak future observations into an earlier comparison.
- Unknown event dates and mixed monitoring windows preserve uncertainty.
- Reobservation with added verified facts provides old/new evidence and is not categorized as newly discovered.
- Reobserved events absent from Run B do not bypass stable-event identity checks.
- Disputed revisions, dispute-to-verified transitions, missing disputed claims, and corroboration-only updates are classified conservatively.
- Whitespace, input array order, title edits and source-ID relabeling alone do not produce material deltas.
- `counts` includes both new categories and remains internally consistent; missing-baseline output returns empty arrays and zero counts for them.
- SQL traces show `context` does not read `package_json` or full historical articles.
- `context`, `compare`, and `changes` do not mutate the ledger or alter saved-plan freshness.
- Prior earnings and political skill regression tests remain green.

---

## 6. Acceptance and Definition of Done

This V2.7 addendum is complete when:

1. A three-run **A → B → C** omission/reobservation sequence preserves unresolved historical context.
2. Previously tracked events reappearing in C are identified as `reobserved_events`, not fresh discoveries.
3. Pending catalysts, open follow-up questions, and thesis hypotheses do not disappear solely because a later run omitted them.
4. Explicit, source-backed resolutions remain historical but are no longer shown as active unresolved issues.
5. `disputed_claim_changes` exposes added, revised, reclassified and unobserved claims with cited before/after evidence.
6. No disputed claim is promoted to a verified event or a trading signal without a separate verified evidentiary basis.
7. Existing JSON inputs, CLI signatures, immutable runs, source-provenance rules, and schema-6 data remain intact.
8. New failing BDD scenarios are committed before implementation, then all tests pass after Red → Green → Refactor.
9. Ruff passes and the final pushed GitHub Actions workflow is green.
10. Documentation and the `investobot-news` skill explain historical carry-forward and disputed claims clearly.

**Guiding principle:** *Missing observations are not resolutions. Rediscovery is not novelty. Disputed claims are not verified facts. Preserve history, show evidence, and report exactly what changed.*
