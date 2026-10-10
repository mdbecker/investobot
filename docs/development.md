# Development evidence
All tests and dependency tools run in Docker. Conventional red/green commits track feature work. Synthetic BDD fixtures need no credentials or internet.

## V2.7 implementation evidence

Red commits `8f29ee0`, `8697468`, `e6f589e` and `8193a1e` capture missing skill,
strict models, storage/schema and executable comparison/three-run CLI scenarios.
Query audit red commit `cfdc39e` captures partial strong-identity fallback,
overbroad context reads, missing prior citation links and relabeled-source false
corroboration. After implementation, the frozen full offline mounted-source
Docker suite passes 516 tests and explicit-config Ruff. The three-run integration
retains actual synthetic plan contents/status and full planning inputs unchanged.
Existing political/earnings behavior and skill content remain intact. These
fixtures do not establish real-news accuracy or a GitHub Actions result.

Independent review reproduced missing outcome locators in summaries/deltas and
global-version coupling for the new skill. Red commit `3ead858` preserves both
regressions. Corrections retain explicit status citations and pin the news skill
version independently without changing existing skill content or hashes. The
frozen full offline Docker suite passes 518 tests and Ruff. A separate agent
installed and followed the news skill using the fictional PRD example, preserving
unknown dates and producing fact/catalyst/thesis/question deltas across saved runs.

Final count-contract red commit `43ce1b1` requires warnings to participate in
structured delta counts, including missing baselines. Nested source/fact/segment
reordering also preserves accepted run identity. The full offline mounted-source
suite passes 520 tests and Ruff; the news skill passes the official format
validator with its YAML dependency confined to a disposable Docker container.
Existing earnings and political skill directories are byte-for-byte unchanged.

## Deliberate schema reset

SQLite schema 6 initializes only a fresh database and rejects incompatible older
schemas with a structured inconsistent-state error. It never deletes a database
on startup. Version 2/3/4/5 records, including saved plans and research, are not migrated or converted.
A reset discards all accepted holdings, lots, activity, targets, plans and research in the
selected ledger. Reimport reviewed source observations and recreate targets after
resetting. Keep a private backup first if any information may be needed later.

For Compose, stop the application and remove only the ledger database and its
SQLite sidecars from the mounted data volume after making that decision:

```sh
docker compose stop app
docker compose run --rm --no-deps app sh -c 'rm -f /data/portfolio.db /data/portfolio.db-wal /data/portfolio.db-shm'
docker compose up --build -d
```

This preserves `/data/prompts` and the separate `/opt/venv` dependency volume.
If `INVEST_DB` selects another file, identify its actual mounted path first and
delete only that chosen database and matching sidecars. Do not use
`docker compose down --volumes` for a database-only reset: it also removes prompts
and dependency volumes. The application initializes schema 6 on the next access.

For native installations, stop every process using the ledger. Locate the exact
`INVEST_DB` file or the platformdirs `investobot` data directory, back up anything
needed, then deliberately delete that database and its matching `-wal`/`-shm`
files. Retain the sibling `prompts` directory. Restart using the same selected
path. No native dependency installation is needed for this development workflow;
all verification below uses fresh disposable Docker ledgers.

## PRD v2.3 implementation

The attachment is preserved verbatim in [PRD-v2.3.md](PRD-v2.3.md). Packages proceed
in order: shared baselines/schema, efficient plan queries, planner hot path, then
performance verification. Financial semantics, Decimal precision, explicit
mutations and manual execution remain the governing constraints.

Schema 3 separates `plan_baselines.state_json` from `plans.summary_json` and
`plans.details_json`. Identical source financial inputs share a canonical baseline
hash. Baseline/plan insertion is atomic. Current planning-state reads project
latest observation provenance instead of loading historical snapshot payloads,
and retain confirmed activity needed by existing tax/wash-sale analysis.
Listing/comparison read summaries and assumption hashes, with one current-state
hash per operation. Full retrieval joins one plan to its baseline; report export
uses saved results without live prices or tax recomputation.

