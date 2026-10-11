# Unified MVP rebuild evidence

Specification: [preserved October 10 PRD](../PRD-unified-mvp-2026-10-10.md).
This is an implementation record, not a claim that the rebuild is delivered.
Historical PRDs retain their original contents.

## Current completion assessment — October 11

Estimated **85% of offline MVP delivery** is complete. This is a qualitative
full-specification assessment, not a test-count-derived completion measure.
Entries below this section are historical checkpoints and retain their original
pending-work statements; this section supersedes those statements.

- Exact committed image `89798cf` passed all **1,085 tests**, 26.14 seconds,
  with locked dependencies and no network or private ledger volume.
- Storage/recovery, deterministic financial engines, immutable datasets,
  specialist research, text/vector retrieval and all seven portable portfolio
  workflows have integrated acceptance coverage. Passing coverage does not
  establish every requirement in the PRD.
- The actual 100,000-chunk search measurement completed. Its reproducible report
  is `benchmark-unified-100k-2026-10-11.json`; vectors are explicitly fictional
  two-dimensional fixtures, not a production embedding throughput claim.
- The identical-fixture, same-hardware 20-plan comparison passed the ≤2× gate;
  see [paired measurement](benchmark-plan-comparison.md). Measurements apply
  to the recorded images, not arbitrary subsequent changes.
- Dashboard readiness/performance/search parity, safe managed-staging cleanup,
  exact activity retries, reconciliation of confirmed cash/lot effects and
  additional provenance gates and public immutable policy approval now pass
  the integrated mounted-source offline Docker suite: **1,122 tests**, 30.18
  seconds, with Ruff passing. Their observed-red checkpoints precede production
  implementation. Fresh exact-commit image verification remains a release gate.

Remaining software work includes the accepted linked
household cash-transfer lifecycle, further verified-lot/identity lifecycle
checks, consolidated political reporting, compatible semantic-search filtering
and public CLI access, and final documentation,
packaging, recovery demonstrations and exact-release-commit verification.
The remaining audit may identify additional cases; no package is declared
complete solely because its minimum B01–B66 scenarios pass.

Real institution support remains **PROVISIONAL** until reviewed anonymized
Vanguard, Fidelity NetBenefits and PNC HTML is supplied. Entitled live FMP
support remains **UNVERIFIED** until human acceptance. Source rights and actual
external-agent compliance are independent manual gates. No secrets are needed
for offline MVP acceptance; no remote CI result or push is claimed.

### Subsequent integrated checkpoint

Explicit paired household cash transfers, account/household actual-performance
projection, employee/PAC category preservation, consolidated legacy political
coverage and compatible semantic-search CLI access now pass **1,145 tests**,
29.46 seconds, in offline Docker. Ruff passes. These close the corresponding
items above; remaining work is the verified-lot/identity lifecycle audit, runtime
and documentation simplification, and final exact-commit release validation.

## October 11 full specification audit checkpoint

The prior committed tree `d2028ef` was independently built as image
`fdc7149a3ac8`: locked offline verification passed **1,036 tests in 24.32s**
and Ruff. Its wheel built and installed in a disposable offline container;
the installed CLI and all 13 skills imported successfully.

Additional observed red checkpoints cover adjusted tax basis, account/currency
performance, independent cash freshness and inventory completeness, retirement
sale and underweight purchase priority, historical immutable holdings, missing
risk sessions, unsupported backtest assumptions, shared research envelopes,
corporate PAC/employee acceptance, private corpus sources, saved calculation
storage identity, plain bond runtime, authoritative CLI schemas and reproducible
benchmarks. No skips or blocked-only replacement of success workflows were used.
Source-preserving fixture assertions were corrected where they incorrectly
expected a normalized research lexeme or omitted known-at-time holdings evidence.

Mounted-source offline Docker verification now passes **1,085 tests in 25.83s**.
The dependency lock was resolved inside Docker after removing QuantLib; fresh
locked image verification is still required for this checkpoint. Full-corpus
measurement is running separately; its tiny-fixture acceptance is not a claim
about 100,000 chunks. Dashboard parity, orphan cleanup and the identical-data
plan baseline comparison remain release work. Institution and entitled live FMP
validation remain explicit human gates.

