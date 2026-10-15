# Correctness and simplification handoff - 2026-10-14

Synthetic MVP implementation is complete under the
[completion addendum](../PRD-mvp-completion-scope-addendum-2026-10-14.md).
Original verified product commit: `a6d3efa2aae48c6a1aa592e33d357e89766178f9` on `main`.
The final handoff commit changes documentation only. No pushes or host installs.

## Review follow-up — 2026-10-14

The supplied 22-commit review's nullable-price case reproduced as `Invalid numeric
value`; test-only red checkpoint `7ba80a1` preceded fix `04246f0`.
Reconciliation now emits `INCOMPLETE_POSITION_VALUATION` when a comparison term is
absent despite printed precision, preserving other review evidence and accepted
state without inferring a price. Four key exposure scenarios now state concrete
observable amounts, identity and denominator outcomes instead of a case-name
switch. Their original numerical expectations remain unchanged. The testing guide
clarifies the addendum's mounted-source reuse allowance.

Latest verified product: `04246f0be9f55f444dedb23001c53874a5bc58e8`.
Locked offline Docker mounted-source verification: **1,390 passed in 46.49s**;
Ruff **All checks passed**. Focused observation/exposure checks: **26 passed**.
Local logs: ignored `benchmark-results/review-2026-10-14/`; these results do not
claim fresh exact-image or remote CI verification. No known material correctness
defect remains from the supplied review.

Packaging, skills, host bridge, recovery and dashboard inputs are unchanged; their
earlier passing smoke checks below are reused. No benchmark, profile, CI change or
provider validation was performed for this review. **PERFORMANCE EXCEPTION — NOT
PASSED** and all real-source gates remain unchanged.

Current contract: [correctness PRD](../PRD-mvp-correctness-simplification-2026-10-13.md).
It supersedes explicit older decisions; unchanged financial/recovery/privacy
invariants remain. No broker credentials, orders, agent service, host installation,
remote Git operation or push is part of this work.

Gate 0 on untouched main: the complete A-F synthetic BDD set produced **35 failed,
10 preservation passes**, committed `0b4dd66` before production edits. Failures
covered canonical ticker reconciliation, lost parser diagnostics, observed exposure,
fee-adjusted tax budgeting, household dates, preview writes and retired/implicit
CLI behavior. Existing absent-mark summary, partial inventory preservation and
basic fee arithmetic were already correct and remained preservation tests.

Original acceptance set passed all 45 scenarios at `de173e0`. Review then found
independently supported XIRR was being suppressed by intermediate TWR ambiguity;
source/cash/issuer boundaries and long Decimal input precision needed additional
scenarios. Each confirmed behavior received a test-only red checkpoint before its
fix. Full mounted-source offline Docker checkpoint `34106fd`: **1,384 passed**,
Ruff passed. The later fixed saved-plan fixture regression showed previews must
not prepare persisted plans; preparation now explicitly approves immutable policy
and preserves real zero-cash coverage. Product source reference for final checks
is recorded below after exact-image verification.

One `lookthrough.exposure`, one `planning.propose`, and one hypothetical sale
estimator now serve all workflows. Deleted the separate exposure/proposal engines,
public generation command, redundant ST/LT gain-budget input fields and their
implementation-specific tests. Useful storage, classification, research
nonmutation, exact accounting and recovery regressions use approved canonical
proposals. The older broad storage benchmark is removed; eight fixed paired
workflows remain. No schema migration or compatibility adapter was added.

Current observations preserve all typed diagnostics; accepted proposal blockers
remain blockers in planning/exposure. Same import-time observation ties select the
later stored receipt, never a random UUID; this is receipt selection, not inferred
financial event ordering. Missing valuation/cash leaves null denominators with
known amounts. Source-only identities retain paths and never become ticker-based
issuer equivalence. Provisional caches cannot certify issuer aggregation. Stale
observed numeric exposure remains visible separately from evidence quality.

CLI snapshots preview by default and require explicit publication confirmation;
absent-ledger preview leaves it absent. Preview saves nothing. Approved proposals
require saved target IDs and retain full executable details. Backtest comparison
creates no targets or transition plans. Skills prefer monthly discretionary
sessions and at most four rebalances annually as human preferences, with explained
exceptions on any valid date. [Workflows](../workflows.md) is authoritative.

Review followed intent, architecture, implementation, then polish. The separately
referenced `code_review(8).md` and `code_smell_review(9).md` were not supplied/readable;
the criteria reproduced in the PRD were applied. Must fix/TODO findings (source
gates, denominators, identity, fee residues and chronology) received regression
coverage. Recommended now/Follow-up: provide reviewed real sources. Can defer/
Follow-up: the safe deterministic planner may leave drift when a full requested
sale exceeds allowance; no optimizer or guarantee of global optimality is claimed.

## Fixed performance evidence projection

Reference and recipe pins remain unchanged. Native outputs and initial unprojected
warmup identities stay in ignored local evidence. The retained single warmup
samples have no second timed warmup. Native oracles run before reviewed comparison
projection, outside timed operations. Fixture preparation and raw retention are
also outside measurement.

The only additional comparison deltas are: empty accepted source issues/null
institution status; retired null gain-budget placeholders; saved=true; new zero
sale metrics and zero term summary metrics; complete exposure flags/subtotals,
reviewed supplemental identity labels, complete fund coverage and false stale/
provisional path labels. Normalized source-state hashes are recomputed from the
same projected facts; original hashes remain in native evidence. Nonempty issues,
nonzero sale metrics, partial/uncertain exposure or nonempty retired budgets cannot
be hidden. Money, action quantities, lot allocations, source/policy evidence and
contribution paths remain in compared output. Projection tests preserve changed
cents and typed source blockers. These are response/evidence-shape deltas, not a
rebaseline or performance allowance.

Local evidence: ignored `benchmark-results/correctness-2026-10-13/`. Retain 90 days
and retain unresolved failures until resolution. Local checks are not remote CI.

## Final bounded verification

The final material corrections preserve exact large-value summary cents and make
partial/repeated imports retain honest coverage and source diagnostics. Test-only
checkpoint `610a033` observed three failures and four preservation passes before
these fixes. An older complete-response expectation was updated only for the
intentional added `issues` and `evidence_complete` fields; no financial expected
values changed. A small behavior-preserving exposure refactor already underway
before the addendum avoids rebuilding issuer metadata and repeated sums/scans.

- Final locked offline Docker full suite: **1,389 passed in 45.93s**
  (`final-green-repeat.log`); Ruff: **All checks passed** (`final-ruff.log`).
  Focused final observation/history/exposure checks: **27 passed**
  (`final-focused.log`). No further production changes followed these checks.
- Actual synthetic CLI demo passed against the final bound source: no external
  calls, hypothetical operations preserved accepted financial fingerprints,
  specific-lot conservation and nested source paths passed, and backup/restore
  recovered financial facts and corpus retrieval (`final-cli-demo.json`).
- Disposable real host bridge/Compose walkthrough passed: private host storage,
  absent-ledger previews, explicit/idempotent evidence publication, project skill
  installation preserving unrelated resources, online backup/verify, restore
  preview/confirm, loopback GET and malformed POST **405**, unchanged GET results
  (`host-qa.log`). The initial temporary project-name error was corrected in the
  disposable QA script; it did not reveal a product defect.
- Reused valid image/wheel QA from `dc894c8`: both project-local agent formats,
  **13 bundled skills**, installed wheel resources, retired command/module absent,
  and private directories excluded. Subsequent changes did not change packaging
  or skills. Final smoke tests use the final source bind with that image's locked
  runtime; no claim is made that its baked source contains later corrections.
  Earlier exact-image tests passed **1,387 tests**; final-source results above
  supersede that count. All results are local, not remote CI evidence.

No outstanding material correctness defect is known from these finite checks.
Residual maintenance limits: the existing CLI remains large, and the deterministic
greedy planner can leave drift when full sales exceed the approved tax allowance;
it is not a global optimizer. Further audit/refactoring is deferred.

## PERFORMANCE EXCEPTION — NOT PASSED

The addendum explicitly accepts the confirmed exposure regression for this
implementation. The gate remains failed; its threshold/reference are unchanged
for this exception. No further measurements, profiles or optimization follow the
addendum. The final small refactor and summary/import corrections were **not
remeasured**; no performance improvement is claimed.

Measured candidate product: `dc894c8c6ce72db25c44e12da4034c6874b61e0f`;
reference: `d0940a12c44831095492efcd7091fb7b937ad6b3`. Native ARM64, same Docker
runner, offline, 2 CPUs/4 GiB, one warm-up per pair and five samples per shared
batch. All raw samples exceeded 200 ms and native financial/identity/path oracles
passed. The other seven workflows stayed within the guard in both pairs.

| Look-through paired workflow | Reference median | Candidate median | Change | Raw batch medians |
|---|---:|---:|---:|---|
| Initial pair | 4.560949 ms | 6.196091 ms | +35.85% | 136 iterations: 620.289050 / 842.668422 ms |
| Complete confirmation pair | 4.404951 ms | 6.268134 ms | +42.30% | 134 iterations: 590.263367 / 839.930002 ms |

Each iteration runs recursive exposure plus top-issuer selection: four accounts,
200 positions, 400 lots, four funds with 12 constituents and three nested levels.
Both paths retain comparable financial quantities and contribution paths; the new
path additionally reports source identity/provenance and explicit numeric/evidence
coverage. They do not perform identical reporting work. No evidence fields were
removed to improve speed. Reviewed incidental response/order deltas are documented
above; immutable receipt lists compare full membership independently of display
ordering. Native results, initial invalid comparisons, raw samples and exit codes
remain outside Git under the local evidence directory. The confirmed result is
`performance/confirmed-comparison.json`: **FAIL**, accepted exception, not green.

## Real-source gate — NOT TESTED / UNVERIFIED

No reviewed Vanguard, Fidelity NetBenefits, PNC HTML or entitled FMP responses were
supplied. Every adapter remains PROVISIONAL; live FMP remains UNVERIFIED. The
[readiness matrix](../readiness.md) records NOT TESTED human gates and
required inputs. Synthetic acceptance cannot establish real-trade readiness.
The smallest next human step is to supply one permission-cleared, sanitized broker
sample with independently reviewed expected balances, dates, identities and lot
facts; entitled FMP responses require separate rights/freshness review. This gate
does not block the synthetic handoff. Stop here unless the human requests new work.
