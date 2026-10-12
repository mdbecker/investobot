# Performance and fuzz addendum status

Native acceptance follow-up: red checkpoint `b73e70e` records eight intended
failures for dimension-specific fixture identity. Green `d607b11` hashes the
actual recipe and dimensions in every native scaling report, instead of
inheriting the stress hash. Eighty-two focused contracts and Ruff pass in Docker.
The new capture freezes base `5e70f69` (current main at work start), rather than
reusing an older historical optimization comparator. Full measurement evidence
is recorded below when available; this metadata fix does not establish native
acceptance.

Exact `d607b11` source, archived into native ARM64 image `8c50ba5e6e12`, passed
**1,627 tests in 247.56 seconds** and Ruff offline with no source mounts.

Actual three-revision medium capture completed nine cases: the first eight
passed both comparators; `P02.check` failed the 200 ms batch floor (20 of 21
observations were too short). The next case was deliberately interrupted to
fix calibration. The original report is retained as
`docs/performance-evidence/m4-2026-10-12/paired-pr-d607b11-interrupted.json`.
This is a measured harness blocker, not an application financial defect.

Latest priority: finish native M4 medium/extended acceptance. A certification
audit found that stress results were incorrectly being compared with named
medium absolute budgets, and import acceptance lacked p95 sampling. Red
checkpoint `54ff7f1` records eight intended failures; green `bb345f8` separates
absolute workload contracts, reuses medium scaling/100k-vector evidence and
requires 21 import observations. All 78 focused contracts pass in Docker.
Exact committed-source image `e50df4fe811a` passed **1,619 tests in 245.65
seconds** and Ruff offline, without source bind mounts. Implementation remains about
**90%**; no full native acceptance or reference approval is claimed.

The corrected candidate's 1,000-position import budget now passes: **1.7724 s
p95 across 21 fresh constrained native ARM Docker observations** (median
1.7176 s, maximum 1.7842 s). Identical input/output hashes and all native
financial invariants were verified. Raw evidence is retained in
`docs/performance-evidence/m4-2026-10-12/import-acceptance-p95.json`.
This single-workload result does not certify complete paired/scaling coverage.

After performance acceptance, the next engineering priority is executable fuzz
slow-path investigation: operation timings, matched 1x/4x saved scenarios and
repeated confirmation/minimization. Current fixed harness tests and numerical
triage helpers do not establish that workflow. Live AI campaigns still require
explicit human invocation after performance acceptance.

The original additive specification is preserved in
[`PRD-performance-ai-fuzz-2026-10-10.md`](../PRD-performance-ai-fuzz-2026-10-10.md).
It preserves the unified MVP and strengthens its performance policy.

## Evidence

- MVP reference: `7cbf2bed13a0447865403e986662119571217bc6`.
  Its 1,249 existing tests and lint passed again in offline Docker.
- Global red checkpoint: `f59b5f8`. All 226 missing addendum contracts failed
  intentionally; the existing no-AI-in-CI control passed. No collection errors.
- Performance foundation: all 1,443 MVP/performance tests pass in offline Docker
  (185.62 seconds), including all 114 named workloads and matched-slice tests.
  Exploratory-harness contracts are a separate pending phase; this is not release
  certification or a claim of native paired measurements.
- Additional red checkpoint: `4c7ab7f` recorded four missing scaling contracts
  and two dense-flow failures. Green fix `b2ac5c6` retains every conventional
  flow while resolving the uniquely bracketed root; 23 focused tests passed.

## Remaining acceptance

The checked-in reference metadata records pending human review and capture,
not invented measurements. Run the paired medium and extended suites on the
documented native M4/ARM64 Docker runner, retain their reports, investigate any
offenders, and review the initial reference. The local ARM64 test profile is
diagnostic only. Remote CI and branch-protection results are unverified because
no changes have been pushed.

The fuzz contracts and fixed offline harness are implemented after the green
performance foundation. A real exploratory campaign must be explicitly human-invoked after
performance acceptance. Fixed harness tests do not establish live agent novelty.
No provider keys or brokerage credentials are needed for offline acceptance.

Reviewed real broker HTML, live FMP entitlement and research rights remain the
manual gates listed in the unified MVP status; this addendum does not bypass them.

