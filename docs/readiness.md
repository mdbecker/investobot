# Portfolio readiness

`portfolio check --as-of YYYY-MM-DD` is a read-only preflight over accepted account evidence. It never grants proposal or execution permission. Approved trading and tax policy checks remain separate.

Each account reports independent positions, lots and cash coverage, with source timestamp and age. An empty positions table means complete inventory only when the accepted observation explicitly covers all positions. Matching observed lot quantities does not prove complete lot history. Cash freshness uses its own accepted balance date, not the most recent account import. Evidence-only archived observations do not replace accepted coverage.

Freshness is `UNKNOWN`, `FUTURE` or `DATED`. `DATED` reports calendar age without asserting that the evidence meets a trading policy's age limit. Source hashes and import timestamps remain provenance; imports cannot establish source freshness. Future account observations also affect empty inventories.

Typed issues include calculation, proposal and execution-review gates and concrete next human actions. Missing inventory, cash or valuation chronology blocks complete valuation calculations. Incomplete lots or activity history require review for the affected tax/performance domains without claiming that already known valuation marks are unavailable. Mixed REAL/SYNTHETIC evidence cannot authorize proposals. Readiness does not invent balances, lots, prices or policy approval and does not mutate the ledger.