The older benchmark results below are historical measurements of previous
schemas, not current performance claims. Package 4 records a fresh isolated run
with the unchanged 10-account/1,000-position/2,000-lot/200-snapshot/20-plan
synthetic workload. Timing targets are observations to evaluate, never brittle CI
limits. Response sizes and shared-baseline reuse are deterministic requirements.
No new accounts, credentials, providers or institution HTML are required for this
optimization. Existing manual institution/provider validation remains separate.

### Shared-baseline benchmark results

Isolated Docker measurement on October 8, 2026, with the unchanged workload and
Python 3.12.12 / Linux 6.12.5-linuxkit aarch64 / glibc 2.36 runtime. The ledger and
report were disposable; no private volume, live API or competing full-workload
job was used. [Raw measurements](benchmark-v2.3.json) retain all byte counts,
timings, environment and SQLite query plans.

| Metric | Schema 3 result | Target |
| --- | ---: | ---: |
| SQLite before / after 20 plans | 12,021,760 / 22,515,712 bytes | — |
| Plan database growth | 10,493,952 bytes (10.01 MiB) | <44 MiB |
| Unique baselines | 1 | 1 |
| Average baseline JSON | 880,417 bytes | — |
| Average summary JSON | 601.95 bytes | — |
| Average plan-specific details JSON | 479,184.9 bytes | — |
| Generate 20 plans | 1.758 seconds | <15 seconds |
| Planning/validation portion | 1.331 seconds | — |
| Persistence portion | 0.427 seconds | — |
| List 20 plans | 0.0424 seconds; 12,090 bytes | <1 second; <128 KiB |
| Compare 20 plans | 0.0448 seconds; 12,283 bytes | <1 second; <128 KiB |
| Retrieve one full plan | 0.0484 seconds | — |
| Markdown export, excluding retrieval | 0.00181 seconds | — |

Incremental storage is about 95.5% below the historical 232,009,728-byte baseline,
meeting the 90% stretch goal. All documented targets were met in this run.
The same financial inputs and explicit alternative price assumptions were used;
the small initial database-size difference reflects schema/table overhead.
Persistence timing wraps the real save operation and includes baseline hashing,
serialization and the atomic database transaction. Planning is the remaining
generation time, including validation. Timings are single-run observations, not
universal guarantees or OS cold-cache measurements. The legacy measurement key
`average_serialized_plan_bytes` now aliases plan-specific details size; the three
explicit JSON-size fields describe the shared storage layout.

SQLite EXPLAIN confirms list ordering uses `plans_created_idx`, selected
comparison IDs use the plan primary key, and single-plan/baseline lookups use
their primary keys. Comparison uses a temporary B-tree to order the small selected
summary set; no additional index is warranted. These queries select summary or
requested detail columns explicitly and do not load unrelated financial blobs.

Reproduce without mounting the private ledger volume, after building the image:

```sh
docker build --tag investobot-ci .
docker run --rm --network none -e INVEST_PROMPTS=/data/prompts investobot-ci uv run --locked python scripts/benchmark_plan_storage.py
```

The script uses `time.perf_counter()` and cleans its temporary database/report.
Optional `--output` preserves its JSON inside a deliberately selected mounted
output directory. The full-workload BDD verifies one baseline, storage/response
size bounds, unchanged accepted holdings, explicit selected details, two
byte-identical historical reports after a confirmed cash change, stale originals
and a new baseline for subsequent planning. Wall-clock limits are not CI tests.

The planner maintains Decimal value/cash maps and reuses one hypothetical working
copy. Its final authoritative simulation validates incremental balances before
persistence. Exact trade, lot, gain, cash and drift regression fixtures preserve
the existing strategy. Tax activity/lot analysis, shared accounting searches and
final exposure still traverse relevant financial data; larger or more active
households can cost more. No approximation, global cache, new service or financial
algorithm was introduced to meet the measured targets.

Foundation: observed3 missing-ledger failures before implementation; green3. Import consistency:1 expected failure and5 existing-behavior regression passes; green9. Tax/market/inspection: modules absent before implementation; full suite42 green. Exposure/normalization/bonds: expected4+2+4 failures; full suite52 green.

