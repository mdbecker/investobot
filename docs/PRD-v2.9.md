# Investobot — Management, Compensation & Insider Activity Research

**One MVP Product Requirements Document — V2.9**  
**Repository:** https://github.com/mdbecker/investobot  
**Dependency — complete before this work:** V2.8 (`fbfbe78`) with the competitive skill, immutable research infrastructure, research-only CLI imports, and SQLite schema 7. Preserve the V2.7 news-continuity addendum and all previously installed research skills.  
**Method:** Strict behavior-driven development (**all new BDD tests RED before implementing any feature code**, then GREEN → REFACTOR).  
**Stack:** Existing Python 3.12+, Typer, Pydantic v2, stdlib `sqlite3`, Decimal, Docker/offline pytest-bdd and Ruff.  
**Database policy:** Fresh SQLite **schema 8**. Disposable development databases may be reset deliberately; **never automatically delete or migrate an existing portfolio database**. Do not require a new external service.

## 1. Objective and design decision

Add **`investobot-management-insiders`**, a portable Codex/Claude Code Agent Skill that researches a public company's management, role tenure, reported executive compensation and ownership, and Section 16 insider filings. The agent browses authorized public sources and creates **source-backed, strictly structured JSON**; Investobot validates it, previews/accepts it into immutable research-only SQLite tables, and deterministically summarizes **purchases versus sales versus grants, option exercises, gifts, and tax-withholding transactions** without confusing their economic meanings.

Use SEC **Forms 3, 4, 5 and amendments** as primary sources for U.S. insider ownership and transactions; **DEF 14A** and issuer disclosures as primary sources for compensation arrangements and officer/director roles. Report what filings disclose, not what the agent guesses about insiders' intentions. SEC reporting owners may also be 10% holders rather than company managers: preserve their status and do not call them executives without role evidence.

**No automated filings API, web scraper, continuous monitoring, insider-trading prediction, investment ranking, portfolio action, or brokerage link.** Reuse existing research storage; add only four domain tables and a few CLI read paths. Source content is untrusted; schema validation alone cannot prove a claim's truth.

### User-visible MVP goals

- For one issuer and requested date range, show its identified officers/directors, sourced roles and tenure, and source-backed compensation terms.
- Show each reported Section 16 transaction with original SEC code, filing, transaction date, quantity, price if disclosed, direct/indirect ownership, derivative/non-derivative classification, and applicable 10b5-1 disclosure.
- Distinguish an **acquisition code P** from **exercise code M**, **grant code A**, **sale code S**, **tax withholding code F**, and **gift code G**, preserving unknown/other codes without inventing meaning.
- Show reported beneficial holdings **as observations**, not as cumulative balances reconstructed by summing filings.
- Preserve original filings and documented amendments; never double-count corrected or duplicate lines.
- Allow agents to retrieve prior research without altering holdings, targets, tax lots, trade plans or their stale state.

## 2. Scope, safeguards and source definitions

**Issuer scope:** U.S. SEC-reporting public companies with an identifiable issuer CIK for transaction research. If the CIK cannot be verified, the agent may research leadership/compensation but must omit individually attributed Form 3/4/5 transaction assertions. Require exact canonical security verification when `security_id` is supplied; never auto-register or reclassify a security. One reporting issuer per research run; no cross-company personnel matching.

**People:** Publicly identified officers, directors and Section 16 10% beneficial owners. Keep only publicly disclosed names, role/title, reported-owner CIK where disclosed, date ranges and evidence. No addresses, personal contact information, demographic inferences or personality/ethics scores. A reporting owner is not automatically a current executive, and two people with similar names cannot be merged by name alone. Filing transactions require an independently verified reporting-owner CIK and an exact filing-person association.

**Sources:** SEC originals (forms `3`, `3/A`, `4`, `4/A`, `5`, `5/A`, `DEF 14A`, `8-K`, `10-K`) and documented issuer disclosures. Keep SEC accession, issuer CIK, filing/acceptance date, source URL, source locator and accessed date. Use the existing credential-safe URL normalizer and preserve safe filing identifiers. Record relevant source footnotes as concise original interpretations/references, **not full scraped filing pages**. A filing's availability does not guarantee exhaustive insider coverage.

