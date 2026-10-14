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
| Actual real-source performance | BLOCKED | Complete dated checkpoints/flow history and explicit same-day boundary ordering |
| Real trade proposal | BLOCKED | Approved immutable policy/target, current sourced prices, permissions, fees and verified saleable lots |
| Tax-loss harvest execution review | BLOCKED | Household/spouse/IRA/DRIP/outside-account and substantially-identical/future purchase review |

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
[private storage and recovery](operations.md), and [local evidence](implementation/correctness-status.md).