A parallel tax audit wrote new scenarios between the52-test run and the following commit, so that commit also contains red tests. The coordinator then observed3 expected audit failures (retained-share quantity, missing estimate assumptions, unknown tax status); production was unchanged until this red evidence commit. The passing mixed-loss/net-gain audit scenario verifies behavior already implemented. Coordinate test writes at commit boundaries to avoid this race.

Scenario/risk:7 missing-behavior failures observed, full64 green after implementation. Discovery:6 expected missing-module failures; inspection analysis:3 expected missing-endpoint failures; identity/basis/cash/history hardening:4 failures. Full80 green after integration, including3 composite acceptance scenarios. Composite acceptance scenarios intentionally exercise existing functionality and passed without new domain code; they are integration regression evidence rather than new implementation chunks.

Final data hardening:2 exposure/currency and2 quote TTL failures observed before changes; full84 green. Inspection inconsistent-state response:1 expected disconnected-response failure observed and committed before error handling; full85 green plus Ruff checks and locked Docker rebuild. No live FMP credentials were used; institution HTML support remains provisional until samples arrive.

Deployment verification exposed a Docker Desktop nested-mount interaction when cleaning the workspace dependency directory. Added an observed failing runtime-location BDD scenario, then moved dependencies to /opt/venv outside the bind mount. Full86 tests and Ruff passed; the rebuilt running container's `invest portfolio summary` entry point and localhost HTTP response were checked. The repository contains no host virtual environment.

PRD v2 package 1: parser scenarios observed 9 expected failures and 1 existing-behavior pass; synchronization scenarios observed 9 expected failures and 2 regression passes before implementation (red commit f22a108). Completeness defaults to false. Accepted source dates are independent of import time; stale overrides require an audited justification. Missing inventory is retained unless coverage is explicitly complete. Retained lot mismatches are marked unresolved. The attached requirements are preserved verbatim in docs/PRD-v2.md; docs/PRD.md remains unchanged.

PRD v2 package 2: 8 expected failing BDD scenarios committed as 2eae741 before implementation. Stable activity IDs, exact executed lot allocations, unknown-selection unresolved state, transaction/market price separation, fee-inclusive basis and atomic movement rejection implemented. Legacy synthetic confirmed-activity fixtures now explicitly provide IDs. Scenario marks remain explicit hypothetical price assumptions.

PRD v2 package 3: 14 expected tax/exposure failures plus 1 unsafe cross-tax transfer failure were committed in 19d8147. Packages 1–3 then passed all 133 relevant tests; eight separately committed package 4 discovery tests remained intentionally red until this release gate passed. Known synthetic fixture dates were made explicit rather than inferring source freshness in production. Tax calculation now receives gross execution price and exact fees separately; simulation does not round an effective fee-adjusted price.

PRD v2 package 4: five missing-contract failures (a3a1bcc) and three missing-CLI failures (5c57da2) preceded implementation. Tool contracts discover registered Typer commands and reuse Pydantic schemas; adding a command does not require a second input schema registry. Source-date/completeness CLI options and justified stale overrides use the same domain paths as the local UI. Complete integrated suite: 141 tests green in Docker, explicit Ruff clean. Native CLI remains supported by packaging, but this implementation session uses Docker exclusively per user instruction.

PRD v2 package 5: 10 expected missing-target failures and 3 missing CLI/migration failures committed in 0d1f4e5. SQLite version 2 adds targets, immutable target versions and immutable-plan storage without changing old portfolio tables. Canonical security registration stores explicitly sourced metadata without inventing holdings. Target weights are Decimal fractions totaling 1 within 0.000001. Full Docker suite: 154 passed; Ruff clean.

PRD v2 package 6: 15 expected planner failures and 4 report failures committed in b9fe596 before production changes. Plans use the same allocation comparator, tax analyzer, activity transformations and scenario engine as other interfaces. Plans/exports preserve source state, target version and price/tax/account assumptions. Full suite: 173 tests passed in Docker; explicit Ruff clean. No account credentials, broker calls or live FMP credentials were used.