**Important distinctions:**

- Form 3 is primarily **initial reported ownership**, not evidence of an open-market transaction.
- Form 4 and Form 5 may contain both non-derivative and derivative rows, amendments and footnotes. Preserve the table type and as-filed transaction code; transaction date is distinct from filing date.
- Code `P` denotes **open-market or private purchase**: describe it as *reported purchase* unless an original source explicitly confirms exchange/open-market venue. Code `S` is a reported sale, not proof of discretionary selling; retain whether a disclosed Rule 10b5-1 plan applies, if known.
- `M` exercise/conversion, `A` award/grant, `F` payment of price or tax with securities, and `G` gift are **not** counted as P purchases or S sales. Unrecognized/other codes remain `OTHER` with the original code and uncertainty.
- Direct versus indirect beneficial ownership, different share classes and derivatives must remain separate; derivative option counts are **not** automatically common shares owned.
- Proxy stock/option award values are frequently **grant-date fair values**, not money received, cash compensation, realized gain, or actual exercise proceeds. Keep compensation types and valuation basis explicit; do not sum an already reported total with its components.
- A Form 4 Rule 10b5-1 checkbox reports intended plan coverage; it is **not** proof of insider knowledge, legality, intent or discretionary timing. Missing historical disclosure must stay `NOT_DISCLOSED`.
- An amended filing corrects specified previous disclosure rows. Preserve original and amended evidence, but **never double-count** the replaced economic transaction.

### Authorized-source reference documents (for skill documentation)

- SEC overview of Forms 3/4/5: https://www.sec.gov/about/forms/forms-3-4-5.pdf
- SEC Form 4 and transaction instructions: https://www.sec.gov/about/forms/form4.pdf
- SEC insider transaction datasets and caveats: https://www.sec.gov/data-research/sec-markets-data/insider-transactions-data-sets
- SEC 10b5-1 disclosure amendments: https://www.sec.gov/newsroom/modernizing-rule-10b5-1-insider-trading-plans
- Public SEC filings and issuer DEF 14A proxy materials for compensation.

## 3. Agent Skill

Create and register this canonical package, reusing the existing skill installer and safe project-local copying:

```text
skills/investobot-management-insiders/
  SKILL.md
  references/
    research-method.md
    sec-transaction-codes.md
    compensation-ownership-rules.md
    json-contract.md
```

Minimal metadata:

```yaml
---
name: investobot-management-insiders
description: Research officers, directors, compensation, SEC insider filings, transaction types, and reported beneficial ownership with cited structured JSON for Investobot.
metadata:
  version: "1.0.0"
---
```

Register trusted **per-skill** `skill_version="1.0.0"`, `schema_version="1.0"`, `research_command="research.insiders"` in the existing `SUPPORTED_SKILLS`. Do not change other skills' identities or install behavior. `invest research skills list/show/install` must discover/install the new skill for both Codex and Claude Code without automatically executing it.

### Skill research sequence (mandatory)

1. **Confirm issuer and period.** Verify legal name, ticker, CIK, any linked Investobot `security_id`, start/end dates, and source-access cutoff. Read previous saved research only for context; do not silently conflate distinct runs.
2. **Identify the people.** Compile publicly disclosed current/former officers and directors within scope and applicable 10% reporting owners. Record role type, title, known role start/end, verified reporting-owner CIK, and exact original-source citations. Unknown tenure dates remain null, never assumed.
3. **Find primary filings.** Locate relevant Forms 3/4/5 and `/A` amendments, corresponding XML tables and footnotes, proxy compensation tables/CD&A, and applicable issuer leadership/award agreements. Check each filing's issuer CIK, reporting owner, accession and acceptance dates. Identify filing omissions and reporting lag.
4. **Extract reported transactions precisely.** Read non-derivative and derivative rows. Preserve as-filed codes, acquisition/disposition marker, underlying security type/title, date, shares/units, price if stated, direct/indirect form, and stated nature of indirect ownership. Distinguish exchanges/private purchases when documentary evidence supports that distinction; otherwise `UNKNOWN`.
5. **Reconcile amendments and duplicates.** Identify corrections and duplicate reporting **only with source evidence**. Explicitly link amended rows and repeated economic events to previously recorded rows in the **same research package**. If the source is ambiguous, mark the row unresolved and exclude it from trade totals rather than guessing. Retain both the as-filed and amended records.
6. **Capture reported ownership.** Keep each Form 3 initial or Form 4/5 post-transaction holding as a dated observation with class, table type, direct/indirect status and source. Never add snapshots together or infer share-class conversion or total beneficial ownership from incomplete filings.
7. **Capture compensation.** Use DEF 14A and applicable issuer filings to record each named person's disclosed salary, cash/non-equity incentives, equity award grant-date values, reported summary compensation totals, and material vesting/performance/severance/change-in-control/clawback arrangements where available. Keep the reporting fiscal year, units/value basis, terms and source. Distinguish policy from actual payment.
8. **Review uncertainty.** Note unmatched people, late/missing filings, amended or disputed rows, unknown price, unknown Rule 10b5-1 status, indirect holdings, limited compensation coverage and whether summary figures reflect different reporting periods.
9. **Emit one strict JSON file** matching the authoritative `InsiderResearchInput` Pydantic schema. Save under ignored `local-data/`; validate and preview via the CLI. Obtain explicit human approval before any `--yes` import.
10. **Use deterministic reporting** through `summary`/`activity`/`ownership`; do not make trading recommendations or alter the investment ledger.

