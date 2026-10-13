# Foundation stabilization — 2026-10-12

Historical foundation checkpoint; current execution/storage/prompt ownership is governed by [host-agent PRD](../PRD-mvp-host-agent-docker-persistence-2026-10-12.md) and [current handoff](host-agent-status.md). Measurements below remain unchanged.

Active specification at this checkpoint: [foundation PRD](../PRD-mvp-foundation-stabilization-2026-10-12.md).
Phase 1 is synthetic foundation work; Phase 2 original brokerage/provider validation
has not begun. Historical wrap-up acceptance remains a prior checkpoint.

## Baseline before implementation

On `main`, unchanged production baseline `6af9cc6f7942c3c6554a11eed92637b6f4cdb40c`; all A–F changed scenarios
were authored before production edits. Offline Docker `investobot-review-final`,
mounted source, `INVEST_PROMPTS=/data/prompts`, no private ledger or network:

- Focused foundation/dashboard/policy/decision suite: **46 failed, 96 passed**.
- Additional live-policy schema scenario: **1 failed** (retired calendar fields).
- Expected failures: POST mutation routes and retired UI; missing saved-backtest
  reads; provider call on overview cache miss; calendar/month gates; basisless
  retirement accounting and intake; untyped impossible/taxable sales; CLI parser
  environment mismatch and omitted environment; ignored blocking parser issues;
  false look-through completeness or discarded known values; weekday holiday
  inference and missing unverified-calendar disclosure.
- Green controls preserve contributions-only, explicit invalid environment,
  sourced nested exposure/residual/mismatch, pinned-calendar backtest gaps,
  invalid/duplicate/nonpositive history, approved policy identity, tax/TLH guards,
  accepted balance/plan reads and GET error handling.

The first draft used stored snapshot metadata as an intake payload in two tests;
this was corrected to the public Snapshot fields before the recorded run.
Raw logs: ignored `benchmark-results/foundation-2026-10-12/`; retain 90 days,
and unresolved failure evidence until resolution. No generated logs are tracked.
The referenced review guides were not supplied; review uses the PRD's explicit
intent → architecture → implementation → polish order and smell criteria.

## Implementation

A–F are implemented in local conventional green checkpoints. The dashboard's
write dispatch, import/activity/prompt/workbench UI and mutation-only tests/features
were deleted. It retains accepted facts, targets, plans/reports, actual performance
and saved backtest list/read/compare. Query-only reads and provider-free GETs are
covered against absent, populated and partially valued ledgers.

Proposals have no live calendar/month/drift enforcement. Contributions-only is
still buy-only; rebalance is cash-first. Retirement allocated sales preserve exact
share/cash accounting and null unknown tax facts; taxable basis/date, annual budget,
verified REAL identity, fee, immutable policy and wash-review guards remain.
Explicit CLI environments now reach the parser; acceptance retains blocking parser
evidence. Look-through preserves numeric paths/residuals while disclosing missing
provenance. Market history reports observed adjusted prices and unverified exchange
sessions, preserving pinned backtest missing-session checks.

Integrated review added observed-red checkpoints for mixed invalid adjusted prices
(1 failure), unknown dashboard marks plus active target reads (1 failure), and the
approved benchmark calendar-output projection (1 failure). Their focused checks
are green. Branding remains unchanged. The new numeric fixture explicitly supplies
its valuation date; no source dates are guessed.

Package G reconciles README, active product/workflow/inspection/planning/policy/
architecture/backtest/performance docs, three orchestration skills and AGENTS.md.
Prior PRDs and prior acceptance reports remain historical; this report is current.
The review removed obsolete calendar policy fields and handlers rather than adding
compatibility aliases, frameworks, tables or scheduling layers.

## Integrated acceptance

Final runtime/harness tree: `8c839cf`; image `fecf260aea3a` (native ARM64).
All commands ran inside offline disposable Docker, with
`INVEST_PROMPTS=/data/prompts`, no private volume and no credentials:

- `uv run --locked pytest -q`: **1,344 passed in 47.82 seconds**.
- `uv run --locked ruff check --config pyproject.toml src tests benchmarks scripts fuzz`:
  all checks pass. Viewer JavaScript syntax also passed in Node Docker.