PRD v2 package 7: 13 prompt failures, 5 dashboard failures and 3 API failures (plus 2 existing safety passes) committed in 51d0972 before implementation. Shared domain APIs power CLI and the five-area local dashboard. Prompts are plain text with safe atomic user CRUD and immutable bundled defaults. Full Docker suite: 196 passed, Ruff clean; dashboard JavaScript syntax checked in Docker. The target activation button explicitly identifies latest-version selection when historical versions are being inspected.

PRD v2 package 8: final audit scenarios observed 12 expected failures and 2 regression passes, plus 2 tax and 7 parser failures, before the red commit 5c5316a. Two additional missing-classification/missing-cash failures were observed and committed in 0b0ac56. Hardened duplicate cash/column parsing, explicit complete-lot assertions, valuation-independent generated lot IDs, retirement tax completeness, unknown-date wash-sale analysis, shared normalized/activity validation, basis preservation and contradictory basis rejection, strong identity conflicts, excessive sale fees, stale holding quantities, native loopback binding and persistent Docker prompt storage. Existing synthetic complete-import and post-trade fixtures were corrected to provide internally consistent lot facts. Full Docker suite: 221 passed; explicit-config Ruff clean.

An isolated Docker Playwright browser walked through import → reconcile → accept, target save/activate/diff, plan generation/report download, plain Markdown prompt save/full-text copy and stale-plan display after confirmed activity. It used disposable synthetic data and no brokerage credentials. Browser tooling was installed only inside the disposable browser container. CI builds the Python 3.12 Docker image with uv.lock and runs tests and explicit-config Ruff without network access. No host dependencies were installed and no pushes were attempted.

Manual release gates remain: validate each provisional institution against real anonymized HTML, verify live FMP entitlement/response behavior with a user-provided market-data key, and review tax assumptions and execution fees before manually acting. Synthetic fixtures exercise the API boundary but do not establish institution support or live-provider completeness. Original docs/PRD.md remains preserved.

Final committed-image verification: Docker rebuilt successfully; all 221 tests passed again with network disabled. The running localhost dashboard returned HTTP 200 and the public `invest tools describe plan.generate` entry point returned JSON. Existing Docker ledger volume was retained; the synthetic browser server was removed.

## PRD v2.1 stabilization

The original attachment is preserved in [PRD-v2.1.md](PRD-v2.1.md). Baseline:
221 tests passed in Docker. Red commit `428e156` captures 34 expected new
missing-behavior failures across ledger/CLI/WebUI, plus existing idempotency,
registration-conflict and report-reproducibility passes. One initially undefined
empty-provenance BDD step was repaired and rerun before committing; the resulting
failure was the missing classification operation. Commit `4e053cf` adds the
full synthetic storage scenario, observed failing for its missing fixture builder.

Classification correction, authoritative account metadata and shared freshness
policy use the existing ledger and plan state hashes. Audit arrays are optional
JSON extensions with safe legacy read defaults; SQLite schema version 2 remains
unchanged. A legacy synthetic retirement fixture now explicitly corrects account
metadata before importing positions, matching the new financial boundary. The
core regression gate passed 258 tests before storage measurement. No real pages,
broker credentials, live providers or host dependency installations were used.

Additional review exposed a provenance-only bypass: equal numeric values could
still erase accepted source dates when an undated snapshot was applied. Red
commit `d59eb1c` captures the observed missing override failure. Losing dated
observation provenance counts as a change; previously accepted identical imports
remain no-ops. The shared guard now also protects that case.

All checks use the repository Docker runtime. CI builds the locked Python 3.12
image and runs the full suite and explicit Ruff configuration with networking
disabled. A local reproduction of those CI commands is verification evidence;
GitHub Actions cannot run for this unpushed local branch.

### Saved-plan storage assessment

Disposable synthetic workload: 10 accounts, 1,000 total positions, 2,000 lots
with actual synthetic acquisition dates and exact basis, 20 snapshots per account,
and 20 independently generated alternative plans. The builder seeds validated
normalized records directly to isolate saved-plan cost from repeated HTML parsing.
Production planning, listing, retrieval and report export run unchanged with
offline fixtures. No private ledger or provider API is involved.

Isolated Docker measurement on October 8, 2026 (Python 3.12.12, Linux
6.12.5-linuxkit aarch64, glibc 2.36):

