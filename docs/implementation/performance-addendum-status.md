# Performance and fuzz addendum status

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