The skill's `references/json-contract.md` explains fields but must refer to the **authoritative `invest schema`** output; no independently maintained competing schema.

## 4. Structured JSON contract

Implement `src/invest/insider_models.py` with `InsiderResearchInput` (strict Pydantic v2, `extra="forbid"`, no silent coercion). Reuse existing `Text`, CIK, date, safe-URL, Decimal-string validators where appropriate. Top-level fields:

```text
schema_version: "1.0"
research_type: "MANAGEMENT_INSIDER_ACTIVITY"
company: {name, ticker, cik, security_id?}
scope: {period_start, period_end, researched_as_of, coverage_status, coverage_notes}
sources[]
people[]
compensation[]
transactions[]
ownership[]
limitations[]
```

**Source:** `{id,source_type,publisher,url,cik?,reporting_owner_ciks[],accession_number?,filed_at?,accepted_at?,accessed_at,source_locator,is_amendment,original_accession_number?}`. `cik` identifies the issuer, `reporting_owner_ciks` identifies disclosed filers and is validated against transaction-person links; keep it in the immutable `package_json` and omit it from the `research_sources` SQL insert (no unnecessary shared-source column). `source_type` is a checked enum for SEC/issuer disclosure types above. For Forms 3/4/5, require valid SEC accession, filed date and issuer CIK match; `/A` requires its explicit original accession. Source IDs are unique *within a run*; every cited source must be included. Ensure source timestamps do not exceed `researched_as_of`, except a future event date described as expected in an issuer agreement (not a transaction).

**Person:** `{id,name,reporting_owner_type,reporting_owner_cik?,identity_source_id,roles:[{role_type,title,start_date?,end_date?,source_id}]}`. `role_type` in `OFFICER`, `DIRECTOR`, `TEN_PERCENT_OWNER`. Add `reporting_owner_type` (`INDIVIDUAL` or `ENTITY`) so a 10% entity holder is not represented as a human executive. Role dates may be unknown, and end cannot precede start. At least one cited role. Transactions require a reporting-owner CIK. Duplicate known owner CIKs or contradictory person identifications are rejected.

**Compensation:** `{id,person_id,fiscal_year?,compensation_type,value?,currency?,value_basis,terms,source_id,source_locator}`. Types: `SALARY`, `BONUS`, `NON_EQUITY_INCENTIVE`, `STOCK_AWARD`, `OPTION_AWARD`, `OTHER_COMPENSATION`, `SUMMARY_COMPENSATION_TOTAL`, `VESTING_TERMS`, `PERFORMANCE_CONDITIONS`, `SEVERANCE`, `CHANGE_IN_CONTROL`, `CLAWBACK`, `OTHER`. Basis: `REPORTED_ANNUAL_AMOUNT`, `GRANT_DATE_FAIR_VALUE`, `UNQUANTIFIED_TERMS`. Numeric values are plain Decimal strings, nonnegative, with explicit currency; terms-only items require null value/currency and explanatory terms. Grant-date value basis required for stock/option award values. An item `SUMMARY_COMPENSATION_TOTAL` must not be added to its underlying components in summaries.