| Metric | Observed result |
| --- | ---: |
| SQLite size before plans (after fixture and target) | 12,009,472 bytes (11.45 MiB) |
| SQLite size after 20 plans | 244,019,200 bytes (232.71 MiB) |
| Growth from saved alternatives | 232,009,728 bytes (221.26 MiB) |
| Average serialized plan JSON | 11,588,638.9 bytes (11.05 MiB) |
| Generate all 20 plans | 44.379 seconds |
| List all plans with current status | 17.866 seconds |
| Retrieve one saved plan with current status | 0.836 seconds |
| Export retrieved plan to Markdown | 0.0018 seconds |

Sizes are actual SQLite file bytes and stored UTF-8 JSON bytes. Timings are one
application call each, using a disposable database, without concurrent benchmark
work; they are observations rather than machine-independent performance limits or
an OS cold-cache benchmark. Export time excludes the separately timed retrieval.
The fixture fixes financial facts, IDs and dates; generated plan UUIDs and creation
timestamps retain normal behavior. Reproduce entirely in Docker:

```sh
docker compose run --rm --no-deps app uv run --locked python scripts/benchmark_plan_storage.py
```

The command emits JSON and removes its disposable database/report. Optional
`--output /app/local-data/storage-assessment.json` preserves measurements in an
ignored directory created by the user. Four BDD scenarios verify readable saved
plans after later snapshots/reopening, byte-identical historical exports,
independent assumptions and access under the full workload.

Full source histories make saved alternatives materially large. Listing is
noticeably slower because its existing per-plan inspection repeatedly loads plan
rows and hashes live state. Retrieval and export succeeded, with no operational
failure; the requested design is retained. Storage/listing optimization remains
separately scoped work, with these measurements as evidence rather than a reason
to introduce compression, new services or an unrequested schema redesign.

## PRD v2.2 agent usability audit

The original attachment is preserved verbatim in [PRD-v2.2.md](PRD-v2.2.md).
Package 1 red commit `f42d6f8` records 16 expected compact-response/discovery
failures and two preservation passes. Additional red commit `8a785f2` records
the full-workload benchmark's missing response-size measurements before extending
the measurement script. Green verification: all 281 tests passed in Docker,
explicit-config Ruff passed, and browser JavaScript syntax passed in a disposable
Node container. Reports retain byte-identical historical JSON and Markdown.

The initial baseline run used an incorrect test-only prompt directory, causing
one runtime configuration failure (262 other tests passed). The final runs use
`INVEST_PROMPTS=/data/prompts` as required by offline CI, in disposable containers
without the private ledger volume. No host packages were installed.

List and compare use SQLite JSON projection and one current-household hash;
generation still returns its full internal plan but exposes a shared summary at
the CLI/WebUI boundary. No schema, stored plan format or financial algorithm was
changed. The benchmark now reports list/compare sizes and wall times; the full
synthetic BDD workload enforces both responses below 128 KiB without timing limits.
The older storage assessment above remains historical baseline evidence; v2.2
addresses retrieval/transmission, not saved-plan storage growth.

Package 2 red commit `945f836` captures six expected missing-review/bypass/contract
failures and eleven preserved-behavior passes. Existing securities now retain
their canonical classification during snapshot acceptance; reconciliation shares
the identity resolver with acceptance and identifies explicit classification
reviews. New securities retain their initially observed type. Confirmed
corrections still use the existing audited operation. Full Docker suite: 294
tests passed; explicit Ruff and browser syntax checks passed. Atomic multi-security
rejection, CUSIP/ISIN/FIGI conflicts, account metadata, source freshness, financial
amounts, history, correction idempotence and plan staleness remain covered.

### Compact response benchmark

Final disposable synthetic measurement on October 8, 2026, using the same full
workload and Python 3.12.12 / Linux aarch64 runtime as the baseline:

| Metric | Observed result |
| --- | ---: |
| List 20 plans | 12,090 bytes; 1.216 seconds |
| Compare 20 plans | 12,283 bytes; 1.229 seconds |
| Retrieve one complete plan | 0.112 seconds |
| Generate all 20 plans | 47.018 seconds |
| Markdown export, excluding retrieval | 0.0025 seconds |
| Database before / after plans | 12,009,472 / 244,019,200 bytes |
| Saved-plan database growth | 232,009,728 bytes |
| Average complete serialized plan | 11,588,638.9 bytes |

