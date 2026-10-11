# Unified offline benchmark

Run the driver in the pinned analytical image with networking disabled and no
private ledger volume. It ignores `INVEST_DB`, creates a disposable synthetic
workspace, measures real SQLite/DuckDB/sqlite-vec operations, and removes the
workspace before reporting. Output is JSON stdout; `--output PATH` optionally
saves the same measured report.

```sh
docker run --rm --network none -v "$PWD:/app" -e INVEST_PROMPTS=/data/prompts \
  investobot-unified-analytics uv run --no-sync python \
  scripts/benchmark_unified_mvp.py --chunks 12 --queries 3
```

The default is 100,000 permitted fictional chunks and 20 repeated top-10 queries.
Omit `--chunks` for the required manual corpus measurement. The small acceptance
test runs twice and verifies fixture hashes and observable results without a
wall-clock limit.

Measured workloads include fresh ledger initialization, supplied fictional HTML
parsing and reconciliation, verified online backup, listing/comparing 20 genuinely
saved plans, a pinned historical Parquet join against a consistent SQLite export,
a hypothetical sourced 20-issuer research universe, corpus/index construction,
and lexical/hybrid vector retrieval p50/p95 latency. Financial state is checked
before/after corpus reads and writes. Plan records retain normal storage identities.

The fixture hash covers exact HTML, reviewed fictional issuer records, immutable
Parquet bytes and every canonical corpus record including its vector. Production
UUIDs and measured timestamps are deliberately excluded from the fixture hash.
Hardware, Python/DuckDB/vector versions, container assumptions, database/index size
and actual elapsed measurements accompany each result. Startup measures database
initialization, not a cold OS or container launch. Queries use warm repeated calls.
Vectors use an explicitly reported two-dimensional fictional unit model; results
do not establish latency for a larger production embedding model. Kernel physical
memory may differ from the container limit.

This driver complements `benchmark_plan_storage.py`; its smaller plan fixture
cannot establish the PRD's ≤2× regression gate against the original 1,000-position
baseline. Run that baseline separately on identical hardware, data and image and
retain both reports before claiming regression acceptance. No throughput numbers
or real-data readiness are inferred from the small acceptance test. Reviewed real
institution samples, FMP entitlement and production embedding permissions remain
manual gates.

## Observed small-run evidence

A disposable ARM64 analytical container run on 2026-10-11 reported Python
3.12.12, DuckDB 1.4.1, sqlite-vec v0.1.6, 16 visible CPUs and 8,216,731,648 kernel
memory bytes. For 12 chunks / 3 queries, fixture SHA was
`2b2a630c9a13fa5a21a63efb87c13b1bdc1d333fb942d97e9d758238206b9d08`.
Observed text p50/p95 was 0.904/0.986 ms; hybrid vector p50/p95 was
1.062/1.125 ms; corpus build was 2.314 ms and total SQLite-related size was
2,056,086 bytes. Both searches returned ten cited hits. Initialization, import,
reconcile, backup, 20-plan list/compare, pinned Parquet join and top-N selection
completed; the financial-state and disposable-cleanup checks passed.
These measurements describe that small run only.

## Full-corpus and paired regression evidence

The actual [100,000-chunk report](implementation/benchmark-unified-100k-2026-10-11.json)
records fixture SHA `f423cb8e33b31e6b74503ebfabde63db4e3b21f898017f5426ff53d3f52da926`,
20 warm top-10 queries, the explicitly fictional two-dimensional model, hardware
and native versions. Corpus construction took 215.018 seconds; total artifact
size was 218,568,542 bytes. Text p50/p95 was 312.044/314.745 ms; hybrid p50/p95
was 548.308/558.056 ms. Financial invariants and disposable cleanup passed.
These measurements apply to that recorded implementation. Model compatibility
filter changes after the measurement require remeasurement before claiming
current-release search latency.

The [same-hardware paired 20-plan measurement](implementation/benchmark-plan-comparison.md)
passed the ≤2× gate against the original local baseline: list 0.572×,
compare 0.588×, database growth 0.822×. Exact images, financial fixture hashes,
raw measurements and the single-pair limitations are retained in the report.
