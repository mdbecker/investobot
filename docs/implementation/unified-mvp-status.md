# Unified MVP rebuild evidence

Specification: [preserved October 10 PRD](../PRD-unified-mvp-2026-10-10.md).
This is an implementation record, not a claim that the rebuild is delivered.
Historical PRDs retain their original contents.

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
or complete policy/planning acceptance. Backtest storage is reserved for immutable
runs; its engine remains outstanding.

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

Vanguard, Fidelity NetBenefits and PNC require reviewed redacted original HTML;
synthetic pages cannot establish institution support. FMP entitlement/endpoints
require the user's manually reviewed live-provider gate. Real-company source
truth, permissions and actual LLM skill-following remain separate human gates.
No GitHub Actions result is claimed; this session never pushes.
