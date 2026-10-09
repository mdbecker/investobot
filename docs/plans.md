# Human-reviewed plans and reports

## Report exports

Export a saved plan with `invest report export PLAN_ID --format markdown --output report.md` or `--format json --output report.json`. The command writes the requested local file and returns JSON containing its absolute path, SHA256 content hash, format and plan ID. Unsupported formats fail before creating a file. Export replaces an existing output atomically; its directory must already exist.

Markdown reports contain the target rationale and version, source snapshot dates, saved price assumptions and timestamps, current/proposed allocations, trades grouped by account, specific taxable lots, ST/LT gains, estimated tax effects, wash-sale limitations, before/after cash, remaining drift, exposure and unresolved constraints. All numbers come from the persisted plan; report export does not recompute prices, taxes or holdings. Missing information is printed as unknown. Weights remain fractions.

JSON exports roundtrip the complete immutable saved plan, including its inputs and provenance. Repeated exports of the same plan are reproducible. Reports show the status saved at generation and are historical: use `invest plan show PLAN_ID` to check the current status, including STALE, before acting.

No report executes trades. Every plan requires a human decision and manual broker execution. Negative estimated tax effects are not guaranteed usable savings; wash-sale adjustments and filing-specific constraints are not automated. Reports contain sensitive portfolio information, so choose an appropriate private local output directory.

## Generate and compare

`invest plan generate --target TARGET_ID --as-of YYYY-MM-DD` saves a new immutable plan. Use `--version N` to pin an older target version, `--name LABEL`, or `--prices prices.json` for explicit dated price assumptions keyed by canonical security ID: `{"SECURITY_ID":{"price":"100","as_of":"2026-10-08","currency":"USD","source":"verified public quote"}}`. Accepted snapshot prices are the default. Dates, currencies and price age are checked; no cached quote silently replaces accepted prices. Generation never updates actual prices or writes public-data caches.

The deterministic heuristic sells overweight eligible retirement positions first, then known taxable lots (MIN_TAX with configured rates, HIFO otherwise), then buys underweight securities with each account's own cash. Positive short-term and long-term gains are capped separately; losses do not increase a budget. Cash floors, household cash targets, excluded positions and permitted investments constrain trades. Stocks, ETFs and mutual funds default to whole units; explicitly verified per-account increments permit fractional units. Individual bonds receive no automatic instructions. Generated trades assume zero fees; check broker fees before manual execution.

`invest plan generate` returns `{"plan": SUMMARY}`; `invest plan list` returns
`{"plans": [SUMMARY, ...]}`. `invest plan compare PLAN_A PLAN_B` returns those
same compact summaries plus compatibility flags for source snapshot, price
assumptions, tax assumptions and analysis date, comparison warnings and
`ranking: null`. There is no invented ranking score. Lists are newest first,
with plan ID as a stable tie-breaker.

Each summary contains `id`, `name`, `target_version_id`, `created_at`, `as_of`,
current `status`, original `generated_status`, `trade_count`, `turnover`,
`tax_summary`, `drift_summary`, `warning_count` and `warnings_preview`.
Tax metrics retain saved short/long-term gain/loss and estimated tax effect.
Drift metrics show maximum absolute remaining weight difference and the number
outside the saved target tolerance. Decimal values are strings; unknown metrics
remain null. The warning preview contains at most the first five saved warnings
in original order. Unknown metrics remain explicit.

These summaries reuse saved calculations; they omit actions, lots, exposure
datasets and portfolio histories. List and compare extract only required fields
from dedicated summary columns and hash the current planning state once per
request. Comparison reads only the selected summaries and assumption hashes.
Financial calculations retain their existing semantics. The dashboard uses the same
summary representation at `/api/plans`, `/api/plans/generate` and
`/api/plans/compare`.

`invest plan show PLAN_ID` intentionally returns the full saved plan, including
source state, assumptions, proposed actions and detailed analyses. Its JSON can
be large. Request it only when those details are needed; prefer Markdown report
export for human review without loading the complete structure into an agent's
conversation. The dashboard's `/api/plans/PLAN_ID` and report endpoint retain
full detail. Compact summaries do not truncate saved records or report exports.

Incomplete eligibility, prices, basis or infeasible targets produce REVIEW_REQUIRED.
READY_FOR_HUMAN_REVIEW still requires a human decision. Changes to actual state
make existing plans STALE at read time; `generated_status` preserves the saved
status. Immutable inputs are retained, and recalculation creates a new plan.
Target activation never executes the actions.

## Shared planning baselines

Alternatives with identical source financial inputs reference one immutable
baseline. It stores current accounts, security identities, holdings, known lots,
cash, confirmed activity history and latest accepted observation provenance.
Historical account snapshots stay in the ledger rather than being embedded in
each plan. Plan details retain pinned targets, assumptions, actions and calculated
results. A changed source portfolio creates a new baseline; historical plans and
reports retain their original inputs.

Staleness compares the baseline ID with a canonical SHA-256 fingerprint of current
planning inputs. Quantities, basis, accepted prices, account/security metadata,
confirmed activity and relevant source provenance participate. Unrelated older
audit history does not. Listing and comparison never deserialize full details or
baselines. Showing a plan or exporting its report loads only that plan and its
referenced baseline. Schema 3 requires a deliberate
[database reset](development.md#deliberate-schema-reset) for older installations.
