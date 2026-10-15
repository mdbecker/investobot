# Readiness and human gates

This MVP is a development preview. Local synthetic acceptance demonstrates
behavior, not brokerage-source truth, entitlement, tax legality or trade readiness.
The human signs in directly, supplies permission-cleared sanitized samples, reviews
original sources and manually executes trades. No credentials/cookies or raw
financial HTML belong in Git, logs, the ledger or agent requests.

| Source/workflow | State | Required human evidence |
|---|---|---|
| Vanguard HTML | NOT TESTED / adapter PROVISIONAL | Sanitized reviewed original page; expected positions, cash, dates, precision, stable lots and adjusted basis |
| Fidelity NetBenefits 401(k) HTML | NOT TESTED / adapter PROVISIONAL | Exact plan investment identity, permitted inventory and complete cash/position coverage |
| PNC HTML | NOT TESTED / adapter PROVISIONAL | Reviewed balances, dates and explicit transaction classification |
| Live FMP | NOT TESTED / provider UNVERIFIED | Entitled actual response, original dates, exact share class, rights and source freshness |
| Actual real-source performance | NOT TESTED | Complete dated checkpoints/flow history and explicit same-day boundary ordering |
| Real trade proposal | NOT TESTED | Approved immutable policy/target, current sourced prices, permissions, fees and verified saleable lots |
| Tax-loss harvest execution review | NOT TESTED | Household/spouse/IRA/DRIP/outside-account and substantially-identical/future purchase review |

Typed missing evidence remains visible; status cannot be upgraded because fictional
HTML or provider fixtures pass. Preserve independently expected quantities, prices,
basis, dates and source precision before testing each real sample.

Once samples exist, follow [workflows](workflows.md): import, reconcile, explicit
acceptance, subsequent snapshot, confirmed lot lifecycle, actual performance or
its typed blockers, sourced fund exposure, contributions-only/rebalance/conditional
harvest, then online backup/verify/restore. Compare accepted-state fingerprints
around previews, reports, backtests and dashboard GETs. Record each result as
VERIFIED, BLOCKED with actual issue codes, or NOT TESTED; never infer missing flows.

See [Docker/host setup](../README.md), [FMP account and secret setup](data-sources.md),
[private storage and recovery](operations.md), and [current contract](contract.md).

## Current local verification

Runtime/test commit `a40e43a` passed **1,440 tests in 45.61 seconds**, exit 0,
and Ruff passed, exit 0. Verification used native ARM64
`investobot-correctness-final`, current source bound at `/app`, `UV_OFFLINE=1`,
network disabled, dependencies in `/opt/venv` and no private ledger. This checks
bound source, not a newly baked exact-source image, and is local evidence rather
than remote CI certification. The suite covers the inclusive 50% allowance, confirmation above it, paired
ratios across absolute speeds and invalid-evidence rejection. It also includes
the synthetic CLI demonstration,
host bridge/skills, recovery and GET-only viewer behavior.

README JSON was also extracted and exercised through actual CLI discovery,
reconciliation, absent-ledger preview, explicit confirmation, summary and portfolio coverage
check in disposable offline Docker. Preview left the ledger absent. Existing
package configuration/privacy and host Compose persistence checks are reused;
no newly baked wheel is claimed.
No host installation, remote operation, live provider call or push occurred.

## Performance and limits

**Historical PERFORMANCE EXCEPTION — NOT PASSED under the former 25% gate;
not remeasured.** The confirmed recursive
look-through result is reference **4.404951 ms**, candidate **6.268134 ms**,
**+42.30%** on the fixed representative workflow. Candidate reporting additionally
includes provenance/coverage. The approved exception preserves that failed result;
no speedup or broad performance certification is claimed. The owner subsequently
authorized a 50% timing allowance with headroom above that recorded result.
The new gate has not been exercised by a new timed pair or remote CI run;
changing its threshold does not rewrite the historical failure or invalid run.

[CI run 38681163065](https://github.com/mdbecker/investobot/actions/runs/38681163065)
at `5c12c4a` remains INVALID, exit 3, before measurement because warm-up native
workflow evidence differed. The narrowly corrected target-default projection
passed untimed native comparisons/oracles; it does not establish a future remote
result. See [performance rules](performance.md).

The deterministic greedy planner may leave drift and is not globally optimal;
the large CLI remains a maintenance limitation. Further refactoring and real-source
validation require separately scoped work. Historical review guides
`code_review(8).md` and `code_smell_review(9).md` were unavailable; no review against
them is claimed. Stop after the finite cleanup checks; do not launch new campaigns.
