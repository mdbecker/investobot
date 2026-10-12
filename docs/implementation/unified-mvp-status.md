# Unified MVP status

Investobot ships a synthetic development preview. The original
[unified specification](../PRD-unified-mvp-2026-10-10.md) retains financial
requirements; the [October 12 addendum](../PRD-mvp-wrap-up-2026-10-12.md)
limits the remaining performance/fuzz work. Current acceptance evidence and
remaining gates belong in [one checklist](wrap-up-status.md).

Implemented domains include exact normalized SQLite accounting, chronological
imports and confirmed activity, tax lots and annual estimated tax-cost limits,
human-reviewed contribution/rebalance/harvest proposals, immutable plans,
actual returns, historical strategy comparison, recursive look-through,
specialist research evidence, text/vector retrieval, portable skills and verified
backup/restore. Tests and synthetic workflows check these behaviors; they do
not establish real-world source accuracy or legal suitability.

Before real use, supply reviewed anonymized Vanguard, Fidelity NetBenefits and
PNC HTML; verify FMP entitlement and sourced dataset coverage; review original
research sources/rights and approved policies, specific lots and wash-sale
uncertainties. Demonstrate the nine dated, sourced workflows or explicit typed
blockers listed in the wrap-up. Import profiles remain PROVISIONAL and live FMP
UNVERIFIED. Missing prices, basis, chronology or permissions stay unknown.
No credentials, trade placement or autonomous investing are supported.

Historical implementation checkpoints remain in Git history rather than a
continually growing current status document.