## Baseline

- Branch: `main`; source commit `5120897e9e5a314ad50fb242ad1496d976549a92`.
- Offline Docker image: `investobot-unified-baseline`.
- `uv run --locked pytest -q`: **862 passed**, 33.66 seconds.
- `uv run --locked ruff check --config pyproject.toml src tests`: passed.
- Containers have no network and no private ledger volume. No host packages installed.
- The attachment's exact pinned commit
  `d31316c8fbda0c2a5aa27a989c1341bcd1d57a31` was independently archived from
  local Git objects and built without changing `main`: **752 passed**, 29.71
  seconds; locked offline Ruff passed. No remote was contacted. The newer
  starting checkout additionally preserves fund diligence.

## Global red phase

New acceptance files live under `tests/features/mvp/`, grouped by user domain.
Each step uses fixed fictional inputs and disposable SQLite files; only external
network boundaries may be faked. Independent agents own accounting, decision,
and research workflow scenarios; the coordinator owns recovery and datasets.
No production implementation starts until the complete scenario inventory is
observed with valid requirement failures and committed as a test-only checkpoint.
A baseline regression may pass already; it must remain an explicit regression.

Red checkpoint `638a2a5` records the initial recovery/dataset/decision cases.
Checkpoint `b3727cd` records the frozen expanded global suite, including all
minimum B01–B66 cases and focused policy, provenance, recovery and corpus cases.
The final full offline Docker run observed **141 new failures, 862 existing
passes**, 40.35 seconds, with no collection errors; explicit-config Ruff passed.
The [compact manifest](../../tests/evidence/unified-mvp-red.json) records each
diagnostic and exact scenario/fixture hashes. Three independent agents wrote
separate groups; the coordinator reviewed shared contracts and committed them.

| Domain | New executable cases |
| --- | ---: |
| Recovery/storage | 8 |
| Immutable datasets/deployment | 8 |
| Accounting/performance/tax | 45 |
| Planning/look-through/backtests | 36 |
| Research/corpus/portable workflows | 44 |

Observed gaps include missing `db` commands and pinned analytical readers,
untyped provider gaps, an insecure native bind, absent actual performance and
annual budget capabilities, adjusted-basis loss, stale observation overwrite,
and missing portable workflows/search. Failures remain visible; no skip/xfail
or fake internal collaborator makes this a green release.

Fixtures explicitly supply precision, reviewed fictional lot identity, canonical
security IDs and aligned daily dividend-adjusted history. Policy approval is
separate from hypothetical proposals; actual consumption derives from confirmed
events. A real synthetic Parquet fixture was prepared in a disposable Docker
container with DuckDB 1.4.1 before any project dependency changes.

The global red phase preceded all production changes. Schema-identity tests
were committed at `72d6b7c`; preserved regression fixtures now reference the
new physical tables at `18cfeda` without changing their behavioral checks.

## Storage and recovery foundation

Fresh ledgers now use checksum-identified schema 1, typed relational financial
columns, exact decimal text, foreign keys and indexed current balances. Existing
development ledgers are rejected before writer settings or initialization.
Immutable observation evidence remains separate from authoritative balances.
Database commands provide status, online backup, verification, staged restore
with explicit confirmation, and transactional future migrations guarded by a
verified current backup. Application connections share a restore exclusion lock.
See [operations](../operations.md) and [migrations](../migrations.md).

Offline Docker checkpoint: **870 passed**, 20.14 seconds (862 preserved tests
and eight recovery acceptance cases); Ruff passed for source, tests and scripts.
The four later MVP acceptance modules were excluded from this domain checkpoint
because their implementations remain outstanding; this is not full-suite green.
Recovery also passed real disposable artifact corruption and restoration checks.
No private ledger was reset or migrated. Runtime dependencies and skills are
unchanged at this checkpoint.

## Remaining delivery gates

Incremental domain checks: specific-lot adjusted-basis and final-residue cases
pass (two cases), with all 870 foundation/regression cases still passing,
20.89 seconds. Confirmed sale allocations now retain basis, term, realized gain
and fee separately; retries compare the submitted facts rather than derived
fields. Recursive look-through passes eleven frozen cases, retaining residuals,
cycles/depth bounds, dated holdings, issuer evidence and each contributing path.
See [look-through](../lookthrough.md). These checks do not claim CLI integration
or complete policy/planning acceptance. Backtest storage at that checkpoint was
reserved for immutable runs; the engine was implemented at the following checkpoint.

