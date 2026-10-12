# Investobot

Local portfolio accounting, source-backed research and hypothetical planning.
Humans review evidence, accept facts and execute decisions manually. Investobot
never takes brokerage credentials or places trades.

The [active unified PRD](docs/PRD-unified-mvp-2026-10-10.md) is preserved here.
This is a **development preview** until the software and human gates in the
[implementation record](docs/implementation/unified-mvp-status.md) are complete.
Vanguard, Fidelity NetBenefits and PNC adapters remain **PROVISIONAL**. Live FMP
entitlement and response contracts remain **UNVERIFIED**.

## Start with Docker

Docker is the only required runtime. Install no project packages on the host.

```sh
docker compose build
docker compose up -d
docker compose run --rm -T app invest tools list
docker compose run --rm -T app invest tools describe portfolio.check
```

Open [the local dashboard](http://localhost:8765). Compose publishes only to
`127.0.0.1`; keep this single-user interface local. Its domain results and
confirmation boundaries match the CLI. `docker compose down` stops it.
Do not delete a private data volume to fix an incompatible schema.

SQLite at `/data/portfolio.db` owns accepted financial facts. Prompts live at
`/data/prompts`; dependencies are baked into `/opt/venv` in the image.
`INVEST_DB`, `INVEST_CONFIG` and `INVEST_PROMPTS` select explicit paths.
Fresh normalized ledgers use checksum-identified schema 1. Old development
schemas are rejected unchanged; future migrations require verified backups.

## Safe first use

1. Start with a separate disposable ledger and labelled synthetic fixtures.
2. Preview supplied HTML and reconcile normalized values. Keep private files
   outside Git; raw account HTML is never stored in the ledger.
3. Review source dates, displayed precision, canonical identity and independent
   position, lot and cash coverage before explicitly accepting facts.
4. Run preflight before proposals. Unknown amounts, fees, permissions, provenance
   and tax history remain issues. Approved policies and targets are separate.
5. Save hypothetical alternatives and compare their preserved inputs. Plans show
   staleness after actual changes; saving a plan never trades.
6. After manual execution, record the exact confirmed activity and executed lots.

```sh
docker compose run --rm -T app invest portfolio check --as-of 2026-10-10
docker compose run --rm -T app invest portfolio performance --from 2025-10-10 --to 2026-10-10
docker compose run --rm -T app invest plan list
docker compose run --rm -T app invest research search --query "issuer disclosure"
```

Replace dates with your source/reporting dates. Discover current flags and JSON
schemas with `tools describe`. Success is JSON stdout; financial decimals are
strings. Errors are JSON stderr with codes 1 input, 2 external,
3 inconsistent/blocked state and 4 internal.

## Manual setup and source review

Offline acceptance needs no secrets or accounts. For public market data, create
your own FMP account, verify required entitlements and provide `FMP_API_KEY`
through an ignored `.env` or environment variable. Validate actual entitled
responses before relying on real data. Never supply brokerage credentials,
cookies or sessions. See [source setup](docs/data-sources.md).

Institution verification needs representative anonymized HTML and human review;
synthetic pages do not establish verified support. External agents research
original sources; humans review accuracy and reuse rights. Named contribution
evidence needs an independently reviewed local rights policy. Embeddings need
explicit authorization and compatible model/dimension; no subscription or source
upload occurs by default.

## Recovery and verification

```sh
docker compose run --rm -T app invest db backup --output /data/backups/reviewed.tar
docker compose run --rm -T app invest db verify /data/backups/reviewed.tar
docker compose run --rm -T app invest db restore /data/backups/reviewed.tar
# Only after reviewing the staged restore:
docker compose run --rm -T app invest db restore /data/backups/reviewed.tar --confirm
docker build -t investobot-test .
docker run --rm --network none -e INVEST_PROMPTS=/data/prompts investobot-test uv run --locked pytest -q
docker run --rm --network none -e INVEST_PROMPTS=/data/prompts investobot-test uv run --locked ruff check --config pyproject.toml .
```

Verification uses disposable containers without private ledger volumes.
[Benchmarks](docs/benchmarks-unified-mvp.md) disclose hashes, hardware and limits.
Local evidence is not a remote CI result.

## Documentation

[Product](docs/product.md) · [Architecture](docs/architecture.md) ·
[Data contracts](docs/data-contracts.md) · [Workflows](docs/workflows.md) ·
[Testing](docs/testing.md) · [Skills](docs/skills.md) ·
[Operations](docs/operations.md) · [Tax limitations](docs/tax-limitations.md).
[Performance](docs/performance.md) ·
[Addendum status](docs/implementation/performance-addendum-status.md).

Work stays on `main`, with conventional observed red/green commits and no remote
Git operations. Historical specifications remain unmodified references; the
unified PRD governs financial behavior; the [October 12 wrap-up](docs/PRD-mvp-wrap-up-2026-10-12.md)
supersedes older performance/campaign requirements. Refactors use existing green
tests; new behavior and confirmed bugs require red-first tests. See [project rules](AGENTS.md).

The [local agent fuzzing guide](docs/agent-fuzzing.md) documents safe data-only
adversarial exploration, replay and actionable reports. Fixed regressions run
offline in CI; generated exploration requires an explicit human request.
