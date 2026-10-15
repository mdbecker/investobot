# Investobot MVP PRD — Completion and Scope-Control Addendum

**Date:** 2026-10-14  
**Applies to:** `investobot_mvp_correctness_simplification_prd_2026-10-13.md` ("the MVP PRD"), including its dependencies.  
**Status:** Authoritative amendment for the **already-in-progress** implementation. **Do not restart work or redo completed red/green phases.**

## 1. Decision and precedence

**Finish and hand off the substantially implemented MVP now.** The goal is a correct, understandable, maintainable single-user investment assistant, not exhaustive optimization or indefinite certification. This addendum **supersedes conflicting final-acceptance, performance, re-review, and completion requirements** in the MVP PRD and earlier PRDs. All substantive financial correctness, provenance, deterministic behavior, nonmutation, explicit approval, recovery, and host-agent/Docker boundaries remain mandatory.

The original A–F scope and observed red-first BDD work are accepted as the implementation baseline; do not recreate checkpoints or rewrite already passing tests. Package G **cannot be completed without human-reviewed real broker/provider samples** and is a separately recorded **NOT TESTED / NOT VERIFIED** live-use gate, **not a blocker to the synthetic MVP handoff**. This is not approval for real trading or unsupervised use.

## 2. Finish only material correctness work already identified

Complete and verify the *specific* open correctness issues already demonstrated by failing tests, including, if still unresolved:

- Accepted source blockers must propagate to conditional tax-loss-harvesting decisions, as they do to planning.
- Large-value financial summaries must preserve exact Decimal cents; no context-dependent loss of precision.
- Partial imports must not claim complete evidence, and repeated identical imports must retain the relevant source diagnostics.
- Correct any remaining stale regression expectation **only if** it conflicts with an independently verified, intentionally changed public contract; never adjust expected financial results merely to make a test pass.

Preserve the original MVP PRD's invariants: one canonical exposure engine and planner, correct lot/fee/tax arithmetic, stable security and receipt identity, explicit accepted-state writes, deterministic results, typed unknowns/blockers, no fabricated values or chronology, recoverable ledger state, and a read-only/no-network dashboard. Fix a new issue only if an existing final check reveals a **demonstrated material correctness, data-integrity, safety, or operational blocker**. Write a genuine failing domain-level BDD regression first for newly demonstrated behavior; behavior-preserving cleanup does **not** require manufactured red tests.

**Stop looking for further improvements.** No new speculative edge-case campaigns, open-ended code-smell hunts, unrelated cleanups, broad CLI/module reorganizations, abstractions, frameworks, test harnesses, or documentation expansions. Apply the review guides' intent → architecture → implementation → polish hierarchy, but use them to assess *touched changes*, not to generate new projects. Fix obvious dead/duplicated code introduced by these changes; record unrelated minor nits for later.

## 3. Performance: explicit one-time acceptance exception

The existing eight-workflow benchmark, five-sample paired measurement, repeat-confirmation, and >25% regression guard came from earlier PRDs. **For this implementation only, the confirmed look-through exposure slowdown is an explicitly approved, documented acceptance exception.** The benchmark suite and threshold may remain as they are; do **not** rerun the eight cases, run additional confirmation pairs, profile further, optimize for a synthetic score, change benchmark references/fingerprints, or weaken/delete/skip a failing performance gate merely to claim success.

Report the measured **reference and candidate absolute runtimes**, slowdown percentage, fixture/workload, and whether the old and new paths perform equivalent work. In particular, new source-provenance and contribution-path reporting must not be deleted to recover speed. If comparable numerical outputs or financial behavior differ unexpectedly, that is a **correctness issue**, not an authorized performance exception; investigate it with focused tests. Intentional response-shape/order changes may be acknowledged without forcing obsolete byte/hash equality, provided relevant financial numbers, identities, issues, and source paths remain correct.

If the current benchmark gate still reports failure, label it **PERFORMANCE EXCEPTION — NOT PASSED** in the handoff. Do not claim the full performance gate is green. Only reconsider optimization if an existing representative workflow visibly fails to complete, exhausts resources, or exhibits a concrete operational failure; otherwise defer the measured slowdown. **Do not change CI configuration or the benchmark framework for this exception.**

## 4. Bounded final verification — reuse what already passed

Do not repeatedly rerun broad verification simply because unrelated metadata or documentation changes. Reuse already completed, recorded checks if the relevant production/artifact inputs have not changed. Complete only checks still missing or invalidated by subsequent code changes:

1. Run focused tests for the final correctness fixes, then **one** final full locked offline-Docker pytest run and Ruff check after the last production change. Existing meaningful BDD coverage must pass; do not suppress failures. If a material issue requires another fix, rerun its focused tests and repeat the final full suite once the fix is in place.
2. Run the synthetic end-to-end CLI/host-bridge walkthrough, skill packaging/install, backup/restore, and read-only dashboard smoke tests **once each only if not already successfully demonstrated against the applicable final code/artifact**. Reuse prior valid image, wheel, file-integrity, and workflow results rather than rebuilding or byte-comparing hundreds of files without a concrete reason.
3. Reconcile only the active user-facing documentation and skills affected by changed commands. Preserve one authoritative workflow example, accurate architecture, and candid provisional-provider labels. Do not rewrite historical PRDs or produce elaborate certification evidence.
4. Commit the final verified state and provide a concise handoff. **Do not push. Do not begin another audit after handoff.**

No new work package or subagent investigation should be started. Collect outputs of existing work and resolve only true handoff blockers. If a previously passing check becomes stale due to relevant code changes, rerun **that** check; otherwise do not repeat it for ritual completeness.

## 5. Mandatory handoff and stopping rule

Hand off when the financial/BDD suite, Ruff, and the essential synthetic CLI + recovery + read-only architecture smoke checks are green, and any remaining performance/real-source limitations are accurately documented. A documented performance exception and unavailable real-source fixtures **do not prevent completion**.

The final handoff must state, briefly:

1. Final commit SHA; principal functionality implemented, duplicate paths deleted, and any significant residual smell.
2. Exact last full test/lint results and which host-bridge, skill, dashboard, and backup/restore checks passed (including checks reused from earlier commits/images).
3. Any outstanding *material correctness* defect, distinguished from minor nits; do not call work complete if such a defect remains.
4. The look-through performance exception with **absolute times**, relative change, and explicit failed/passed/not-rerun status; no disguised benchmark rebaseline.
5. Real Vanguard, Fidelity NetBenefits, PNC, and FMP validation status as **NOT TESTED / UNVERIFIED** until reviewed source samples are supplied, with the smallest next human action required.

**After that report, STOP.** Do not launch more benchmarking, profiling, refactoring, tests, audits, or cleanup unless the human specifically asks. The most maintainable MVP is the smallest correct implementation that is finished and understandable—not an indefinitely expanding exercise in assurance.