Additional domain checkpoint: strict observation timestamp/unknown-field and
independent provenance cases pass (three). Annual budget/household harvest cases
pass (eleven) using immutable confirmed sale allocations and explicit provenance.
All 870 preserved/recovery cases still pass, 21.19 seconds. Hypothetical immutable
backtests pass seven existing cases plus a new quarterly-session scenario. Its
red was observed against `25dedc4` without the uncommitted engine, then committed
at `9e025c7`. This closes a quarterly coverage gap found during implementation;
historical performance remains hypothetical, not evidence of actual returns.
Ruff passes. See [tax policy](../tax-policy.md) and [backtests](../backtests.md).

Remaining domain implementation, integrated full-suite green, locked offline fresh-image
verification, recovery roundtrip, synthetic CLI demonstration, performance
measurements and current operations docs are outstanding. No new-design ledger
is claimed release-ready yet. No existing ledger has been reset or migrated.

## Current integrated domain checkpoint

Docker checks now pass all 862 preserved regressions (21.39 seconds), eight
recovery cases, and 112 implemented MVP domain cases (2.37 seconds). The latter
run deselects 24 pending scenarios; it is explicitly not full-suite green.
Ruff passes with the repository configuration. Actual historical performance,
source rounding diagnostics, chronology protection, immutable dataset readers,
approved policy proposal engine, strict research envelopes, native vector search
and five-specialty research coverage are implemented. Research reports select
issuer evidence before loading packages and distinguish historical coverage.
The command surface includes dataset pin/list/verify and portfolio research
plan/report; other workflow commands and seven portable skills are being integrated.

Docker builds bake hash-verified DuckDB SQLite and native sqlite-vec binaries.
The sqlite-vec ARM64 wheel could not load, so the build compiles the pinned
official amalgamation inside a disposable build stage and load-tests the result.
Runtime loading verifies the baked manifest; offline operation downloads nothing.
Missing printed precision prevents observation acceptance. Known subtotals remain
separate from unknown household totals, and reported values are never rewritten
to match a rounded printed price.

Pending acceptance includes corporate actions/reinvestment, hypothetical risk
labels, full portable workflow success/blocked paths and complete command
integration. Fresh locked image acceptance and reproducible benchmark evidence
remain outstanding. This checkpoint does not establish live institution/provider
support, source permissions, or financial actionability.

Vanguard, Fidelity NetBenefits and PNC require reviewed redacted original HTML;
synthetic pages cannot establish institution support. FMP entitlement/endpoints
require the user's manually reviewed live-provider gate. Real-company source
truth, permissions and actual LLM skill-following remain separate human gates.
No GitHub Actions result is claimed; this session never pushes.

## October 11 full local green checkpoint

All **1,036 tests pass**, 24.50 seconds, in the offline analytics Docker runtime
with mounted source; Ruff passes. No tests were skipped, marked expected-failure,
or deselected in this run. This includes all fourteen complete portable workflow
success/blocked walkthroughs, the preserved specialist suites, exact arithmetic
above 100 digits, reviewed issuer registration, independent readiness coverage,
and corporate-action lot/basis conservation. Search and confirmed derived-index
rebuild are now discoverable CLI commands. Missing source dates, permissions,
research tasks and screening characteristics return typed review issues.

Confirmed reinvestment records gross distribution, acquisition and fee separately.
Its derived acquisition basis does not establish a verified broker lot identity.
Splits preserve acquisition references and basis; return-of-capital excess or
unknown lot basis requires manual review. The pre-release schema-1 foundation
now includes the normalized split-ratio column. Earlier development foundation
checksums remain rejected without modification; no existing database is migrated
implicitly. Use disposable new ledgers for this rebuild.

Fresh-image `uv run --locked` verification, packaging, reproducible measurements,
and a full-PRD coverage audit remain outstanding. Passing the current suite does
not establish every PRD requirement or real institution/provider/source rights.
