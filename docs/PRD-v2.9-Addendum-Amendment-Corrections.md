# Investobot — V2.9 Addendum: Corrected Insider Ownership & Transaction Amendments

**Addendum to:** `docs/PRD-v2.9.md` — Management, Compensation & Insider Activity Research  
**Dependency (must be complete):** V2.9 at commit `d6eb5e5` (October 10, 2026), including `investobot-management-insiders`, `InsiderResearchInput`, SEC Forms 3/4/5 ingestion and immutable schema-8 research.  
**Priority:** P1 ownership reporting correctness; P2 transaction correction flexibility  
**Development rule:** **Write and execute the entire new behavioral BDD suite RED before implementing production code**, then GREEN, then REFACTOR.  
**Scope:** One focused hardening addendum, not a new feature or research framework.

## 1. Purpose and release decision

Fix two observed weaknesses without changing the agent/browser boundary, the meaning of insider activity, or unrelated skills:

1. **Ownership corrections:** A Form 4/A or 5/A may correct a previously filed ownership balance **without changing the `as_of_date`**. The existing `ownership()` output selects every observation having the latest date, so both original and corrected balances can appear current. Preserve all filings historically but return **only an unambiguously supported effective latest observation** per holding identity.
2. **Transaction corrections:** A Form 4/A or 5/A may correct the **transaction date or SEC transaction code**, not just price or quantity. Existing validation prohibits this because corrected and original rows must match on both fields. Allow explicitly documented changes while retaining rigorous identity and anti-double-counting safeguards.

**Invariant:** An amended filing does not by itself establish that an earlier row was corrected. Link a specific original row to a specific amended row using accession numbers, reporting owner identity, instrument identity, and a verifiable amendment locator. Matching figures, dates or headlines alone are not evidence of a correction. Never reconstruct current holdings by adding transactions to disclosed ownership balances.

## 2. Contract and schema decisions (KISS)

Use **two optional structured linkage fields on ownership observations**, matching the established transaction pattern:

```json
{
  "id": "amended-holding",
  "person_id": "executive-1",
  "source_id": "form-4-amendment",
  "source_row_id": "non-derivative-holdings-1",
  "as_of_date": "2026-05-02",
  "table_type": "NON_DERIVATIVE",
  "security_title": "Common Stock",
  "reported_quantity": "120",
  "ownership_form": "DIRECT",
  "indirect_ownership_nature": null,
  "supersedes_id": "original-holding",
  "duplicate_of_id": null,
  "correction_source_locator": "Form 4/A explanatory note identifying corrected shares held",
  "notes": "Corrects 125 to 120 shares; fictional example."
}
```

Add `correction_source_locator: string | null` to **transaction** records too. It is required for any correction that changes `transaction_date` or `transaction_code`, and must point to an explicit explanatory note, footnote, correction disclosure, or amended table cell. If the changed field is unsupported by the filing, mark the proposed correction unresolved and **exclude it from effective aggregated activity**. It is not sufficient for an agent to assert that two rows describe the same trade.

### Versioning

- **SQLite schema 9** on newly initialized databases, adding `supersedes_id`, `duplicate_of_id` and `correction_source_locator` columns to `research_insider_ownership` and `correction_source_locator` to `research_insider_transactions`. Use same-run deferred foreign keys for ownership links as in the transaction table; preserve all existing columns. Add a `CHECK` disallowing both ownership link kinds on one row.
- **Insider input contract `1.1`** and trusted skill version **`1.1.0`**. Older `1.0` JSON files must be explicitly updated for a new import; no implicit rewriting of accepted historical research. The JSON schema shown by `invest schema` / `invest tools describe` must be authoritative. Update only this skill's version. Do not alter earlier research skill versions/hashes.
- No silent migration or deletion of a schema-8 private ledger. Reuse the project's **fresh-schema development policy**: reject incompatible nonempty databases with deliberate backup/reset instructions and test on disposable schema-9 ledgers. Research is immutable, so any corrected evidence forms a new accepted research run.
- No new table or generalized correction engine. Implement link validation in `insider_models.py`, inserts in `insiders.py`, and effective projection in `insider_queries.py`. Maintain the existing CLI paths.