**Transaction:** `{id,person_id,source_id,source_row_id,transaction_date,table_type,security_title,transaction_code,acquired_disposed,quantity,price_per_unit?,price_currency?,ownership_form,indirect_ownership_nature?,purchase_venue,purchase_venue_locator?,rule_10b5_1_status,review_status,supersedes_id?,duplicate_of_id?,notes}`. Values:

- `table_type`: `NON_DERIVATIVE` or `DERIVATIVE`; distinct instrument titles remain distinct.
- `transaction_code`: preserve the original SEC code in a validated short uppercase format. Derive `transaction_category` in Investobot: `P → PURCHASE`, `S → SALE`, `M → OPTION_EXERCISE_OR_CONVERSION`, `A → AWARD_OR_GRANT`, `F → TAX_OR_EXERCISE_PAYMENT`, `G → GIFT`, otherwise `OTHER`. If source text establishes special/compound SEC codes, retain verbatim and conservatively classify `OTHER` until explicitly supported.
- `acquired_disposed`: `A` or `D`, independent of SEC transaction code; never assume P and S imply this field without checking the filing.
- `quantity`: positive Decimal string; `price_per_unit`: null if not stated, else nonnegative Decimal string; `price_currency` must be a source-supported ISO currency when price is known and null otherwise. **Zero is not a substitute for missing**; no implicit USD or FX assumptions.
- `ownership_form`: `DIRECT` or `INDIRECT`; nature must be present when `INDIRECT` and disclosed; otherwise limitations explain the omission.
- `purchase_venue`: `OPEN_MARKET`, `PRIVATE`, `UNKNOWN`. Code `P` alone does **not** establish `OPEN_MARKET`; require an explicit cited venue statement with `purchase_venue_locator` for non-`UNKNOWN` values; otherwise this locator is null.
- `rule_10b5_1_status`: `REPORTED_YES`, `REPORTED_NO`, `NOT_DISCLOSED`. Preserve reported checkbox/plan indicator without inferring intent or legality.
- `review_status`: `VERIFIED` or `UNRESOLVED`; only `VERIFIED` unique effective rows contribute to totals. `UNRESOLVED` requires an explanatory note and is shown, not silently omitted.
- `source_row_id` uniquely identifies a disclosed table row **within a single filing**; `(source_id,source_row_id)` unique within a run.
- `supersedes_id` points to a corrected *original transaction within the same run* and requires a Form `/A` source with supported linkage; `duplicate_of_id` points to the same underlying economic event in the same run. Neither may point to itself, form a cycle, cross persons/instrument identities, or silently override a different event. A transaction cannot set both. If unresolved, set `review_status=UNRESOLVED`, show it with a warning, and exclude it from totals rather than guessing.

**Ownership:** `{id,person_id,source_id,source_row_id,as_of_date,table_type,security_title,reported_quantity,ownership_form,indirect_ownership_nature?,notes}`. A holding is an **as-filed observation**, not a portfolio transaction. It may be based on Form 3, or Form 4/5 post-transaction values. Do not sum across filing dates, derivative/non-derivative tables, or direct/indirect holdings. `reported_quantity` must be a nonnegative Decimal string. Keep filing and observation dates distinct.

**Global validation:** One issuer; `period_start <= period_end <= researched_as_of`; transaction dates within the requested range (amendment filings may arrive later, but their corrected in-scope transaction dates stay within the window); no source published/accepted after the research cutoff; SEC owner/issuer identity consistent; exactly one validated source per primary transaction line; same-run IDs/references only; no duplicates/cycles; all rows have attributable evidence; no unreviewed claims of completeness. Unknown/missing data stays absent. New source edits produce a new run, never an overwrite.

### Illustrative synthetic payload excerpt

The file must be a **complete** `InsiderResearchInput`; the excerpt below illustrates the crucial transaction distinction, not an independently validated example:

