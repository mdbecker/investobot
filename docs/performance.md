# Actual portfolio performance

Actual performance uses explicit complete dated valuation checkpoints and an
attested external cash-flow history. Missing evidence returns typed unavailable
outcomes rather than zero returns. This calculation never treats current weights
or hypothetical backtests as historical account performance.

TWR links complete intervals around each external flow. A boundary mark must
explicitly say `BEFORE_FLOW` or `AFTER_FLOW`; the paired balance follows from that
mark and the exact cash flow. Two supplied marks must agree with the cash movement.
Missing or ambiguous boundary ordering blocks TWR; no interpolation is performed.
CAGR annualizes supported linked TWR using actual calendar days and 365.25 days per
year. A supported complete total loss produces -100%.

XIRR uses investor signs: deposits negative, withdrawals positive and terminal
value positive. The equation uses actual day differences divided by 365.25. Root
isolation uses disclosed floating-point arithmetic over log rates [-700,700].
One chronological cash-flow sign change proves uniqueness and uses direct
bracketing without a flow-count limit. Other histories retain recursive root
isolation and the explicit review gate above 128 investor flows. No flows are
dropped. Missing or multiple roots leave the rate null. Explicit `investor_cash_flows` may
supply already reviewed investor-sign flows. They are separate from portfolio-sign
external cash movements.

Paired household transfers cancel only with explicit links, distinct accounts,
matching dates and exact opposite amounts. Account-level transfers remain external.
Record a reviewed pair with `invest portfolio record-cash-transfer --file
transfer.json`; add `--confirm` only after reviewing the preview. Required JSON
fields are `transfer_id`, `from_account_id`, `to_account_id`, exact string
`amount`, `currency`, `data_environment`, verified `event_timestamp` and `source`.
Both accounts must exist with known cash, matching provenance/currency and verified
chronological ordering. The pair changes cash and writes both immutable event
legs in one transaction. Identical retries do nothing; conflicting IDs reject
both legs. No security transfer, inferred missing leg or FX conversion is supported.
Retained dividends, interest, purchases, sales, fees and reinvestment are not
external contributions. Their effects must already be represented in complete
checkpoint valuations; they are never added twice. Default results are net of fees.
A gross-fee report requires separately sourced adjusted valuation evidence.

The pure `calculate(payload)` function accepts reporting dates, scope, provenance,
checkpoints, cash flows and explicit coverage. Ledger extraction and CLI routing
supply these facts; the function neither discovers completeness nor changes the
ledger, valuations, caches or saved plans.

## Fixed workload benchmarks

The post-MVP performance suite measures the named operations in
[`benchmarks/cases.json`](../benchmarks/cases.json), grouped into P01–P15.
Coverage means every identified critical workload has a runnable case; it does
not mean every possible input or instruction has been tested. Add a separately
measured case for each new expensive public path in the same change. Cheap paths
need an explicit short reviewed exemption. Faster results with omitted records,
wrong output, missing cases, errors, timeouts or OOM failures fail acceptance.

Use disposable synthetic fixtures only: seed `271828`, fixed UTC clock,
canonical decimal strings and recorded recipe/input hashes. Never mount a private
ledger, research directory, credentials or application data volume. The runner
uses real local application/storage algorithms; no live provider or AI is needed.

For an offline development check, use an already built locked project image:

```sh
docker run --rm --network none \
  -e INVEST_PROMPTS=/data/prompts \
  investobot-unified-analytics \
  uv run --locked python scripts/perf.py coverage

docker run --rm --network none \
  -e INVEST_PROMPTS=/data/prompts \
  investobot-unified-analytics \
  uv run --locked python scripts/perf.py run --suite pr --profile test
```

The reduced `test` profile checks execution and correctness contracts. It cannot
certify medium/stress coverage or release latency. Source development may bind
only the checkout and use `--no-sync` after building its locked image; all
execution and dependency installation remain inside Docker.

The paired orchestration entry point is being integrated as:

```sh
python scripts/perf.py paired --suite pr \
  --images '{"reference":"reviewed-reference-image","base":"target-image","candidate":"candidate-image"}' \
  --commits '{"reference":"PINNED_SHA","base":"TARGET_SHA","candidate":"CANDIDATE_SHA"}' \
  --host-root /absolute/disposable/workspace --output paired-pr.json
```

