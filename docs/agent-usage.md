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

Native CLI execution is also available for users who deliberately choose a local
Python environment (`uv sync --locked`, then `uv run invest ...`). To share a
ledger, explicitly configure `INVEST_DB` in both environments: the container path
must refer to the same mounted file as the host path. The default Compose ledger
is `/data/portfolio.db` in a named volume; a host default is a different location.
Back up and choose the database deliberately before changing runtimes. Dependency
resolution, execution and tests for this implementation use Docker only.

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
need an explicit justified override. Raw HTML must stay outside Git and must not
be persisted in the database or logs.

After manual execution, `portfolio record-activity ACTIVITY.json` previews the
activity; `--yes` explicitly records it. Supply a stable unique `activity_id` and
known executed lot allocations for taxable sales. Identical retries are no-ops;
conflicting retries fail. Unknown executed lot selection leaves basis unresolved;
it must never silently become FIFO. Execution prices are activity facts and do
not replace portfolio valuation marks. Cross-account or security transfers need
human classification and remain unsupported for recording.

## Hypothetical analysis and planning

Use `tax lots`, `tax harvest-candidates`, and `tax analyze` for proposed sales.
Missing lots, basis, dates, quantity consistency or history can make estimates
unavailable. Review short/long-term results separately, wash-sale concerns,
unknown outside accounts and future purchases. Estimates are not guaranteed tax
savings or tax advice, and similar funds are not automatically safe replacements.

`portfolio simulate ACTIONS.json` changes neither accepted portfolio state nor
market caches. Explicit scenario prices are hypothetical assumptions. Compare
alternatives using the same source portfolio and price assumptions.

Once available in `tools list`, use target commands to save/version household
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
human discussion. Discover each command before using it; development may expose
these groups incrementally. No command submits orders or authenticates to brokers.