```json
{
  "schema_version": "1.0",
  "research_type": "MANAGEMENT_INSIDER_ACTIVITY",
  "company": {"name": "Fictional Systems Inc.", "ticker": "FCSI", "cik": "0000000001", "security_id": null},
  "scope": {"period_start": "2026-01-01", "period_end": "2026-10-09", "researched_as_of": "2026-10-10", "coverage_status": "PARTIAL", "coverage_notes": "Synthetic filing sample."},
  "sources": [],
  "people": [],
  "compensation": [],
  "transactions": [
    {"id":"tx-p","person_id":"p1","source_id":"form4-1","source_row_id":"non-derivative-1","transaction_date":"2026-05-01","table_type":"NON_DERIVATIVE","security_title":"Common Stock","transaction_code":"P","acquired_disposed":"A","quantity":"100","price_per_unit":"40.00","price_currency":"USD","ownership_form":"DIRECT","indirect_ownership_nature":null,"purchase_venue":"UNKNOWN","purchase_venue_locator":null,"rule_10b5_1_status":"NOT_DISCLOSED","review_status":"VERIFIED","supersedes_id":null,"duplicate_of_id":null,"notes":"Purchase venue not independently established."},
    {"id":"tx-m","person_id":"p1","source_id":"form4-2","source_row_id":"derivative-1","transaction_date":"2026-05-02","table_type":"DERIVATIVE","security_title":"Employee Stock Option","transaction_code":"M","acquired_disposed":"D","quantity":"200","price_per_unit":null,"price_currency":null,"ownership_form":"DIRECT","indirect_ownership_nature":null,"purchase_venue":"UNKNOWN","purchase_venue_locator":null,"rule_10b5_1_status":"NOT_DISCLOSED","review_status":"VERIFIED","supersedes_id":null,"duplicate_of_id":null,"notes":"Exercise/conversion, not a discretionary share purchase."}
  ],
  "ownership": [],
  "limitations": ["Illustrative only: filing and identity source records are intentionally omitted."]
}
```

The Pydantic contract must reject this **incomplete illustrative excerpt** because its referenced people/sources are absent. Put at least one **fully valid fictional package** with complete SEC-like source objects, roles and transactions in `tests/fixtures/insiders.json`; use that fixture for documented end-to-end examples.

## 5. SQLite schema 8 and persistence

Reuse `research_runs` (type `MANAGEMENT_INSIDER_ACTIVITY`, skill `investobot-management-insiders`, immutable `package_json`, compact `summary_json`, issuer identity, `researched_as_of`, no fiscal-year reporting fields) and `research_sources` (the existing SEC provenance columns; no shared-table redesign). Add four tables and only the indexes justified by filtering:

| Table | Primary key | Required columns / references |
|---|---|---|
| `research_insider_people` | `(run_id,person_id)` | `name`, `reporting_owner_type`, `reporting_owner_cik?`, `roles_json`, `identity_source_id`; FK `run_id → research_runs`, composite FK identity source → `research_sources`. |
| `research_insider_compensation` | `(run_id,compensation_id)` | `person_id`, `fiscal_year?`, `compensation_type`, `value_text?`, `currency?`, `value_basis`, `terms`, `source_id`, `source_locator`; composite FKs to same-run people/sources. |
| `research_insider_transactions` | `(run_id,transaction_id)` | `person_id`, `source_id`, `source_row_id`, `transaction_date`, `table_type`, `security_title`, `transaction_code`, `acquired_disposed`, `quantity_text`, `price_text?`, `price_currency?`, `ownership_form`, `indirect_nature?`, `purchase_venue`, `rule_10b5_1_status`, `review_status`, `purchase_venue_locator?`, `supersedes_id?`, `duplicate_of_id?`, `notes`; same-run FKs to people/sources/linked transactions; unique `(run_id,source_id,source_row_id)`. |
| `research_insider_ownership` | `(run_id,holding_id)` | `person_id`, `source_id`, `source_row_id`, `as_of_date`, `table_type`, `security_title`, `quantity_text`, `ownership_form`, `indirect_nature?`, `notes`; same-run FKs; unique `(run_id,source_id,source_row_id)`. |

`roles_json` and other small term/limitation arrays remain Pydantic-validated JSON. Do **not** add a fifth role table, person registry, graph database, cache, or a separate filings table: existing `research_sources` holds filing metadata. Do **not** copy entire SEC XML, HTML, proxy statements or non-public personal data into SQLite.

