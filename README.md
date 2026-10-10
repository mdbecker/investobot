# Investobot

Local financial tools for a browser-equipped coding agent: accepted portfolio
facts, tax/exposure analysis, hypothetical targets, proposed manual trades and
reproducible reports. The agent researches and explains; the human decides and
executes. Investobot never accepts brokerage credentials or places trades.

## Agent-first workflow

Run from this checkout with Docker. Discover contracts before supplying private
financial inputs:

```sh
docker compose build
docker compose run --rm -T app invest tools list
docker compose run --rm -T app invest tools describe portfolio.simulate
docker compose run --rm -T app invest portfolio summary
```

1. Import supplied HTML, inspect normalized facts and reconcile changes.
2. Explicitly apply an accepted snapshot; unknown basis/dates stay unknown.
3. Use the CLI for financial calculations and Chrome for current public research.
4. Save multiple security-based targets with explicit account restrictions.
5. Generate and compare hypothetical plans; export reports for human review.
6. After manual execution, explicitly record confirmed activity or accept a later
   snapshot. Target/plan creation never changes actual holdings.

Plan generation, listing and comparison return compact summaries with saved
metrics, current stale status and a short warning preview. `plan show PLAN_ID`
retrieves full details and may return large JSON; prefer Markdown report export
for human review. Saved financial inputs and report contents remain unchanged.
Alternatives reuse one immutable planning baseline containing current financial
facts and observation provenance. Historical snapshots stay in the ledger;
listing/comparison read summaries, while full retrieval loads one selected plan.

[Complete working examples](docs/workflows.md) cover synchronization, tax-loss
harvesting, fund comparisons, three alternative targets, plan comparison,
reports and exact executed lots. [Agent instructions](docs/agent-usage.md) explain
freshness, unknown data and mutation boundaries.