## Subsequent implementation progress

- Automatic extended paired scaling now measures candidate-only matched 1x/4x
  slices and applies the shared scaling gate, preserving native observations.
- The historical-metrics boundary now calculates one adjusted series instead of
  duplicating whole-fund comparison. Six focused scaling/boundary tests pass.
- The offline fuzz driver, strict schema, retained novelty history, independent
  oracles, local reports, replay, minimization and triage are implemented.
  All 40 fixed harness contracts pass in Docker (25.31 seconds); repository lint
  passes. No AI campaign was launched.
- Final combined verification follows this checkpoint. This remains development
  evidence, not native release certification.

Fixture reuse and the provider/specialty scaling follow-ups are recorded below.
Retain native paired/extended reports before asserting performance acceptance.
The current fuzz
operation adapters cover the fixed campaign; additional adapters are needed for
full P01–P15 exploratory workflow coverage. Five fresh human-invoked campaigns,
coverage/novelty review, native budgets and baseline approval remain unverified.

## Exact committed-source verification

Commit `8524245` was archived with Git and built with locked dependencies into
Docker image `453f16c9683c`. With no source bind mount and networking disabled,
`uv run --locked pytest -q -x` passed **1,485 tests in 202.35 seconds** and Ruff
passed. This includes all existing MVP tests, 114 fixed workload boundaries,
paired scaling-plan contracts and 40 fixed fuzz contracts. These ARM64 diagnostic
results certify functional behavior for that tree, not paired native performance budgets.

Earlier implementation estimate: approximately **85%**, a scope estimate rather
than a measured acceptance score. Remaining engineering and human gates above
prevent describing this PRD as complete. No live AI campaign, host installation,
remote Git operation or push was performed.

## Native M4 and fixture reuse follow-up

The user's native M4 scope supersedes the preserved attachment's x86-64 runner
choice. Red checkpoint `9222bd9` records 39 intended failures and seven existing
controls for the ARM runtime and fixture-reuse follow-up. Implementation is complete at `55f19e7`; exact
final combined green evidence follows below; these reds are not release results.

Verified Docker facts are engine `aarch64`, image `arm64`, container `aarch64`.
No GPU/render device paths are exposed (`/dev/dri`, `/dev/nvidia0`, `/dev/kfd`
or render devices). Current benchmarks measure native CPU algorithms and
retrieval over precomputed synthetic 384-dimensional vectors, without a GPU or
embedding provider. Metal access and GPU adapter acceleration remain unverified
and require future explicit setup and measurement.

Native paired medium/extended reports, absolute budget certification, reviewed
reference capture and remote branch-protection configuration remain outstanding.
The smaller test profile cannot satisfy those gates merely by running on ARM.

### Fixture reuse implementation

The previous fixture-reuse engineering gap is addressed: all 114 boundaries now
prepare one closed checksummed template per case/revision/dimension. Fresh
observations clone and reopen it; initial construction, copying and hydration are
outside timed work. Named volumes are owned, mounted read-only for workers, and
removed between cases and on failure. Raw SQLite backup/reset handles are
explicitly closed. Source/dimension mismatches, corruption and symlinks reject
reuse. The native M4 workflow excludes x86 emulation and targets a configured
self-hosted M4 runner.

Focused Docker verification passed 107 template/runtime/gate contracts. A real
Docker-engine smoke exercised activity append and hybrid retrieval: each template
was built once and reused by two fresh constrained offline containers, with
matching substantive results and no owned volumes left. Full exact-source green
verification is recorded below when complete.

Next priority: audit matched scaling against actual timed record counts before
capturing native performance baselines. Provider history and bounded specialty
packages still need that audit. Broader fuzz adapters and expressly requested
live campaigns follow performance acceptance. GPU embedding integration is
outside this change: the current native ARM image has no exposed GPU devices and
the fixed retrieval workloads invoke no embedding provider.

### Exact ARM committed-source green

Commit `55f19e7a15f4d13a05a7ec7183a56a33e7f77fa6` was archived and built with
locked dependencies as native `linux/arm64` image `236f854973c1`. Without source
bind mounts or networking, `uv run --locked pytest -q -x` passed **1,532 tests
in 246.15 seconds**, and repository Ruff passed. This preserves all MVP and
specialist research behavior while exercising all fixed workload templates.
No host installations, remote Git operations, pushes or live AI campaigns ran.