Each compact response is below 128 KiB. Listing improved from the historical
17.866-second baseline; comparison has no historical timing baseline. Timings
are observations, not CI thresholds. No other full-workload benchmark ran
concurrently. Database growth and complete plan size match the earlier workload;
storage compression remains outside scope. Reproduce with the Docker command in
the storage assessment above. The script cleans up its synthetic ledger and report.

Package 3 adds a CLI/inspection parity regression that compares identical saved
alternatives and verifies the entire SQLite dump remains unchanged by reads.
It passes on existing behavior, so it is preservation evidence rather than an
expected-red feature. A small projection refactor omits comparison-only price/tax
assumptions from list reads. No financial algorithms or persisted formats change.

The optional in-app browser smoke attempt was blocked with
`net::ERR_BLOCKED_BY_CLIENT` for the disposable loopback site. No browser-rendered
smoke result is claimed for this audit. HTTP inspection BDD, frontend guidance
checks and Docker JavaScript syntax validation provide the automated UI coverage;
the disposable server was removed without touching the persistent ledger.

Final verification reproduced `.github/workflows/ci.yml` locally: a fresh locked
Docker build, `uv sync --locked`, `uv run --locked pytest` (295 passed), and
`uv run --locked ruff check --config pyproject.toml src tests` (clean). Verification
containers ran with `--network none` and `INVEST_PROMPTS=/data/prompts`, without
host dependency installation or private ledger mounts. GitHub Actions itself was
not dispatched because this work stays on local main and is never pushed.

PRD v2.2's code scope is complete. Release still requires anonymized real HTML
validation for Vanguard, Fidelity NetBenefits and PNC, live provider/entitlement
validation using a user-supplied market-data key, and human review of tax/fee
assumptions. Brokerage credentials and automated trade execution remain excluded;
no new setup secrets or services are required by this stabilization release.

### Final v2.3 verification

Red commits `98007c0`, `405ebb3` and `ea8662f` record the observed missing
baseline/schema behavior, missing authoritative consistency rejection, and
missing measurement/projection/fingerprint guarantees. Query preservation tests
in `1f7616c` pass with detail/baseline reads forbidden by SQLite authorization.
The foundational schema change includes query integration so the fresh schema
remains usable by every existing CLI and inspection endpoint.

Final verification reproduced the offline CI workflow in a fresh locked Docker
image: `uv sync --locked`, `uv run --locked pytest` (**309 passed**, 18.82 seconds),
and `uv run --locked ruff check --config pyproject.toml src tests` (clean).
Containers used `--network none` and `INVEST_PROMPTS=/data/prompts`, with no
private ledger volume or host dependency installation. The complete suite covers
CLI/HTTP inspection list, compare, full details and report parity, database
reopen, immutable reports after confirmed activity, concurrent baseline reuse,
unknown financial inputs, exact planner results and cache-write suppression.

One earlier mounted-source run encountered a transient broken pipe in the
existing oversized HTTP-input test (304 passed); its isolated checks and the
full rerun passed. Final CI passed without retries. No new browser-rendered smoke
claim is made; this release's UI verification uses the existing HTTP BDD suite.
All work stays on local `main`; no remote or push operation was performed.

V2.5 adds isolated executive political-contribution research and uses SQLite
schema **4**. Older schema versions, including 3, are rejected without modification.
Do not reset a private ledger to try this optional feature. Use a disposable
container/database for evaluation; stop the app and review the existing deliberate
reset procedure only if the selected data is disposable. Prompt overrides remain
separate and must be preserved. See [political research](political-research.md)
for manual source review and Docker-only commands.

## V2.5 verification

Red commits recorded missing imports/contracts/schema rejection (`0bc6f2a`),
missing queries (`396abdd`), three refund/role/evidence failures (`0315abf`),
normalized-amount idempotence (`2b9a393`) and the decimal-string discovery schema
mismatch (`a7fd003`). Production changes followed those observed failures.