Existing account configuration survives holdings imports. Correct an imported
`OTHER` security with `security classify SECURITY_ID --asset-type ETF --source
"Verified issuer reference"` (preview), then `--confirm` to accept. Use
`account update ACCOUNT_ID --file /app/local-data/changes.json` (preview), then
`--yes` for account configuration changes. See the
[correction workflow](docs/workflows.md#correct-classification-and-account-configuration).
Undated snapshots replacing dated state require `--allow-older` and a nonempty
`--justification`; that override never establishes source freshness.

An import can establish a new security's initial classification. For an existing
`OTHER` security, a known observed type appears in reconciliation's
`classification_reviews`; accepting holdings preserves `OTHER`. Verify the
suggestion and use the preview/confirmed classification workflow above. Known
type contradictions reject snapshot acceptance atomically.

```sh
# HTML stays outside Git; create the ignored local-data directory first.
docker compose run --rm -T app invest portfolio import - \
  --account taxable --institution vanguard --tax-status TAXABLE \
  --as-of 2026-10-08 < local-data/account.html > local-data/snapshot.json
docker compose run --rm -T app invest portfolio reconcile - < local-data/snapshot.json
# Explicit acceptance only after reviewing reconciliation and warnings:
docker compose run --rm -T app invest portfolio apply - < local-data/snapshot.json

docker compose run --rm -T app invest tax harvest-candidates --as-of 2026-10-08
docker compose run --rm -T app invest fund compare VTI ITOT
docker compose run --rm -T app invest target save - < local-data/target.json
docker compose run --rm -T app invest target diff TARGET_ID
docker compose run --rm -T app invest plan generate --target TARGET_ID --as-of 2026-10-08
docker compose run --rm -T app invest plan compare PLAN_A PLAN_B PLAN_C
docker compose run --rm -T app invest report export PLAN_A \
  --format markdown --output /app/local-data/report.md
```

Replace dates with known source/planning dates and IDs with values returned by the
CLI. Source dates cannot be inferred from import time. Completeness defaults
false; use `--positions-complete` / `--lots-complete` only after confirming full
coverage. Fund tickers above illustrate tool usage, not investment choices.
Unknown eligibility, stale prices or unresolved tax lots can leave a plan
`REVIEW_REQUIRED`. Every plan still requires human review and manual execution.

Success output is JSON. Financial decimals are strings. Errors are JSON on
stderr: 1 invalid input, 2 external data unavailable, 3 inconsistent state,
4 internal error. `invest schema` documents command inputs, output contracts
and persistent mutation scopes.

## Runtime and local dashboard

No host project installation is needed. Dependencies and testing run in Docker;
Python dependencies live at `/opt/venv` in the `runtime_dependencies` volume.
Compose stores accepted state at `/data/portfolio.db` in the `ledger` volume.
The application/distribution name is Investobot / `investobot`; the CLI is `invest`.

```sh
docker compose up --build -d
```

Open [the local dashboard](http://localhost:8765): Overview, Targets, Plans,
Prompt Library and Import & Reconcile, plus secondary activity and analysis tools.
It displays the same domain calculations as the CLI, copies plain Markdown
prompts and never launches agents or submits orders. Compose publishes only to
host loopback; never expose this unauthenticated single-user tool publicly.
See [inspection](docs/inspection.md). `docker compose down` stops it;
adding `--volumes` deletes persisted data.

Native CLI execution is supported for users who separately choose a local Python
3.12+/uv environment. No host installation was performed for this implementation.
`INVEST_DB`, `INVEST_CONFIG` and `INVEST_PROMPTS` explicitly select database,
configuration and prompt storage. Native defaults use platformdirs `investobot`
directories. A native default and Compose's data volume are different ledgers;
configure both paths to the same mounted file deliberately when sharing state.
Schema 3 requires a fresh ledger; older databases produce a reset error and are
never deleted automatically. Follow the deliberate
[database-reset procedure](docs/development.md#deliberate-schema-reset) before
recreating disposable state. Reset discards holdings, targets and saved plans.

## External data and remaining manual validation

Create your own [FMP account](https://site.financialmodelingprep.com), verify plan
entitlements and set only its public market-data `FMP_API_KEY` in an ignored
`.env` or shell environment. Brokerage credentials, sessions and cookies never
belong in Investobot. Optional tax rates are user assumptions; missing rates
produce gains/losses without invented tax estimates. See
[data sources and setup](docs/data-sources.md) and [tax limitations](docs/tax-limitations.md).

Offline demonstrations explicitly select synthetic fixtures:

```sh
docker compose run --rm -T \
  -e INVEST_FIXTURES=/app/tests/fixtures/fmp-synthetic.json \
  app invest fund compare AAA BBB
```

Fixtures are invented, labelled `SYNTHETIC_FMP_FIXTURE` and never automatically
populate a live ledger. Vanguard, Fidelity NetBenefits and PNC HTML profiles
remain provisional: representative anonymized HTML has not been provided.
Live FMP responses have not been validated with user test credentials. Those
manual integration checks remain open; offline test success does not establish
verified institution support or vendor entitlement/coverage.

## Development and requirements

Work on `main`, with conventional red/green BDD commits and no pushes. Preserve
[original PRD](docs/PRD.md) and [PRD v2](docs/PRD-v2.md). Packages 1–3 gate planning.
The [stabilization PRD v2.1](docs/PRD-v2.1.md) preserves the final MVP requirements.
The [final usability and classification audit PRD v2.2](docs/PRD-v2.2.md)
preserves the attached stabilization scope. Real institution HTML and live
market-data validation remain separate release gates.
The [SQLite performance PRD v2.3](docs/PRD-v2.3.md) preserves the current baseline,
query and planning optimization requirements.
The [final CI stabilization PRD v2.4](docs/PRD-v2.4.md) scopes the oversized HTTP
request regression to the test harness. Its headers-only request must receive
HTTP 413 before any body is sent; the existing 2 MB limit remains unchanged.
Local offline Docker verification does not establish a GitHub Actions result.
The remote CI acceptance gate remains pending while this work stays unpushed.
Local v2.4 verification: 309 tests passed, Ruff passed, and the oversized-request
scenario passed 20 consecutive runs in disposable, offline Docker containers.
No new credentials, API setup, or institution fixtures are needed for this fix.
The unchanged synthetic 20-plan Docker workload now uses one shared baseline:
plan storage grew 10.01 MiB, generation took 1.758 seconds, and list/compare took
about 0.04 seconds with roughly 12 KiB responses. These are measured observations;
see [benchmark evidence and limitations](docs/development.md#shared-baseline-benchmark-results).
See [data model](docs/data-model.md), [targets](docs/targets.md),
[plans and reports](docs/plans.md), [prompts](docs/prompts.md),
[bonds](docs/bonds.md) and [development rules](AGENTS.md).

```sh
docker compose run --rm -T app uv run --locked pytest
docker compose run --rm -T app uv run --locked ruff check --config pyproject.toml src tests
```

CI builds the same Python 3.12 Docker image and runs locked, offline checks.
No telemetry, cloud ledger, ORM, broker API, LLM integration or background worker
is included. SQLite, Decimal and small deterministic domain modules remain the
foundation.

V2.5 adds [executive political-contribution research](docs/political-research.md):
an external-agent research workflow, strict JSON validation, preview/confirmed
immutable imports, compact listing and descriptive totals with evidence.
Named transactions require an independently reviewed local source policy;
agent assertions and `--yes` cannot grant permission. No scraping, FEC client,
political scoring or financial-state changes are introduced.
The [attached V2.5 PRD](docs/PRD-v2.5.md) is preserved. Schema 4 deliberately
rejects older databases without deleting them; evaluate with a disposable ledger
before deciding how to preserve/recreate existing data. Local verification:
350 offline Docker tests and Ruff passed; remote GitHub Actions remains unverified
because no changes were pushed.

V2.6 adds project-local [research skills](docs/research-skills.md) for Codex and
Claude Code, stronger political source/identity checks, and immutable
[earnings research](docs/earnings-research.md) with strict financial facts,
source provenance and conservative Decimal comparisons. The political skill
replaces the bundled political prompt; existing user prompt overrides remain.
The [V2.6 PRD](docs/PRD-v2.6.md) is preserved. Active schema 5 rejects older
databases without changing them. Use a disposable ledger to evaluate it;
preserve existing data before manually selecting a replacement database.
Research validation, previews and reads do not create a missing database.
External research and source review remain human responsibilities; no new API
accounts, secrets or credentials are needed for the offline MVP.
Local V2.6 verification: 462 tests, Ruff and wheel-only skill discovery passed
in offline Docker. Changes remain local; GitHub Actions is unverified.

V2.7 adds [incremental news research](docs/news-research.md) and the
`investobot-news` skill. Source-backed immutable events, catalysts and research
hypotheses support compact prior context and deterministic changes between
selected runs. Repeated articles, title edits and missing coverage cannot become
new developments or implied resolutions. No scheduling, scraping or financial
planning integration is included. The [V2.7 PRD](docs/PRD-v2.7.md) is preserved.
Active schema 9 rejects existing older databases without deleting them; evaluate
with a fresh disposable ledger and preserve private data before any manual reset.
Local V2.7 verification: 521 tests, Ruff, skill format validation and wheel-only
skill discovery passed in Docker. Work remains local; remote CI is unverified.

The [V2.7 continuity addendum](docs/PRD-v2.7-Addendum-Research-Continuity.md)
keeps unresolved historical context across omitted runs, distinguishes
reobservations from discoveries, and exposes cited disputed-claim changes.
Inherited records carry last-observed provenance; unchanged citations cannot
establish fresh verification. Schema 6 and existing accepted research stay intact.
Addendum verification: 540 tests, Ruff, skill format validation and wheel-only
discovery pass in Docker. No host installs or pushes; remote CI remains unverified.

V2.8 adds [competitive research](docs/competitive-research.md): source-backed
market/segment overlaps, attributed advantages/disadvantages, and exact reported
peer matrices. Install `investobot-competitive` through `research skills install`;
validate and preview `research competitive import`, then explicitly accept with
`--yes`. Private-company gaps and incompatible observations remain unknown.
Schema 7 requires a separate fresh ledger; no private data migration or reset.

V2.9 adds [management and insider research](docs/insider-research.md), with the
portable `investobot-management-insiders` skill and `research insiders` commands.
Strict fictional/offline validation, preview and explicit `--yes` acceptance
preserve immutable filing evidence. Reports distinguish P/S purchases/sales from
M/A/F/G and other codes, exclude linked corrections/duplicates and unresolved
rows, and show dated ownership and reported compensation without misleading
totals. No SEC API, credentials or dashboard change is required. Fresh schema 8
rejects existing ledgers without migration or deletion; evaluate with a disposable
database. The [original PRD](docs/PRD-v2.9.md) and
[verification record](docs/v2.9-verification.md) preserve scope and release gates.

The [V2.9 amendment addendum](docs/PRD-v2.9-Addendum-Amendment-Corrections.md)
adds explicitly linked ownership corrections and documented transaction date/code
corrections. Conflicting same-date balances remain uncertain; unsupported amendment
rows never establish a new effective balance. Insider JSON is now **1.1**, its
skill is **1.1.0**, and fresh database schema **9** rejects schema 8 without
migration or deletion. Update new JSON inputs explicitly after reviewing their
sources. Existing accepted evidence is never rewritten. See
[correction verification](docs/v2.9-corrections-verification.md).