Fixture reuse and ARM runtime support are complete for this checkpoint. Native
medium/extended performance acceptance remains outstanding; passing reduced
functional fixtures does not certify their budgets. The next engineering task
is scaling accuracy, followed by actual same-M4 reference/base/candidate capture
and human baseline review. Broader fuzz adapters/campaign acceptance remain later
work; GPU embedding integration is deferred because no embedding provider is
currently part of the measured search workloads.

### Scaling accuracy follow-up

Red checkpoints `44740d2`, `36ca9b6` and `b9f8acd` recorded 43, 19 and two
intended failures respectively. Green checkpoints `4ba9fca`, `0efa11e` and
`0c365ea` correct history/evidence growth, native output coverage and replacement
candidate counts. Seventy focused tests and repository lint passed in Docker.

- Provider history scales actual adjusted-price rows; replacement counts exclude
  the subject fund. Selected look-through counts exclude unused vintages.
- Six native specialties scale distinct fictional evidence within legal bounds,
  preserving exact fund coverage and insider correction/duplicate relationships.
  Validation/import counters and complete show identities independently check
  returned coverage, including rejection of missing or incorrect results.
- Reports distinguish processed record growth, larger database context and
  fixed-size controls. Single quotes and fund summaries retain ordinary
  latency/resource/budget checks; their unchanged inputs cannot establish a
  fourfold record-growth ratio. Context pairs retain the existing growth limit.

Estimated implementation progress is now approximately **88%**. This is a scope
estimate, not a percentage of performance gates passed. Native M4 medium and
extended reference/base/candidate measurements are the next most important
unmet requirement: capture actual reports, resolve measured failures, and obtain
human reference review. Broader fuzz adapters and five explicitly invoked fresh
campaigns follow performance acceptance. No live campaign or remote CI result is
claimed, and the provisional real-data/manual gates remain unchanged.

Exact committed-source verification: `0c365eaaf8c0a36a710ab5632ea2eb196686db3a`
was archived and built with locked dependencies into native ARM64 image
`72cac66706d9`. Without source mounts or networking, the full suite passed
**1,596 tests in 245.45 seconds**; repository Ruff passed. Public scaled runner
smokes also passed with 20 history observations and 40 insider evidence rows,
reusing closed templates in fresh workers. These remain functional diagnostics,
not medium/extended budget certification. All work stays on `main`; no host
installations, remote Git operations, pushes or live AI campaigns occurred.

### First actual M4 measurements and import optimization

The first constrained native three-revision capture completed six cases without
regressions, then was deliberately interrupted during import acceptance for
investigation. Atomic checkpoint support (`1a89a4c` red, `9881546` green) retains
the completed evidence and original failure on interruption/cleanup. Partial
coverage never certifies acceptance.

An isolated 1,000-position import measured a 29.5569-second median. Profiling
identified 10,130 repeated inventory reads. After additional red checkpoint
`a009b47` (ten intended failures, two controls), `2e38c4a` reuses transaction-local
inventories while preserving canonical identity resolution, protected exhausted
lots, partial basis and exact accumulation order. Three fresh constrained ARM
observations measured **1.6351 seconds median, 1.6458 seconds maximum**, with
identical logical input/output hashes, processed counts and persisted bytes.
This is about 18x faster, with all three imports below the 5-second target;
it is not complete p95 or release certification.

Original reports and revision/image identities are retained in
[`performance-evidence/m4-2026-10-12`](../performance-evidence/m4-2026-10-12/README.md).
The implementation estimate is now approximately **90%**; full medium/extended
three-revision captures, matched scaling and human reference approval remain
the most important unmet requirement. Broader fuzz coverage/campaign acceptance
follows. No thresholds or approvals were relaxed.

Exact committed-source green: `2e38c4af64ca7bb75e5470ae2e5b3275c5d283aa`
was archived and built as native ARM64 image `46bc149bcf60`. With no source
mounts or networking, **1,611 tests passed in 246.57 seconds**, and repository
Ruff passed. Red/green checkpoints are committed on `main`; no host installs,
Git remote operations, pushes or live AI campaigns ran.
