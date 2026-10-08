# Human-reviewed plans and reports

## Report exports

Export a saved plan with `invest report export PLAN_ID --format markdown --output report.md` or `--format json --output report.json`. The command writes the requested local file and returns JSON containing its absolute path, SHA256 content hash, format and plan ID. Unsupported formats fail before creating a file. Export replaces an existing output atomically; its directory must already exist.

Markdown reports contain the target rationale and version, source snapshot dates, saved price assumptions and timestamps, current/proposed allocations, trades grouped by account, specific taxable lots, ST/LT gains, estimated tax effects, wash-sale limitations, before/after cash, remaining drift, exposure and unresolved constraints. All numbers come from the persisted plan; report export does not recompute prices, taxes or holdings. Missing information is printed as unknown. Weights remain fractions.

JSON exports roundtrip the complete immutable saved plan, including its inputs and provenance. Repeated exports of the same plan are reproducible. Reports show the status saved at generation and are historical: use `invest plan show PLAN_ID` to check the current status, including STALE, before acting.

No report executes trades. Every plan requires a human decision and manual broker execution. Negative estimated tax effects are not guaranteed usable savings; wash-sale adjustments and filing-specific constraints are not automated. Reports contain sensitive portfolio information, so choose an appropriate private local output directory.

## Generate and compare

`invest plan generate --target TARGET_ID --as-of YYYY-MM-DD` saves a new immutable plan. Use `--version N` to pin an older target version, `--name LABEL`, or `--prices prices.json` for explicit dated price assumptions keyed by canonical security ID: `{"SECURITY_ID":{"price":"100","as_of":"2026-10-08","currency":"USD","source":"verified public quote"}}`. Accepted snapshot prices are the default. Dates, currencies and price age are checked; no cached quote silently replaces accepted prices. Generation never updates actual prices or writes public-data caches.

The deterministic heuristic sells overweight eligible retirement positions first, then known taxable lots (MIN_TAX with configured rates, HIFO otherwise), then buys underweight securities with each account's own cash. Positive short-term and long-term gains are capped separately; losses do not increase a budget. Cash floors, household cash targets, excluded positions and permitted investments constrain trades. Stocks, ETFs and mutual funds default to whole units; explicitly verified per-account increments permit fractional units. Individual bonds receive no automatic instructions. Generated trades assume zero fees; check broker fees before manual execution.

`invest plan list`, `invest plan show PLAN_ID` and `invest plan compare PLAN_A PLAN_B` show saved alternatives, turnover, trade count, taxes, cash, exposure and remaining drift. Different source hashes, prices, tax rates or analysis dates are disclosed without a ranking score. Incomplete eligibility, prices, basis or infeasible targets produce REVIEW_REQUIRED. READY_FOR_HUMAN_REVIEW still requires a human decision. Changes to actual state make existing plans STALE at read time; immutable inputs are retained, and recalculation creates a new plan. Target activation never executes the actions.