Add an index on `(run_id,person_id,transaction_date)` for transaction inspection, plus source/transaction unique constraints. Use SQLite checks for enum and numeric **storage shape** where practical; Pydantic owns richer validation, source association and amendment cycle checks. `PRAGMA foreign_keys=ON` must remain enforced. All new row inserts run inside one transaction; a failed insert rolls back the run, sources, people, compensation, transactions and holdings.

For normalizations/hashes, follow the competitive skill: sort independent collections by stable IDs; normalize Decimal strings (including tiny values, no exponent strings), preserve filing identifiers verbatim, preserve material source and status differences, and include **trusted** skill name/version/schema in SHA-256 identity. Keep earlier earnings/news/political/competitive run IDs unchanged. Reimport reordered identical content as `UNCHANGED`; new facts or corrected filings produce a distinct immutable run. Never update old runs in place.

**Amendment/duplicate counting:** Persist original and correction/duplicate rows, but summary counts and monetary totals use only effective unique **verified** underlying transactions. Build that effective set by following *validated explicit same-run links*: a superseded row is excluded; a duplicate row is excluded; a `review_status=UNRESOLVED` row is not counted and emits a warning. Correction must cite the `/A` filing and original accession. Missing original links cannot be silently reconciled across runs; make them `UNRESOLVED` in output and do not count a questionable row. A Form 5 row that repeats a previously reported Form 4 event must be marked as a linked duplicate or excluded as unresolved. Never infer a duplicate solely from date, shares and price.

## 6. CLI commands and deterministic reports

Use existing `invest research` grouping, JSON stdout, structured errors, mutation scopes and `invest tools` discovery:

```sh
invest research insiders validate FILE
invest research insiders import FILE
invest research insiders import FILE --yes
invest research insiders list [--ticker TICKER]
invest research insiders show RUN_ID
invest research insiders summary RUN_ID
invest research insiders activity RUN_ID [--person PERSON_ID]
invest research insiders ownership RUN_ID [--person PERSON_ID]
```

- `validate`: schema, issuer/person/filing association, amendments and source-link checks. Strictly read-only; no database creation or writes.
- `import`: preview by default (`PREVIEW`, counts, missing coverage, warnings, `committed:false`, `mutation_scope:"research"`); `--yes` after explicit human review; unchanged package returns `UNCHANGED` without writing. Do not allow the agent to self-authorize human approval.
- `list`: run ID, issuer/ticker, cutoff and coverage dates, counts, preview warnings; summary-only SQL, **no full `package_json` loads**.
- `show`: one full immutable accepted package and source provenance.
- `summary`: documented people/roles, compensation grouped by person and fiscal year, category-separated transaction counts/quantities and missing-data warnings, not an investment rating.
- `activity`: chronological effective and excluded transaction rows with raw SEC code, deterministic category, original and amended filing provenance, direct/indirect and derivative labels, source evidence and exclusion reason. `--person` rejects unknown IDs.
- `ownership`: most recent as-filed observations by `(person, security_title, table_type, ownership_form, indirect_nature)` plus all relevant dated observations; show date and source, **never calculated current holdings**. `--person` rejects unknown IDs.

**Summary arithmetic:** Count unique effective `P` purchases, `S` sales, `M` exercises/conversions, `A` grants, `F` tax/exercise payments, `G` gifts, and `OTHER` separately. Summarize quantities only per identical instrument title, derivative status and acquisition/disposition direction; do not net different share classes or direct/indirect types into a single “shares bought” amount. For `P` and `S` with reported per-unit price and currency, compute `quantity × price` as **reported gross line value** in Decimal by currency, explicitly **not realized gain, investment return, tax basis, execution proceeds or cash compensation**. Never synthesize missing prices, denominators or ownership percentages. Do not sum employee grant-date valuation with annual total compensation. Source-backed compensation arrangements remain terms, not arithmetic assumptions.

`invest tools describe research.insiders.import` must identify a research-only mutator. `invest schema` must expose `InsiderResearchInput`; CLI commands must be documented in skill references and AGENTS guidance. There is no WebUI change required.

## 7. BDD-first development — mandatory sequence