Run this entry point in the documented Docker orchestration environment; the host
root is a disposable work directory, never a private application directory.
`--suite extended` selects the extended measurement policy. Until paired
orchestration and its CI wiring are verified, this example describes the intended
interface rather than evidence of a completed release check.

## Comparison and certification

Measure candidate, current target-branch base and pinned reference on the same
runner with their own locked Docker dependencies and identical inputs. Native
Linux x86-64, two CPUs, 4 GiB RAM, no network and one process at a time are required
for release measurements. Set `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS` and
`MKL_NUM_THREADS` to `1`. Retain runtime, dependency, source and fixture identities
in raw JSON. Cross-machine archived timings are audit evidence, not comparators.

Use one warm-up followed by seven observations per revision in PR mode, with
rotated interleaved revision order. Extended retrieval uses 21 observations and
nearest-rank p95; slow bulk operations use three observations with `p95: null`.
A timed operation or common fixed batch must take at least 200 ms. Normalize
elapsed time by batch repetitions for logical-operation comparisons and budgets;
all three revisions use the same batch count. Each timed mutation starts from
fresh identical state. Peak RSS comes from a fresh observation process. Fixture
preparation and Docker startup are outside timing unless explicitly named; CLI
startup remains a separate case. Warm-process measurements make no cold OS-cache
claim.

Fail when raw median elapsed time, peak RSS, persisted bytes or temporary bytes
exceed either comparator by **more than 25%**. Extended retrieval p95 fails above
**35%** growth. Exact threshold ties pass; displayed rounding never decides.
Storage includes the defined SQLite/WAL checkpoint and referenced Parquet/index
artifacts, excluding benchmark logs. Matched 1×/4× approximately linear workloads
fail above 6× elapsed growth. Nonlinear exceptions require a documented complexity
and measured alternative bound, not a waiver for a slow implementation.

A regression provisionally fails and receives exactly one complete fresh paired
retry after cooling. A second breach or any invalid output remains a failure.
A passing retry records `NOISY_FIRST_MEASUREMENT` with both measurements retained;
repeated noise must be addressed before release.

Certification also enforces constrained-runner engineering budgets:

| Workload | Budget |
|---|---:|
| Routine interactive reads/preflight/list/search; 100k vector top-10 | 2 s p95 |
| 1,000-position import/reconcile and actual performance | 5 s p95 |
| 1,000-position proposal/harvest/look-through/top issuers | 10 s p95 |
| 10-year/three-target backtest; 500k-row historical query | 30 s per run |
| 100k-vector rebuild | 180 s |
| Backup plus verification or restore of 200 MiB | 120 s |

These are acceptance budgets, not historical measurement claims. Optimize and
remeasure failures; never certify by inflating a baseline or relaxing coverage.

## Reference and outstanding operator gates

[`benchmarks/reference.json`](../benchmarks/reference.json) pins the actual
post-MVP green commit `7cbf2bed13a0447865403e986662119571217bc6`. Its measurement
capture is **PENDING_CONSTRAINED_RUNNER**, with **PENDING_HUMAN_REVIEW** approval.
No reference timings have been invented. The reference revision must execute the
same fixed workload; incompatible new cases need explicit versioned capture,
while all previously comparable cases remain gated.

Reference/recipe changes require a separate explicitly reviewed performance
rebaseline change, reasons for incompatibility, before/after raw reports and
retained historical evidence. Self-asserted approval inside result JSON grants
no permission. An optimization alone does not require rebaselining.

Repository administrators must manually configure branch protection to require
the fixed PR performance check. PR and extended measurement limits are 20 and
60 minutes respectively; fixture/image preparation remains visible separately.
Nightly and pre-release extended failures block release. Native platform capture,
absolute budgets, paired CI execution and administrator configuration remain
pending until actual evidence is recorded. Local passing gate tests do not imply
remote CI or release certification.

Exploratory AI fuzzing belongs to the subsequent addendum after this performance
foundation is complete. It requires explicit local human invocation; fixed CI
benchmarks never launch an agent or an exploratory campaign.
