# Correctness and simplification handoff - 2026-10-13

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

## Real-source gate

No reviewed Vanguard, Fidelity NetBenefits, PNC HTML or entitled FMP responses were
supplied. Every adapter remains PROVISIONAL; live FMP remains UNVERIFIED. The
[readiness matrix](../readiness.md) records NOT TESTED/BLOCKED human gates and
required inputs. Synthetic acceptance cannot establish real-trade readiness.