**Before any production implementation**, create **all** new readable `.feature` scenarios and their pytest-bdd step definitions plus complete offline fictional fixtures. Run the new suite and establish **expected RED failures** due to absent V2.9 behaviors (not test syntax, missing fixtures, or imported modules). Investigate accidental passing tests; commit the complete RED baseline. Only then implement Packages 1–4, taking their scenarios green. Run the entire regression suite, Ruff and offline Docker, then verify final GitHub Actions after push. Unit tests may supplement behavior tests; do not assert mock call order or internal class implementation details.

```gherkin
Feature: Management and insider research agent skill
  Scenario: Discover and install the insider research skill
    Given Investobot has its bundled investment research skills
    When an agent installs the skills for Codex or Claude Code
    Then the insider research method and authoritative JSON contract are available
    And existing user-customized skills remain unchanged

Feature: Reporting person and tenure identity
  Scenario: Distinguish a former executive from a large shareholder
    Given one person's documented executive role has ended
    And another reporting owner is identified only as a ten percent holder
    When a company management summary is requested
    Then the former role has its sourced historical tenure
    And the shareholder is not described as a current executive

  Scenario: Reject a transaction attributed by a common name alone
    Given a reported trade lacks a verified matching reporting-owner identity
    When the research is validated
    Then the transaction is rejected without saving research

Feature: Insider transaction classification
  Scenario: Distinguish a share purchase from an option exercise
    Given a verified Form 4 reports a P acquisition of 100 common shares
    And another row reports an M exercise of 200 options
    When reported activity is summarized
    Then 100 common shares are categorized as a reported purchase
    And 200 derivative units are categorized as exercise or conversion
    And the exercise is not counted as an open-market purchase

  Scenario: Avoid presenting stock awards as discretionary purchases
    Given a Form 4 contains a grant A and a tax-withholding F row
    When activity is summarized
    Then neither row increases the reported P purchase total
    And both retain their as-filed transaction codes

  Scenario: Preserve uncertain trading-plan status
    Given a historical insider sale has no disclosed Rule 10b5-1 indication
    When it is inspected
    Then its plan status is NOT_DISCLOSED
    And no trading intent is inferred

Feature: Filing amendments and accurate totals
  Scenario: Count a corrected filing transaction only once
    Given an original Form 4 reports a sale of 100 shares
    And an identified Form 4 amendment corrects it to 120 shares
    When the accepted activity is summarized
    Then the effective reported sale is 120 shares
    And both filings remain available with their correction relationship

  Scenario: An unresolved duplicate cannot inflate reported activity
    Given a possible Form 5 duplicate cannot be matched to the original event
    When the research is summarized
    Then the questionable row is excluded from counted totals
    And its ambiguity is disclosed

Feature: Ownership and compensation disclosure
  Scenario: Dated holdings are observations, not additive balances
    Given a Form 3 shows 100 directly held common shares
    And a later Form 4 reports 125 common shares held after a transaction
    When ownership is reviewed
    Then both dated ownership observations are shown
    And they are not added together as 225 shares

  Scenario: Grant-date equity value is not cash compensation
    Given a proxy reports salary, stock-award grant-date fair value, and total compensation
    When compensation is summarized
    Then the stock award remains labeled grant-date fair value
    And the existing reported total is not added to its components

Feature: Immutable, human-approved research
  Scenario: Previewing insider research does not change the ledger
    Given a source-backed fictional insider research package
    When the package is validated and its import is previewed
    Then no research records or portfolio records are written

  Scenario: Repeated and corrected packages preserve history
    Given an accepted fictional insider research package
    When the same evidence is imported again in a different JSON order
    Then the import is idempotent
    And when corrected evidence is accepted it creates a new immutable run

  Scenario: Rejected conflicting filing evidence is atomic
    Given research cites a filing for an unrelated issuer
    When the import is attempted
    Then no people, compensation, transactions, holdings or sources are persisted

  Scenario: Research cannot alter a saved investment plan
    Given accepted portfolio holdings and a saved trade plan
    When approved insider research is imported
    Then holdings and tax lots remain unchanged
    And the saved plan's stale status is unchanged
```

