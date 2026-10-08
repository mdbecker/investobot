# Invest Copilot
Local deterministic portfolio tooling for a browser-equipped agent. No trades, credentials, telemetry, cloud ledger or LLM calls. The original requirements are preserved in [docs/PRD.md](docs/PRD.md).

## Docker only
Install Docker Desktop yourself if needed. No project dependencies are installed on the host.

```sh
docker compose build
docker compose run --rm app uv run pytest
docker compose run --rm app uv run invest --help
```

## Establish account state
Save account HTML locally, then run these inside the mounted project (use synthetic account aliases, never account numbers):

```sh
docker compose run --rm app invest portfolio import /app/account.html --account taxable --institution vanguard
# Save JSON stdout as snapshot.json; inspect warnings before proceeding.
docker compose run --rm app invest portfolio reconcile /app/snapshot.json
docker compose run --rm app invest portfolio apply /app/snapshot.json
docker compose run --rm app invest portfolio summary
```

Import does not write; apply explicitly accepts normalized state. Raw pages are never stored by the ledger. Keep your own HTML files outside Git. Profiles for Vanguard, Fidelity/NetBenefits and PNC are provisional common table aliases, pending anonymized samples. Dynamic/non-table pages may require manual normalization.

Use Chrome for news, theses, SEC filings and qualitative research. Use the CLI for exact local balances, tax lots, holdings, exposure, time-series math, screens and simulations. Human execution is mandatory. See [agent usage](docs/agent-usage.md), [data model](docs/data-model.md), and [tax limitations](docs/tax-limitations.md).

All successful commands print JSON. Errors print JSON to stderr: 1 invalid input, 2 external data unavailable, 3 inconsistent state, 4 internal error. SQLite data is in the Docker `ledger` volume. Native default paths use platformdirs; `INVEST_DB` overrides the database and `INVEST_CONFIG` overrides the local TOML config path.

## Local inspection
```sh
docker compose up -d
```
Open http://localhost:8765. The page previews imported tables and reconciles changes before explicit acceptance; it never authenticates with institutions. See [inspection guide](docs/inspection.md).

## Structured data setup
Create your own Financial Modeling Prep account and obtain an API key with ETF holdings, fund metadata and adjusted historical-data entitlements. Set `FMP_API_KEY` in a local ignored `.env`, then recreate the container. Keys are never sent to brokerage sites. Tests use synthetic fixtures and need no account or internet. For a clearly labelled offline demonstration set `INVEST_FIXTURES=/app/tests/fixtures/fmp-synthetic.json` on a one-off container. See [sources](docs/data-sources.md) for freshness and entitlement limits.

The complete command workflows are in [docs/workflows.md](docs/workflows.md). Bond inputs and conventions are in [docs/bonds.md](docs/bonds.md). Run style checks with `docker compose run --rm app uv run ruff check --config pyproject.toml src tests`.

## Analysis commands
```sh
docker compose run --rm app invest tax lots
docker compose run --rm app invest portfolio exposure
docker compose run --rm app invest fund compare VTI ITOT
docker compose run --rm app invest market history VTI
docker compose run --rm app invest portfolio risk
docker compose run --rm app invest portfolio simulate /app/local-data/actions.json
docker compose run --rm app invest security screen /app/local-data/filters.json
docker compose run --rm app invest fund search /app/local-data/fund-filters.json
docker compose run --rm app invest fund replacements VTI ITOT SCHB
docker compose run --rm app invest bond analyze /app/local-data/bond.json
docker compose run --rm app invest schema
```

[Discovery](docs/discovery.md) documents supported provider filters and ranking. Replacement scores measure similarity only and never determine substantially-identical tax treatment. All account state and actions remain local.

`market quote TICKER --refresh` retrieves a public FMP quote with source timestamps and a15-minute cache. It does not overwrite canonical portfolio valuations. Household calculations reject mixed currencies without configured FX support. Saved HTML without an explicit snapshot date warns that position timestamps use import date.

## Synthetic acceptance fixtures
Tests include taxable, Traditional IRA, Roth IRA, bank/cash, equity, ETF, mutual fund, bond, multiple lots, recent IRA purchases and loss positions in `tests/fixtures/household.json`. They are invented and never loaded into your running ledger automatically. The inspection page starts empty. Provider fixture mode is explicit and marked SYNTHETIC_FMP_FIXTURE. Live FMP endpoints are implemented but were not exercised with your credentials.
