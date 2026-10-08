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