For older JSON properties added here, default optional fields to `null` at model level; this limits fixture and agent changes, although schema version `1.1` is still required. Normalize the new fields into the content hash; reorderings of source/row arrays remain idempotent.

## 3. P1 — Effective ownership observations

### 3.1 Link validation

An ownership `supersedes_id` must resolve to an existing ownership row **in the same research run**, and:

- The referenced original and correction are for the **same reporting owner CIK/person, issuer CIK, security title, derivative/non-derivative table, ownership form, and indirect ownership nature**. Changing any of these identities is **not** silently corrected; flag for human review outside automatic effective holdings.
- The correcting source is an amended **Form 3/A, 4/A or 5/A** of the same base form as the original; its `original_accession_number` points to the exact accession of the original row's source. Both sources' issuer and reporting-owner CIKs are verified. The amended filing must not predate its original.
- Corrected `reported_quantity` may differ. Corrected `as_of_date` may differ **only if** `correction_source_locator` specifically identifies the date correction in the amendment. Changes in quantity also require a specific amendment locator. Keep both as-filed values and dates visible; do not rewrite the original record.
- Each ownership row may be superseded at most once. Linear subsequent amendments may reference the immediately preceding amended row with its accession; reject branching, cycles, self-links, links to duplicates, or links to an unresolved correction.
- `duplicate_of_id` denotes a *verified repeat of the same disclosed holding*, not an amendment. The linked owner, instrument identity, as-of date, and quantity must agree. Never infer duplicates solely from equal share balances. A duplicate cannot itself be superseded.
- When an amended holding appears **without a verifiable original-row link**, retain it in `observations` with `UNRESOLVED` status and a warning; **do not select it as the effective latest** or assert a corrected balance. For the smallest change, derive unresolved status from missing link on an amended source; no new persisted status column is required.

### 3.2 Read model and selection

Keep `invest research insiders ownership RUN_ID [--person PERSON_ID]` and existing `observations[]`, `latest_observations[]`, and source references. Add to each ownership observation:

```text
supersedes_id, duplicate_of_id, correction_source_locator
status: EFFECTIVE | SUPERSEDED | DUPLICATE | UNRESOLVED
is_effective: boolean
exclusion_reason: null | SUPERSEDED | DUPLICATE | UNRESOLVED
```

**Selection procedure:**

1. Determine superseded records using verified same-run `supersedes_id` links. Exclude those originals from effective candidates. Exclude explicit duplicates and unresolved amendment rows. Preserve every row in `observations[]` with its original filing and exclusion reason.
2. Group remaining candidates using the existing exact holding identity fields: `person_id`, `security_title`, `table_type`, `ownership_form`, `indirect_ownership_nature`. For each group, select only observations with the maximum **effective `as_of_date`**, not latest filing date or import date.
3. If one candidate remains for a group, include it in `latest_observations[]`.
4. If multiple nonlinked observations with the same latest effective date assert **different quantities**, do not choose arbitrarily or add the quantities. Leave that group out of `latest_observations[]`; return its rows under a new **`conflicting_latest_observations[]`** list and emit an explicit uncertainty warning with source IDs. If quantities agree but no trustworthy duplicate linkage exists, likewise do **not** silently deduplicate: report ambiguous contemporaneous observations and request review.
5. Ownership observations from earlier runs are **not** joined or implicitly superseded here; `ownership RUN_ID` reports one immutable snapshot. Cross-run ownership consolidation is out of scope.

**Example (fictional):** Original Form 4 says 125 common shares on May 2; 4/A explicitly corrects that same row to 120, still May 2. `observations[]` contains **both**, original `SUPERSEDED`, amended `EFFECTIVE`; `latest_observations[]` contains **120 only**, not 125 + 120 or two equally current rows. An unsupported same-day 120-versus-125 discrepancy appears in `conflicting_latest_observations[]`, never an invented answer.

## 4. P2 — Corrections to transaction dates or codes

Relax **only** the link validator's requirement for identical `transaction_date` and `transaction_code`. Other economic identity checks remain unchanged and mandatory:

