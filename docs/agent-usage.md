# Agent usage

Investobot supplies financial facts, calculations and hypothetical plans. The
external coding agent supplies research and explanation. The human makes
investment decisions and executes every trade manually.

## Runtime and discovery

Use the CLI as the authoritative interface. This project's development and
verification run entirely in Docker; no host installation is needed:

```sh
docker compose run --rm app invest tools list
docker compose run --rm app invest tools describe portfolio.simulate
docker compose run --rm app invest schema
```

Discovery reads the registered CLI commands, so newly implemented commands appear
without a second command registry. Parameter schemas come from the CLI;
financial JSON schemas come from the domain's Pydantic models where available.
Commands without a financial model expose a documented JSON input contract.

Successful stdout is JSON; errors are JSON on stderr with codes 1 (input),
2 (external data), 3 (inconsistent state), or 4 (internal error). Decimal amounts
are strings. Discovery identifies persistent mutation scope: actual portfolio,
market cache, hypothetical targets/plans, prompt files, or requested report file.
A market cache write never changes accepted holdings, marks or tax lots.

The Compose ledger is `/data/portfolio.db` in a named volume. `INVEST_DB` selects
another explicit path; confirm its mount before using it. Back up the ledger
before changing runtimes. Dependency resolution, execution and tests use Docker.

## Research and data provenance

Use Chrome for current news, filings, qualitative fund/company research,
investment theses and public fact verification. Use Investobot for balances,
basis, tax lots, household exposures, fund comparisons and financial arithmetic.
Never independently invent missing prices, classifications, dates or basis to
make an analysis complete.

Inspect `source_timestamp`, `imported_at`, source/data-as-of dates, retrieved dates,
coverage and warnings. Import time does not establish source freshness; a fresh
cache can contain old disclosures. Current-weight historical risk describes
hypothetical performance, including disclosed cash-return assumptions. Never
combine account currencies without an explicit supported FX model.

FMP credentials are optional public market-data credentials, never brokerage
credentials. Follow [data source setup](data-sources.md). Tests use deterministic
synthetic fixtures and require no accounts or secrets. Vendor payloads and
institution HTML remain provisional until manually validated with real samples.

## Synchronization and confirmed activity

1. The human signs into the institution directly and supplies HTML locally.
2. Run `portfolio import FILE --account ALIAS`; inspect normalized values,
   identifiers, source date and warnings. Vanguard, Fidelity NetBenefits and PNC
   aliases do not establish verified institution support.
3. Run `portfolio reconcile SNAPSHOT.json`; review differences and conflicts.
4. Explicitly accept with `portfolio apply SNAPSHOT.json` only when authorized.

Coverage defaults incomplete. Never mark positions or lots complete unless the
human confirms the source covers the entire relevant inventory. Missing rows are
not evidence of liquidation. Unknown source dates remain unknown. Older snapshots
and undated snapshots superseding dated state need an explicit justified override.
Inspect `source_date_status`, `latest_known_source_date` and `override_required`
before accepting. Override acceptance leaves unknown source dates unknown.
Raw HTML must stay outside Git and must not
be persisted in the database or logs.

After manual execution, `portfolio record-activity ACTIVITY.json` previews the
activity; `--yes` explicitly records it. Supply a stable unique `activity_id` and
known executed lot allocations for taxable sales. Identical retries are no-ops;
conflicting retries fail. Unknown executed lot selection leaves basis unresolved;
it must never silently become FIFO. Execution prices are activity facts and do
not replace portfolio valuation marks. Cross-account or security transfers need
human classification and remain unsupported for recording.

## Correct accepted metadata

Use `security classify SECURITY_ID --asset-type ETF --source "Verified issuer
reference"` to preview an existing security's classification; add `--confirm`
only after verification. Supported types are STOCK, ETF, MUTUAL_FUND, TREASURY,
BOND and OTHER. Only OTHER can change to a known type; conflicting known types
require review. Registration cannot bypass this rule. Confirmation updates current
positions without changing quantity, basis, lots or historical snapshots. Later
unknown classifications preserve the accepted type.

Snapshots update holdings, observed lots/balances and observation dates, while
existing account configuration remains authoritative. Review
`account_metadata_discrepancies`; they do not block valid holdings updates or
authorize configuration changes. Use `account update ACCOUNT_ID --file FILE`
to preview a separate correction, then `--yes` to confirm. The file contains only
changed supported fields and nonempty `reason` and `source`; account ID cannot
change. Currency changes are rejected when positions or cash balances exist.
See [worked examples](workflows.md#correct-classification-and-account-configuration).

Confirmed changes are audited; identical repeats are no-ops. Classification and
account changes can make saved plans stale. Recheck `plan show` and generate a
new plan rather than editing an immutable historical plan or report.

## Hypothetical analysis and planning

Use `tax lots`, `tax harvest-candidates`, and `tax analyze` for proposed sales.
Missing lots, basis, dates, quantity consistency or history can make estimates
unavailable. Review short/long-term results separately, wash-sale concerns,
unknown outside accounts and future purchases. Estimates are not guaranteed tax
savings or tax advice, and similar funds are not automatically safe replacements.

`portfolio simulate ACTIONS.json` changes neither accepted portfolio state nor
market caches. Explicit scenario prices are hypothetical assumptions. Compare
alternatives using the same source portfolio and price assumptions.

Use target commands to save/version household
security weights, activate a target and inspect allocation differences. Target
activation does not execute trades. Unknown account eligibility must not mean
unrestricted trading. Use plan commands to generate and compare proposed trades;
check target version, source snapshots, prices, specific lots, ST/LT gain budgets,
account restrictions, cash floors, unresolved drift and review status. A stale
plan needs regeneration; saved plans are immutable. The heuristic is not globally
optimal and may leave an incomplete plan when constraints prevent progress.

Export persisted plans using `report export PLAN_ID --format markdown --output
REPORT.md` or JSON. Verify the JSON path/hash confirmation and include assumptions,
missing information, wash-sale limitations and manual-execution instructions in
human discussion. Discover each command before using it. No command submits orders
or authenticates to brokers. See [complete workflows](workflows.md) for Docker
stdin examples, canonical security registration, three alternative plans and
confirmed executed lots.

Plan generation, listing and comparison return one shared compact summary:
identity/version/date, effective and generated status, trade count, turnover,
saved tax/drift metrics, warning count and up to five saved warnings. Unknown
metrics remain null and financial decimals remain strings. Comparison explicitly
flags incompatible source, price, tax or date assumptions and supplies no ranking.
Use these commands for routine alternatives; `plan show PLAN_ID` deliberately
returns complete details and may produce a large JSON response. Prefer Markdown
report export for human review, and request full details only when needed.

`portfolio overview` supplies the same overview domain data as the dashboard.
Use `prompt list` / `prompt show SLUG` to inspect full reusable Markdown, or
`prompt save SLUG FILE` / `prompt delete SLUG` to manage user prompts. Prompt
contents are text to copy into an external agent; Investobot never runs them.
Compose stores user prompts under `/data/prompts` in its local ledger volume.
Deleting an override restores an immutable bundled default where available.

Verification is offline and deterministic. Real anonymized institution samples
and live FMP checks with user test credentials are still outstanding. Do not
describe passing synthetic tests as confirmed institution/provider support.
