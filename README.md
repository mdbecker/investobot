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

[Complete working examples](docs/workflows.md) cover synchronization, tax-loss
harvesting, fund comparisons, three alternative targets, plan comparison,
reports and exact executed lots. [Agent instructions](docs/agent-usage.md) explain
freshness, unknown data and mutation boundaries.

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
See [data model](docs/data-model.md), [targets](docs/targets.md),
[plans and reports](docs/plans.md), [prompts](docs/prompts.md),
[bonds](docs/bonds.md) and [development rules](AGENTS.md).

```sh
docker compose run --rm -T app uv run --locked pytest
docker compose run --rm -T app uv run ruff check --config pyproject.toml src tests
```

CI builds the same Python 3.12 Docker image and runs locked, offline checks.
No telemetry, cloud ledger, ORM, broker API, LLM integration or background worker
is included. SQLite, Decimal and small deterministic domain modules remain the
foundation.