- Same verified reporting owner and issuer CIK, same derivative/non-derivative table, same security title/instrument, same direct/indirect ownership form and nature, and same `acquired_disposed` (`A`/`D`). If a filing instead corrects one of these identity-defining fields, mark the row unresolved and require manual investigation; do not merge it automatically.
- The correcting source must be a genuine matching Form 4/A or 5/A, its `original_accession_number` must match the target source accession, and the amended filing's date must not precede the original.
- When **date or code changes**, require a nonempty `correction_source_locator` referring to an amendment note or clearly identified corrected field. `notes` alone cannot serve as this locator. Structural validation cannot verify the text of a real filing, so the skill and documentation must instruct agents/humans to confirm the original disclosure manually.
- Keep the existing **single-target**, no-branching, no-cycle, no-duplicate-target, no-cross-run, no-wrong-form and transaction identity checks. Do not automatically link two similarly sized trades; the agent must explicitly provide the supported `supersedes_id`.
- An amended transaction with an unresolved identity, ambiguous correction, or absent date/code evidence must remain `UNRESOLVED` and **excluded from effective aggregation**. If a purported correction cannot be safely linked, retain its original row as filed and flag the ambiguity rather than deleting evidence or doubling counts.
- The original superseded row remains visible with `SUPERSEDED`; the verified amended row becomes effective. Transaction group classification must use the **amended** transaction code. The amendment's corrected date drives group/report ordering; preserve old/new dates, codes, quantities and both filing citations.

**Example (fictional):** Original Form 4 states `2026-05-02`, code `M`, quantity `200`; Form 4/A explicitly corrects the row to `2026-05-03`, code `P`, quantity `200`, with the same verified issuer, owner, security, direction and table. The original `M` row is `SUPERSEDED`; only the supported amended `P` row is effective, and `P` remains **purchase venue `UNKNOWN`** unless an explicit source establishes open-market/private venue. Do not infer insider intent or market purchases solely from the corrected code.

## 5. Unchanged safety boundaries

- Preserve original filing accessions, original versus amended URLs, exact SEC codes, A/D direction, derivative table, share counts, reported price, 10b5-1 status and source locators.
- Keep `P` separate from confirmed open-market acquisitions; `M` option exercise, `A` grant, `F` withholding and `G` gift remain distinct categories. A corrected code must pass the same code/venue validation as any original row.
- Preserve reported compensation grant-date fair value versus cash amounts, roles/tenure, reporting-owner CIK verification, and source-policy restrictions.
- No external SEC client or embedded agent. No changes to prices, household holdings, lots, allocations, accepted classifications, planning inputs or stale-plan status.
- `validate` and preview are read-only and must not create a persistent database. Acceptance must remain explicit, atomic, immutable, idempotent and provenance-preserving.
- Existing earnings/news/competitive/political skills, contracts, saved research semantics and tests must continue to work in a newly initialized schema-9 database.

## 6. BDD: all new cases RED before production changes

Create and bind all new scenarios under the existing insider BDD tests, use fictional SEC-like accessions and synthetic sources, then run the new tests **before modifying production code**. Record and commit the failing suite; failures must represent missing behavior, not import/syntax/fixture errors. Implement and make each one GREEN, refactoring only with green tests. Gherkin describes user-observable behavior, not internal implementation.

```gherkin
Feature: Corrected insider ownership disclosures

  Scenario: An amended holding replaces the originally reported balance
    Given a Form 4 discloses 125 directly held common shares on May 2
    And its cited Form 4/A corrects the same holding to 120 shares on May 2
    When the insider ownership report is requested
    Then the original 125 and corrected 120 observations remain inspectable
    And only 120 shares appear as the effective latest reported balance

  Scenario: Contradictory same-day holdings remain unresolved
    Given two sourced but unlinked ownership observations for the same holding and date
    And one reports 125 shares while the other reports 120 shares
    When insider ownership is summarized
    Then neither amount is selected as a uniquely current balance
    And both filings appear as conflicting latest observations

  Scenario: Unsupported amendment cannot quietly replace ownership
    Given a Form 4/A reports a new balance without a verifiable original-row link
    When the insider ownership report is requested
    Then the amended balance is marked unresolved
    And it is not presented as the effective latest balance

Feature: Corrected insider transaction identities

  Scenario: A filing correction changes a transaction date and code
    Given a Form 4 reports an option exercise on May 2
    And a properly linked Form 4/A cites a correction to a purchase on May 3
    When insider activity is summarized
    Then the original option exercise is excluded as superseded
    And the corrected purchase is counted once under May 3
    And its purchase venue remains unknown without explicit venue evidence

  Scenario: An unsupported date or code correction is not counted twice
    Given a purported amendment changes a transaction code
    But its supporting filing does not identify a verifiable correction
    When research is validated or accepted
    Then the claim cannot become a verified corrected transaction
    And the report cannot double-count the original and purported correction

  Scenario: An amended row cannot correct an unrelated insider's trade
    Given a Form 4/A cites a different reporting owner or unrelated filing accession
    When the correction is validated
    Then the correction is rejected without saving partial research
```

