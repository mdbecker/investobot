# Development evidence
All tests and dependency tools run in Docker. Conventional red/green commits track feature work. Synthetic BDD fixtures need no credentials or internet.

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