- `uv run --locked python scripts/demo_unified_mvp.py`: **34 actual CLI steps**,
  zero external calls; import/reconcile/accept/performance, approved-policy proposal/
  simulation, TLH, nested look-through, saved/compared backtests and recovery pass.
  Actual lot/cash conservation, unchanged hypothetical facts, artifact hashes and
  restored corpus retrieval are verified. Accepted/restored financial fingerprints
  match: `bcd5845eb4ff9023729a700a34e1a0a4e7a9a8904ea1d3d4593d4373085407d1`.
- Offline cached isolated wheel build, installation into a disposable container
  environment and resource inspection: **all 13 bundled financial skills** present.
  Dependencies came from the baked `/opt/venv`; nothing was installed on the host.
  Initial wheel-check command failures (missing build/runtime dependency paths)
  were corrected without changing project dependencies.
- Exactly **eight paired workflows PASS** against
  `d0940a12c44831095492efcd7091fb7b937ad6b3`: same native engine, ARM64 images,
  2 CPUs/4 GiB, one warm-up and five shared-batch samples. Minimum raw sample
  **330.353 ms**, maximum median increase **0.85%**; no repeat pair required.
  Existing tests still reject a confirmed 26% regression and invalid/short evidence.

| Workflow | Reference median ms | Candidate median ms | Ratio |
|---|---:|---:|---:|
| Actual performance | 1.2740 | 1.2520 | 0.9827 |
| Tax lots / annual budget | 27.9286 | 27.5712 | 0.9872 |
| Contribution / saved plans | 355.5952 | 351.8434 | 0.9894 |
| Household harvest | 0.5496 | 0.5270 | 0.9590 |
| Recursive look-through | 4.5232 | 4.5616 | 1.0085 |
| Ten-year backtest | 89.7938 | 90.1162 | 1.0036 |
| Historical analytical query | 73.5221 | 68.9435 | 0.9377 |
| Corpus retrieval | 15.9050 | 15.8221 | 0.9948 |

Input/output hashes and processed counts match after the approved removal of only
eligible calendar metadata described in `docs/performance.md` and reference JSON.
The reference image source/lock was byte-checked against the pinned local Git tree.
Measurements used image `8a92167575ba` and capture label `8a72739`; the complete
runtime source in that image was subsequently byte-verified against committed
`c5f8853` (the final viewer rendering checkpoint). Final `8c839cf` changes only
benchmark import ordering and documentation; financial runtime is unchanged.
Original capture labels/logs are retained rather than rewritten. The rebuilt final
image receives a fresh full suite/lint check; no timing is invented or borrowed.

SHA-256 reference / candidate / comparison reports:

```text
adbbdf16e2a40f8caf85eb53f9226cede9c44ded53601a3da350902cd95e39b6
db6cf6cf992a5bbbd0f555300483bfeb1e79ef83f9b1120c8cefed82c3cafe06
c07adf53960e87ab728d7e92dbda512eb1919815a9020993dcd5794a672eab30
```

Raw baseline, integrated checks, wheel/build diagnostics and paired reports remain
in ignored `benchmark-results/foundation-2026-10-12/` under the retention above.
Local acceptance is not remote CI evidence. No Git fetch, remote or push was used.
The finite foundation checklist is complete; no further performance/fuzz work is
part of this handoff.

## Human prerequisites and stop scope

Phase 1 uses disposable fictional HTML, ledger facts, histories and corpus evidence.
It needs no credentials. Phase 2 starts after foundation acceptance: human-review
sanitized original Vanguard, Fidelity NetBenefits and PNC pages, validate parser
identities/precision/coverage against originals, then verify live FMP entitlement
and response contracts with the user's own account/key. Follow README and
`docs/data-sources.md`; keep keys/private files ignored and never provide broker
credentials, cookies or trading access. Institution profiles remain PROVISIONAL,
FMP remains UNVERIFIED. No financial/legal readiness follows from synthetic tests.
All material fact changes use the human-authorized agent/CLI workflow; manual trade
execution and wash-sale review remain required. Branch protection is optional.
No host installation, private-volume test, push, new fuzz campaign or trade occurred.
