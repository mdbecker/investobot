# Investobot — Final MVP Foundation Stabilization PRD

**Date:** 2026-10-12  
**Status:** Approved implementation direction; not a claim of completed work  
**Scope:** One finite pre-real-data cleanup, organized as independent, reviewable work packages  
**Starting reference:** [`mdbecker/investobot`](https://github.com/mdbecker/investobot), reviewed at `6af9cc6f7942c3c6554a11eed92637b6f4cdb40c`; reconcile filenames and code against HEAD before editing.

> **Dependencies — assume already implemented.** This PRD builds on `docs/PRD-unified-mvp-2026-10-10.md` and `docs/PRD-mvp-wrap-up-2026-10-12.md`, including their completed deterministic ledger, tax, provenance, agent-skill, saved-plan, saved-backtest, synthetic regression, and lightweight performance work. **This PRD supersedes conflicting requirements** concerning dashboard mutations, routine trading cadence, branch protection as a release gate, and the ordering of real-broker data validation; other financial safety invariants remain binding. If an older document disagrees, this PRD wins on those four subjects. The prior PRDs are not an invitation to restart their completed work.

## 1. Product decision and nonnegotiable boundaries

Investobot is a **single-user, local, agent-operated financial analysis toolkit**. The **AI agent** invokes small composable skills and the existing **deterministic Python CLI** to gather evidence, validate documents, record *human-authorized* facts, calculate scenarios, and save results. **SQLite is the financial source of truth. The dashboard is a read-only viewer** of accepted data and already saved analytical results—not a second workflow/command interface. Humans still review evidence and authorize material financial changes; no automated brokerage login or trade execution.

Keep existing `Decimal` accounting, atomic/idempotent ledger changes, canonical security/lot IDs, sourced dates and market prices, explicit `REAL`/`SYNTHETIC` separation, immutable versioned policies/plans/backtests, annual **positive estimated tax-dollar** budget, cash constraints, manual trade decisions, honest known/unknown statuses, and safe backup/restore. A valid calculation must not imply legal wash-sale certainty, real-world provider validation, or investment advice. A preview is not an accepted fact.

**User habits are context, not rules:** trading is usually infrequent, typically contribution-driven and often no more than monthly; quarterly rebalancing is a general preference, **not a requirement to trade** in any month or to restrict proposal dates to prescribed months. Explicitly selected historical `QUARTERLY` backtests remain legitimate hypothetical models, not imposed actual trading policy.

**Acceptance ordering:** stabilize architecture, correctness and synthetic behavior **first**; introduce sanitized original brokerage statements and live data-provider validation **afterward** as a separate phase. Do not claim real-data readiness on the strength of synthetic tests. Main-branch protection is not required for this personal repository; keep useful CI, but do not add enforcement administration.

## 2. Development method and review standard

Follow the attached `code_review(8).md` and `code_smell_review(9).md` guides in this order: **intent → architecture → implementation → polish**. Investigate the five smell families—**Bloaters, Object-Orientation Abusers, Change Preventers, Dispensables, Couplers**—but fix demonstrated problems, not labels. In this work the main risks are divergent ownership of mutations (Couplers/Change Preventers), unnecessary dashboard workflows and stale tests (Dispensables), conditional-heavy planner/accounting logic (Bloaters), and evidence contracts split across boundaries (Change Preventers). Prefer deleting code, sharing an *existing* canonical function, and a few cohesive edits over new layers. The code is pre-user: no compatibility shims, obsolete API aliases, old format migrations, or preservation of unused screens. Retain schema versioning and recovery safeguards; never casually destroy an existing local DB.

**Mandatory BDD sequence, before any production implementation:**

1. **Write or revise the full set of new/changed behavior scenarios for all work packages A–F first.** Use Given/When/Then domain language and concrete synthetic examples; assert observable financial values, statuses, read-only outcomes, or saved evidence. Preserve unaffected existing tests.
2. **Run these tests against the unchanged baseline. Record each expected red failure and its reason.** A test that unexpectedly passes must be investigated: perhaps behavior already exists, the test is weak, or the finding is incorrect. Do not manufacture a failure. Replace/remove old tests that explicitly require the soon-to-be-deleted dashboard behavior; do not leave contradictory expectations.
3. Only **after the behavioral test suite has been authored and its baseline results recorded**, implement packages A–F in the order below, making their scenarios green incrementally. Keep refactoring-only assertions green; do not invent failing tests for behavior-preserving cleanup.
4. Review each package for correctness and smells, then run the complete suite, lint, representative offline workflows and existing lightweight performance checks at the end.

Prefer `pytest-bdd` where it reads naturally; existing pytest fixtures are fine. Do not add a new BDD runner or sprawling numeric-case dispatch test suite. Mock only actual external boundaries (e.g., an HTTP provider), not domain methods or internal call order. Tests should survive renaming functions and refactoring modules. No private financial data in fixtures or CI.

## 3. Work packages — small ownership surfaces, minimal overlap

Each package owns the listed source and its adjacent focused tests. **Package G alone** reconciles cross-cutting documentation and removes dead artifacts after A–F; **Package H alone** runs final integrated acceptance. Avoid mixing unrelated refactors into a package. Work on separate reviewable commits; do not push without the repository owner's direction.

### A — Dashboard: read-only financial viewer (**Must fix before merging · TODO**)

**Problem:** `src/invest/web.py`, `static/index.html`, and `static/app.js` provide import/reconcile/apply, activity recording, target edits, plan generation, prompt editing and analysis execution. This creates an unnecessary second mutation surface and is contrary to product intent.

**Decision:** The web server shall use **only read-only SQLite connections** for application data. Remove all write endpoints and their forms, JavaScript state, backend dispatchers, and associated tests/docs. **All POST requests return HTTP 405** with a small safe JSON error; requests must never instantiate a writable `Ledger`, create an absent DB file, write provider caches, or invoke remote providers. Preserve loopback binding, safe headers, minimal error handling and the existing no-auth local-only posture. Do not replace removed operations with another web job/command API.

**Retain only relevant viewing:** accepted household holdings/cash, value, data freshness and coverage, actual performance, tax-lot warnings, active/saved targets with drift, immutable saved plans and report downloads, and saved historical backtests and their comparisons. A read-only user-selected comparison may perform **deterministic arithmetic over persisted records in memory**; it must not launch a new simulation or write a result. Keep informative empty/unavailable states rather than fabricated numbers. Remove prompt-library editing, import, record-activity and analysis-workbench navigation; prompt and research operations remain CLI/agent responsibilities.

**Backtests are already stored:** reuse the existing `backtest_runs` table and `invest.backtest.compare(ledger, run_ids)`. Add only minimal GET endpoints for listing saved runs, reading one run, and comparing selected saved runs; read stored `result_json` directly and preserve the existing `COMPARABLE`/`INCOMPARABLE` status and assumption-mismatch explanations. No new table, materialized view, cache, framework, scheduler, or backtest runner. Existing plans/targets GET routes may stay if read-only. For any exposure summary, use accepted/persisted observations only: **no implicit market-data refresh or outbound HTTP from a dashboard GET**, including on cache miss/stale cache. Unknown constituents remain visibly unknown.

**Behavioral proofs:** (i) populated dashboard shows accepted balances and an already saved plan; (ii) it shows two saved backtests and flags incompatible assumptions; (iii) an empty DB shows no invented data and is not created merely by GET; (iv) every former POST returns 405 and financial, policy, research, prompt and cache records remain unchanged; (v) GET does not call a provider even when cache is absent; (vi) no removed forms/actions remain in the served UI. Preserve relevant GET authorization/error tests, delete mutation-oriented web tests rather than testing removed features.

**Owned code:** `src/invest/web.py`, `src/invest/static/{index.html,app.js,style.css}`, dashboard-specific tests/features. Do **not** alter canonical CLI write commands or database schema in this package.

### B — Trading proposals: remove accidental calendar enforcement (**Must fix before merging · TODO**)

**Problem:** `src/invest/planning.py` presently blocks proposals using `MONTHLY_CADENCE_USED` and requires March/June/September/December plus drift threshold for routine rebalance. `src/invest/policy_models.py`, `src/invest/harvest_proposals.py`, and policy documentation expose supporting quarterly/exception controls. These were based on *habits*, not mandatory constraints.

**Decision:** Keep explicit `contributions-only` (buy-only) and `rebalance` (cash-first, then permitted sells/buys) modes. **Neither is gated by calendar month, a preceding trade that month, or a minimum drift threshold.** In `rebalance` mode, evaluate positive residual target deviation and generate reasonable actions on any supplied valid date; no unnecessary zero-size trades. Drift and previous trading activity may appear as informative metrics/warnings, **not blockers**. Do not create a general scheduling-policy engine. Remove `MONTHLY_CADENCE_USED`, `CADENCE_NOT_ELIGIBLE`, fixed quarterly windows, `quarterly_months`, `drift_trigger` as an execution gate, and calendar-only exception flags/justifications from the *approved live proposal* policy and its outputs/tests/docs. Since no users depend on old payloads, remove unused fields rather than preserving aliases. **Remove the `HARVEST_EXCEPTION_REQUIRED` calendar exception gate too**, while retaining a human-approved immutable harvest policy, exact lot/tax-budget checks, replacement review, wash-sale cautions and every other substantive safety condition.

**Keep independently chosen backtest strategy options:** `BUY_AND_HOLD` and `QUARTERLY` in `src/invest/backtest.py` remain; their frequency and drift assumptions are explicit hypothetical inputs, not constraints on today's proposal. Do not rewrite the backtest engine.

**Behavioral proofs:** (i) a February 10 rebalance with verified eligible under/overweights and approved tax/cash constraints proposes the same valid sale/buy logic as a March 10 rebalance, all else equal; (ii) an already confirmed purchase in the same month does not block a later proposal; (iii) contributions-only never sells; (iv) low but nonzero drift is not a date/threshold rejection, subject to minimum trade notional; (v) taxable and TLH guards are unchanged; (vi) an explicitly selected quarterly historical backtest still applies its recorded strategy.

**Owned code:** `src/invest/planning.py` calendar gates, `policy_models.py` relevant fields, `harvest_proposals.py` calendar exception, planning/TLH policy fixtures and tests. Do not alter account/lot math here; package C owns that.

### C — Retirement sales: missing tax basis must not break share accounting (**Must fix before merging · TODO**)

**Problem:** `planning._propose().add(SELL, ...)` sorts all sales by per-share basis, including tax-free/deferred accounts, and `accounting.activity_change_inplace()` calculates basis/date for allocated sales irrespective of tax treatment. A legitimate retirement sale can crash when basis is unknown; skipping all lot math can leave inconsistent quantities.

**Decision:** Branch **once on accepted account tax status**. For `TAXABLE`, retain sourced/verified full-lot coverage, adjusted-basis HIFO selection, acquisition dates, tax estimation and annual tax-budget guards. For `TAX_FREE`/`TAX_DEFERRED`, require real share availability and valid sourced lot identity/quantity as applicable, **but not cost basis or acquisition date merely to simulate a sale**; consume known lot quantities deterministically by canonical lot ID, never call `Decimal(None)`, never synthesize a cost basis, holding term, realized gain or tax. Unknown retirement basis remains `null`, not zero; no retirement capital-gains tax budget is consumed. If the source's lot inventory is insufficient/inconsistent, return a typed *review/blocker for that sale* rather than throwing or claiming reconciled lots. Never weaken restrictions on real verified identities, positive quantities, sufficient shares, cash, fees or immutability. Validate the same behavior in the authoritative simulator and confirmed-activity path where shared.

**Behavioral proofs:** a synthetic tax-free account with 10 verified shares, missing basis/acquisition date, and a 4-share proposed sale produces a coherent 6-share remainder, correct cash/notional, unknown basis, and no estimated capital-gains tax; an equivalent taxable sale is safely blocked absent required facts; an impossible 11-share sale or inconsistent lots is blocked with a typed reason. No accepted state changes from hypothetical simulation.

**Owned code:** targeted sale branches in `src/invest/planning.py` and `src/invest/accounting.py`, affected simulation/activity tests; avoid a parallel retirement-only simulator or broad accounting rewrite.

### D — CLI document intake: make environment provenance internally consistent (**Should fix now · TODO**)

**Problem:** CLI `portfolio import` passes no environment into `parse_html()` then overwrites only the returned top-level field. The parser can therefore emit `UNKNOWN_DATA_ENVIRONMENT` even when the CLI user supplied it. The correct import workflow is the **agent-run CLI**, not the deleted dashboard importer.

**Decision:** Require explicit `--data-environment REAL|SYNTHETIC` on the CLI import command, and pass it **directly** to `parse_html()` so snapshot metadata, issues and downstream reconciliation agree. Do not silently assume REAL, suppress parser warnings wholesale, or fabricate source dates/coverage. Preserve existing parser validation, source hash, account aliases, incomplete-row warnings, explicit reconciliation and **human-confirmed** application. Check that a candidate carrying blocking parser evidence issues cannot be accepted as complete/clean merely by overriding a top-level field; use existing typed issue/coverage mechanisms rather than a new validation stack. The `UNVALIDATED_INSTITUTION_ADAPTER` remains until Phase 2 real-page testing; don't optimize or expand parsers here.

**Behavioral proofs:** explicit REAL and SYNTHETIC candidates show matching labels and no contradictory unknown-environment issue; omitted/invalid environment fails safely before import; partial/unresolved HTML cannot silently become complete accepted holdings; preview/reconcile/confirmed apply remain atomic, idempotent, auditable and preserve raw-HTML privacy.

**Owned code:** `src/invest/cli.py` import boundary, `src/invest/parsers/generic.py` only if essential to preserve parser contract, narrow `models.py`/ledger checks only if reproduced via a failing BDD scenario; corresponding CLI/import tests.

### E — Fund look-through: evidence completeness must be honest (**Should fix now · TODO**)

**Problem:** direct `lookthrough.exposure()` can treat an observation with no `data_environment` as valid. It may report a numerically complete portfolio even when evidentiary provenance is absent. The portfolio research orchestration already enforces stronger environment checks; the underlying domain function must not contradict it.

**Decision:** At the direct exposure boundary, require an explicit matching `REAL`/`SYNTHETIC` observation environment and an identifiable source/date for claiming *verified complete* look-through. Missing provenance must produce a typed issue and `complete=false` / review-required or partial status. **Do not erase known constituent values or rescale unknown residual weights**; report numerical exposure and evidence completeness separately using the existing result shape and issue list. For file artifacts, retain available immutable hash/manifest evidence; do not require an invented hash from provider records whose actual source contract lacks one. Existing genuine gaps—unknown constituents, stale holdings, cycles, unsupported currencies, unresolved issuers—still surface independently. Do not add a second evidence registry or research-universe implementation.

**Behavioral proofs:** full numerical weights with missing environment or source identity do not claim complete verified coverage; matching sourced nested holdings produce correct weighted totals and preserved paths; unknown constituents stay unknown rather than being redistributed; mismatched environments block actionable research. Existing `portfolio_research_inputs.universe()` results remain consistent.

**Owned code:** `src/invest/lookthrough.py`, nearest evidence tests; touch orchestration only if an observed contract mismatch requires it.

### F — Historical prices: don't mistake exchange holidays for missing sessions (**Should fix now · TODO**)

**Problem:** `MarketClient.history()` treats weekdays from `numpy.busday_count()` as verified trading sessions. It can mark a normal exchange holiday as missing history, making valid observed adjusted prices spuriously `PARTIAL`.

**Decision:** Remove weekday-count-based claims of missing **exchange** sessions. Market history should report exactly which adjusted-close observations exist and distinguish **provider-observed coverage** from **independently verified full-session coverage**. Without an explicitly pinned session calendar, completeness is **unverified**, not known broken and not certified complete. When an explicit calendar is supplied by the existing backtest manifest, its established missing-session checks remain authoritative; do not build a new holiday-calendar service or install another dependency. Preserve blocking errors for invalid dates, duplicate observations, nonpositive prices and genuinely absent adjusted-return evidence.

**Behavioral proofs:** Friday-to-Tuesday over an exchange holiday is not falsely flagged as a missing session; actual missing dates against a pinned calendar remain blocked in backtests; a genuine lack of adjusted-close data remains explicitly unavailable; an unverified provider calendar is clearly disclosed, never silently promoted to verified coverage.

**Owned code:** `src/invest/market.py` history normalization and its direct tests; backtest integration assertions only, not a backtest rewrite.

### G — Delete obsolete code and reconcile the active instructions (**Recommended now · TODO/Nit**)

**Run after A–F; no new product behavior.** Remove now-unreachable web imports, handlers, JavaScript variables, CSS and obsolete test scenarios; prune duplicated policy/cadence constants and defunct docs/examples. Update the *active* `README.md`, `docs/product.md`, `docs/workflows.md`, `docs/trading-policy.md`, `docs/backtests.md` only as needed, dashboard/help text, and `AGENTS.md` to explain: agent/CLI-only mutations; human review; GET-only dashboard; read-only saved backtest comparisons; optional hypothetical quarterly *backtests* vs no enforced live trading schedule; explicit CLI data environment; Phase 1 vs Phase 2 limitations. Correct stale CLI examples (e.g. `contributions-only`, not `contribution_only`) and inaccurate schema claims where present. Old PRDs remain historical but add a short supersession pointer rather than editing history everywhere.

Refactor the opaque case-number dispatch in `tests/test_mvp_decisions_bdd.py` **only to the extent needed for scenarios directly changed here**; create small domain-readable tests, do not undertake a full test-suite restructure. Remove tests only when they assert intentionally retired behavior; preserve independent financial assertions. Review touched diffs for the guide's dead code, shotgun surgery, speculative generality, excessive conditionals, excessive comments, unhelpful wrappers, duplicative docs, and fragile mock-heavy tests. **No broad cleanup outside affected surfaces, new ORMs, services, middleware, state stores, JS frameworks, performance suites, or database redesign.** If a refactor moves code without changing behavior, existing passing tests—not artificial red tests—are the criterion.

### H — Integrated acceptance and handoff (**Must fix before merging · TODO**)

**Run after G.** Execute Ruff, the full offline behavior suite, representative end-to-end synthetic CLI flows (import → reconcile → accept → performance; approved policy → proposal → simulation; TLH; recursive look-through; run/save/compare backtests), and the eight existing fixed performance workflows. If an intentional financial rule changes a benchmark result fingerprint, document that exact semantic change and update the minimal reference/fixture expectations through the existing approved process; **do not weaken the >25% confirmed-slowdown guard, broaden the benchmark suite, or resurrect AI fuzz campaigns**. The web server must work against an absent/empty DB and a populated saved-results DB, with no mutation or network side effects. Test raw/unknown/partial inputs and rollback on failures. No actual brokerage documents, provider entitlements or real financial accounts in Phase 1.

Deliver a short handoff note stating changed/deleted files, baseline red scenarios, final green counts/commands, unchanged financial invariants, whether the performance gate passed, and any remaining true limitations. **Do not push**; leave commits for human review.

## 4. MVP definition of done / stop rule

The work is complete when **all** the following hold:

- **Architectural:** the dashboard presents accepted facts and persisted alternatives, can compare saved backtests, and has **zero mutation or command-execution endpoints**; DB/caches/prompts/policies remain unchanged across web use.
- **Financial:** contributions-only and rebalance proposals are not calendar-gated; retirement-account basisless sales simulate safely without made-up tax facts; taxable-sale/tax-budget/TLH safeguards remain intact.
- **Evidence:** explicit CLI import environments are consistent from parsing through acceptance; unresolved parsing and look-through provenance do not become false completeness; history coverage does not misclassify holidays or invent verified sessions.
- **Quality:** new behavior had meaningful baseline-red BDD coverage written before code; final suite/lint and lightweight performance checks pass; touched code and active docs no longer contain contradictory retired workflows or dead scaffolding.
- **Scope:** no new frameworks, services, scheduling engine, UI mutation flows, extensive stress/fuzz infrastructure, mandatory branch protection, or premature real-document testing.

**Stop at this point.** Phase 2—reviewed anonymized original brokerage HTML and live FMP contract verification—starts **only after** this foundation is accepted. Remain explicit that financial results are synthetic-tested and real provider readiness is unverified until that phase completes.