**Targeted tests** additionally cover: forms 3/4/5 and `/A`; primary issuer CIK, owner CIK, SEC accession and source-locator matching; multiple reporting persons on one filing; direct/indirect ownership; derivative versus underlying shares; P purchase venue unknown versus verified market/private; S sales with 10b5-1 yes/no/not disclosed; code A/M/F/G/J and unknown SEC codes; zero/missing price; small and large Decimal precision; reported versus noncash compensation; fiscal-year attribution; known/unknown tenure dates; overlapping role titles; gift/amendment/duplicate counting without cycles; rejected cross-run links; incomplete coverage and no-filed-transaction cases; archive-safe source URLs; deterministic hashes and item ordering; schema 7 rejected without mutation; read-only compact list; unknown run/person IDs; full offline regression of all earlier skills and planning.

## 8. Non-overlapping work packages

After **all new BDD scenarios are RED**, implement sequentially:

| Order | Owner/surface | Required result |
|---|---|---|
| **1 — Skill and research method** | `skills/investobot-management-insiders/**`, `src/invest/research_skills.py` | Portable, versioned skill, SEC source and transaction-code guidelines, Codex/Claude installation without modifying other skills. No CLI research processing. |
| **2 — Domain contract** | `src/invest/insider_models.py`, fictional test fixture | Strict issuer, people, roles, compensation, transactions, ownership, source and correction-link validation. No persistence. |
| **3 — Storage and import** | `src/invest/insiders.py`, schema-8 setup in `src/invest/ledger.py`; existing hash/insert helpers only if minimal reuse is needed | Four tables, complete rollback, verified relationships, canonical immutable identity, preview/explicit acceptance, effective-row inclusion decisions. No reporting computations. |
| **4 — CLI and summaries** | `src/invest/insider_queries.py`, additive `cli.py`, `contracts.py` wiring | `validate/import/list/show/summary/activity/ownership`, Decimal classifications, dated holdings, compensation representation, source-backed warnings; no legacy research refactor. |
| **5 — Regression, documentation, release** | New `.feature`/pytest modules; `README.md`, `AGENTS.md`, `docs/agent-usage.md`, `docs/research-skills.md`, `docs/data-model.md`, `docs/development.md`, new `docs/insider-research.md` | All BDD GREEN, full pytest/Ruff, offline locked Docker CI, updated schema-8 deliberate reset instructions and complete documented synthetic example. Final remote GitHub CI verification. |

### KISS boundaries / code smells to avoid

- Reuse `research_runs`, `research_sources`, project-local skills, error conventions and research-only mutation contract; **do not add a universal people database or reimplement one in every skill**. Per-run person records are enough for this MVP.
- Keep the existing earnings-specific `research_storage.canonical_package()` unchanged. A compact domain-local canonicalizer may reuse `canonical_json_hash()` and Decimal helpers, as the competitive skill does; **do not expand a misleadingly named specialized helper into a new generic framework**.
- Do not mix Form 3/4/5 reported beneficial positions with Investobot's household positions or cost-basis ledger. These represent other people's filings.
- Avoid advice scores, insider sentiment, realized gain computations, share-price overlays, alerts, automatic filing downloads, officer social profiles, political donations, cross-issuer networks, or cross-run automatic delta detection in V2.9.

## 9. Final acceptance / release gates

V2.9 is complete only when the new skill is discoverable and installs safely; one valid source-backed fictional package passes strict JSON validation, preview, human-confirmed immutable import and read-only reports; **P/S/M/A/F/G and unknown codes remain distinguishable**; amendments/duplicates do not double count; ownership observations and proxy grant-date equity values are not misleadingly totaled; the four-table schema-8 storage enforces consistent same-run evidence; earlier research and portfolio planning remain untouched; the complete **BDD suite is demonstrably RED before implementation and GREEN after**, full pytest/Ruff and offline Docker pass, and final GitHub Actions is green.

**Separate real-data gate:** Using one U.S. issuer, manually verify a small sample of Form 3 holdings, Form 4 purchase/sale/exercise/grant/tax rows, a `/A` if available, and DEF 14A compensation against original SEC filings and footnotes. Record coverage gaps and mismatches; no private financial data required. Synthetic CI success does not establish extraction accuracy.

**Guiding principle:** *The agent researches management and as-filed insider disclosures. Investobot preserves provenance and distinguishes economic event types with deterministic summaries. The human interprets business significance.*
