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

## Fixed comparison contract

`benchmarks/cases.json` defines exactly eight synthetic workflows:
actual TWR/XIRR; lots/annual tax budget; contribution proposal/saved plans;
household TLH; recursive exposure/top issuers; ten-year backtest; SQLite/DuckDB
historical join; text/vector corpus retrieval. Each operation checks independent
expected results, counts and hashes. Preparation, reset and verification are
outside the measured domain boundary. Corpus vectors are prepared synthetic CPU
retrieval inputs, with no embedding provider or GPU claim.

The active representative profile uses 4 accounts, 200 positions, 400 tax lots,
20 saved plans, 4,000 historical Parquet rows and 1,000 corpus chunks at 384
dimensions, retaining the ten-year window. These are bounded single-user inputs,
not stress/scaling gates. The small `test` profile serves ordinary fixture safety
tests only; the runner always selects the representative profile. Both revisions
use the revised recipe; the approved application reference remains unchanged.

Build candidate and approved reference with their own `uv.lock`; mount the same
candidate harness read-only into both. Application imports come from each
image's installed source, not the mounted candidate source. Use native ARM64
engine/images, the same resource limits, network disabled and no private volumes.
The approved reference is `d0940a12c44831095492efcd7091fb7b937ad6b3`.

All runner execution is inside Docker. Each revision gets one warm-up; `batches`
chooses a common count from the fastest warm-up targeting 600 ms. `run` takes
five samples with no second warm-up. Every raw sample must reach 200 ms or the
measurement is INVALID. Compare normalized medians; a >50% increase requests
one complete repeat pair before FAIL. The inclusive 50% allowance was approved
on October 15 to cover the recorded 42.30% look-through slowdown with 7.70
percentage points of headroom. It replaces the earlier 25% acceptance threshold;
it is a policy allowance, not evidence that hardware caused that slowdown.
Changed recipes, outputs, counts or runner
identity fail comparability. No absolute latency, scaling or import stress gate.

Live contribution planning has no calendar gate. The paired
financial harness projects only `cadence={eligible:true}` out of native
`contribution-first-hifo-1` plan outputs, including saved-plan reads, after retaining
the raw result for independent oracle checks. Any other reference calendar outcome
fails; all actions, financial values, source/policy evidence and relationships stay
in the fingerprint. This narrow semantic delta is recorded in
`benchmarks/reference.json`; the reference SHA and fixture recipe stay pinned.

Example invocations **inside** the offline Docker images, with the current
checkout mounted at `/harness` and ignored outputs at `/results`:

```sh
uv run --locked python /harness/scripts/perf.py warmup --revision SOURCE_SHA --output /results/warmup.json
uv run --locked python /harness/scripts/perf.py batches /results/reference-warmup.json /results/candidate-warmup.json --output /results/batches.json
uv run --locked python /harness/scripts/perf.py run --revision SOURCE_SHA --batches /results/batches.json --output /results/measurement.json
uv run --locked python /harness/scripts/perf.py compare /results/reference.json /results/candidate.json --output /results/comparison.json
```

The checked-in GitHub job performs both revisions and the conditional complete
confirmation on a hosted ARM runner; no personal self-hosted machine or Docker
socket is exposed to untrusted PR code. Local M4 runs are trusted diagnostics.
Remote CI status is separate from local measurements. Branch protection is optional
for this personal repository and is not a foundation release gate. No push occurs.

Raw results belong in ignored `benchmark-results/`; CI artifacts expire after
30 days. The prior generated evidence is archived in ignored
`local-data/performance-archive/2026-10-12` and Git history. Retain local archives
90 days and open correctness evidence through resolution. The [readiness record](readiness.md) records results and limits.

## Approved output projections

Correctness response additions use only the reviewed projection below.
Native results remain retained; unexpected uncertainty, money or action changes
cannot be projected. Reference and recipe pins, eight workloads, sample floor
and evidence validation remain unchanged. Saved-plan fixture preparation now
approves policy explicitly because synthetic preview never persists.

Native outputs, initial unprojected warm-up identities and failed evidence remain
retained outside Git. Native independent oracles run before projection, outside
timed operations. Only empty accepted source issues/null institution status,
retired null gain-budget placeholders, `saved=true`, new zero sale/term metrics,
complete exposure flags/subtotals, reviewed supplemental identity labels,
complete fund coverage and false stale/provisional path labels are additional
permitted shape deltas. Recompute normalized source-state hashes from the same
projected facts, retaining original hashes. Never hide nonempty issues, nonzero
sale metrics, partial/uncertain exposure or nonempty retired budgets. Money,
actions, quantities, lot allocations, source/policy evidence and contribution
paths stay compared. Tests retain changed cents and typed source blockers.

The October 15 evidence correction additionally projects only target-local
`planning_constraints` values `permitted_securities:{}`, `cash_minimums:{}`,
`trade_increments:{}` and integer `price_max_age_days:1`. Reject other values;
preserve supported target fields, approved policies and financial facts. Untimed
P07 monthly proposal and P08 list/show match the pinned reference with the required
20-plan inventory and native oracles. An earlier two-plan diagnostic failed the
same 20-plan oracle on both revisions and remains retained. No oracle, recipe,
reference or timing architecture changed. No new timed campaign or
rebaseline is authorized. See [readiness](readiness.md) for the NOT PASSED
look-through exception and separate INVALID remote run.