**Additional focused regressions:** Form 3/A, 4/A and 5/A ownership links; same and changed `as_of_date`; identical and conflicting reported balances; duplicate and unresolved ownership; second amendment in a linear chain; branched/cyclic/cross-run or wrong-form links; corrected transactions with changed date only, code only, both, and changed A/D direction (reject); missing evidence locator; proper source/owner CIK association; corrected quantity/price with unchanged date/code still accepted; `P` venue unknown; activity/category totals exclude superseded/duplicate/unresolved rows; Decimal serialization and idempotence across array reorderings; read-only query SQL avoids `package_json`; atomic rollback; no portfolio mutation; schema-8 incompatibility leaves files untouched; all prior research regression suites.

## 7. Non-overlapping implementation packages

**Order is mandatory:** first commit all scenarios in their intended **RED** state; then proceed through the following bounded packages.

| Package | Owns | Required outcome |
|---|---|---|
| **1 — Contract & skill** | `src/invest/insider_models.py`, `skills/investobot-management-insiders/**`, trusted `research_skills.py` metadata | Optional correction-link fields, same-run evidence checks, allowed transaction date/code amendments, skill/schema 1.1, documented provenance rules. No SQL query changes. |
| **2 — Persistence** | `src/invest/insiders.py`, `src/invest/ledger.py`, existing installer/schema registration as needed | Fresh schema-9 columns and FKs; new values persisted atomically; corrected packages hash deterministically; historical runs untouched. No output grouping logic. |
| **3 — Reports** | `src/invest/insider_queries.py` | Correct effective ownership selection, explicit conflicts and original provenance, and corrected transaction aggregation without duplicates. Preserve CLI signatures. |
| **4 — Integration & docs** | Existing insider tests/fixtures and `docs/insider-research.md`, `docs/data-model.md`, `docs/development.md`, `docs/research-skills.md`, `README.md`, `AGENTS.md` | Complete end-to-end A → amended A review, document schema reset and JSON 1.1, all BDD/regression tests GREEN; Docker offline tests, Ruff and GitHub Actions green. |

Do **not** introduce a new correction-service abstraction, generic filing graph, new research database, historical portfolio adjustment, automatic SEC downloader, or a management-scoring/trading feature. Prefer the fewest pure validation/query helpers necessary to keep the existing modules readable.

## 8. Final definition of done

1. Both ownership observations are retained but a verified corrected balance is the **only** effective latest balance for its exact holding identity.
2. Same-date contradictions without explicit linkage are surfaced as **uncertain**, not silently selected, summed or interpreted as a position.
3. A documented transaction amendment can correct **date or code**, with original row excluded, amended code/date effective, and both filing citations retained.
4. Incorrect issuer/owner identities, accession links, amendment forms, branches, cycles and unsupported changes are rejected or explicitly unresolved without double-counting.
5. Insider JSON `1.1`, skill `1.1.0`, and fresh SQLite schema **9** are consistently discoverable; old private ledgers are not automatically modified or deleted.
6. All new BDD tests are demonstrated **RED before any production implementation**, then GREEN; the full offline suite, Ruff, and pushed GitHub Actions pass.
7. All earlier research skills and financial portfolio/planning isolation are preserved.
8. A separate manual real-SEC review verifies one original Form 4 and its available Form 4/A correction, including ownership balances and footnotes. Synthetic tests do not substitute for that evidence review.

**Guiding principle:** *A corrected filing should change which observation is effective, never erase the earlier filing. Uncertain linkage stays uncertain; unsupported changes never become insider buying or a reconstructed portfolio holding.*