The integrated offline suite passes 350 tests, including 41 political research
checks, and explicit-config Ruff passes. Fixtures are entirely fictional. Tests
cover restricted sources, ambiguous/private inputs, role dates, candidate/PAC
attribution, net linked refunds beyond Decimal context precision, memo/conduit
exclusions, exact normalization, atomic rollback, same-run SQLite references,
compact list projections, large valid input, read-only validation/preview,
immutable reproducibility and unchanged persisted plan status.

The standard Dockerfile builds with locked dependencies. Final checks use
`uv run --locked` offline in fresh image containers with
`INVEST_PROMPTS=/data/prompts`, no source/private-ledger mounts and no `--no-sync`.
A stalled local Docker credential helper was bypassed using a temporary empty
client configuration plus the already installed BuildKit plugin; no credentials
or host packages were changed. A legacy-builder attempt was abandoned because
its handling of the existing multi-source COPY differs from BuildKit. No Dockerfile
change was needed. GitHub Actions has not been run on these unpushed commits.

V2.6 package 1: six political-hardening failures observed and committed in
`90b54ce` before implementation: public locators, contradictory security linkage,
candidate summaries, two ambiguous locators and explicitly sourced ticker aliases.
The full offline Docker suite passes 356 tests and explicit-config Ruff passes.
Schema remains 4 for this package; earnings will introduce schema 5 separately.

V2.6 package 2: missing skill discovery/installation module observed before red
commit `ecba618`; two CLI/migration failures committed in `3308aa7` and missing
trusted political skill provenance in `23ba14c`. Both canonical skills pass the
skill-creator format validator in disposable Docker containers. The frozen full
suite passes 376 tests and Ruff. Installation tests include symlink/traversal
rejection, modified-file confirmation, unrelated user-file preservation and
atomic rollback. Political workflow regression remains green; saved runs pin
trusted skill name/version without redesigning political tables.

V2.6 package 3: missing earnings model observed before red commit `9da3341`;
three type/schema/unknown guidance-date gaps were then observed and committed in
`5739771`. The frozen model package passes 417 full offline Docker tests, including
41 earnings validation checks, and Ruff. The bundled fictional JSON example
validates against the model; this does not validate live SEC research or parsing.

V2.6 package 4: five schema/persistence failures observed before red commit
`77b6a83`. Schema 5 adds shared research runs/sources and earnings-specific
metrics/guidance/findings, with composite same-run foreign keys. Political tables
remain separate. The full offline Docker suite passes 422 tests and Ruff;
preview preserves database bytes, reordered/equivalent inputs are idempotent,
constraint failures roll back all inserts, incompatible schema 4 stays untouched,
and an actual saved synthetic plan retains its stale status and financial inputs.

V2.6 package 5: missing earnings commands/read-only boundaries were observed and
committed in `e3d189b`; missing query implementation was committed in `4c91d77`.
The frozen full offline Docker suite passes 456 tests and Ruff. Saved facts are
queried without loading package JSON for list/summary/compare. Exact changes,
incompatible bases/periods/entities, ambiguous matches, zero/negative baselines,
amended filings and high-precision values are covered. Validation and previews
leave a missing selected database uncreated; canonical identity contradictions
fail without changing an existing database.

Independent V2.6 review found SEC API issuer contradictions, current-period
fiscal-label contradictions and an exact-percentage rounding-warning defect.
Six failing regression/BDD cases were observed before red commit `9fb28a3`.
After corrections, the full offline mounted-source Docker suite passes 462 tests
and Ruff. A separate agent followed the earnings skill using fictional facts and
verified validation, preview without database creation, confirmed history,
high-precision comparison and idempotent reimport. No live disclosures were used.

V2.6 package 6: a fresh `investobot-v26-ci` image passes `uv sync --locked`,
`uv run --locked pytest` (462 tests) and explicit-config Ruff in separate offline
containers, without source bind mounts or private ledger volumes. An offline
wheel build includes both canonical skills; discovery succeeds using only the
extracted wheel outside `/app`. Both skill format validators passed earlier.
No host dependencies were installed and no changes were pushed. GitHub Actions,
live SEC/source review and real institution HTML remain unverified external gates.
