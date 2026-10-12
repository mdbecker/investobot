# Targeted final-review cleanup

The human-provided October 12 review of `2a495eb` reports successful
[Docker CI](https://github.com/mdbecker/investobot/actions/runs/38306786769) and
[performance CI](https://github.com/mdbecker/investobot/actions/runs/38306786709).
Required-check enforcement remains human-owned and is not configured here.

Four bounded changes address its findings:

- Representative fixtures: 4 accounts, 200 positions, 400 lots, 4,000 historical
  rows, 1,000 384-dimensional chunks; retain 20 plans and ten years. Hundreds of
  positions and thousands of source records exercise a plausible single-user
  portfolio/corpus without restoring stress/scaling certification. Small ordinary
  test fixtures remain separate from the fixed runner's active profile.
- Replay: remove unused fuzz seeds. Complete saved scenario JSON is authoritative;
  variation comes from actual operations, values, ordering and evidence gaps.
- Instructions: remove retired scaling/p95/vector/template/controller requirements
  from AGENTS.md; historical decisions belong in PRDs and Git history.
- Fixture tests: expose the disposable fixture connection explicitly and use
  independent SQLite observers, preserving readonly/mutation/cleanup safeguards.

The application reference stays `d0940a12c44831095492efcd7091fb7b937ad6b3`;
both revisions use revised recipe SHA-256
`7878e0b6ab4ce262a88b85e6927eaa7280d1ca04b9ad0d39089b8cfef219b303`.
Exactly eight workflows, one warm-up, five samples, 200 ms floor and confirmed
>25% regression threshold remain. No application finance code, imports or
dependencies changed. No new campaign, framework, host install or push.

## Acceptance

Committed code `98c5dc22264b7573d55de948102f8968331d989d`, ARM64 image
`1f2ab8bcd895`, offline Docker:

- **1,316 tests pass in 46.40 s**, including 49 targeted review checks; Ruff
  passes for source, tests, benchmarks, scripts and fuzz modules.
- The 34-step synthetic CLI demonstration passes exact lot conservation,
  immutable hypothetical facts, artifact/corpus recovery and matching financial
  fingerprints. Offline wheel installation verifies all 13 financial skills.
- **Eight representative paired workflows PASS** on the same native ARM engine,
  2 CPUs/4 GiB, one sequential warm-up and five shared-batch samples. Minimum raw
  sample: **353.982 ms**. Maximum median increase: **3.42%**; no confirmation needed.
  Existing repeated 26% regression and invalid-measurement tests remain green.

| Workflow | Reference median ms | Candidate median ms | Ratio |
|---|---:|---:|---:|
| Actual returns / linked flows | 1.1902 | 1.2308 | 1.03418 |
| Tax lots / annual budget | 25.4835 | 25.7032 | 1.00862 |
| Contribution / saved plans | 337.8067 | 342.6358 | 1.01430 |
| Household TLH | 0.48557 | 0.48155 | 0.99173 |
| Recursive look-through | 4.5974 | 4.5337 | 0.98614 |
| Ten-year backtest | 92.9883 | 89.2023 | 0.95929 |
| Historical analytical join | 71.1757 | 72.4694 | 1.01818 |
| Text/vector corpus retrieval | 15.2718 | 15.4616 | 1.01242 |

Actual inputs include 4 accounts/200 positions/400 lots/8 snapshots, 20 plans,
121 checkpoints/120 flows, 5,220 historical price rows, 4,000 Parquet rows,
1,000 canonical 384-dimensional chunks and 48 selected fund constituents.
Warm-ups took 14.647/14.653 seconds. Worker wall times were 116.122/115.046
seconds; timed operations totaled 26.536/26.544 seconds. Remaining time combines
preparation, resets, verification and cleanup, not isolated preparation. The
complete pair takes about 4.4 minutes excluding Docker startup/builds; sizes were
measured once and retained without restoring stress gates or optimizing imports.

Raw evidence, including excluded overlapping preliminary warm-ups, is ignored
under `benchmark-results/review-2026-10-12`. Retain locally for 90 days and open
correctness evidence until resolution. Reference/candidate/comparison SHA-256:

```text
25f7ba39c53ae9a3fa52908390e0f5b4df55a6c08f109b5a3d3d7ea37084c488
a664355947b4a98bd31e200e1b31510e9b1428a9cd9f686e75e2d04a87ad3ca9
4cc4b543dfac173aa0c5188de7e1142ca97ff0ddf0cc438319026c55e0f1118f
```

These follow-up results are local; no push or new remote CI result is claimed.
Subsequent documentation/capture metadata do not change the tested runtime or
fixture recipe. All four code findings are addressed; infrastructure work stops.

Human next step: configure main branch rules requiring the Docker `test` and
fixed-performance `performance` jobs, using their actual check names shown by
GitHub. Then prioritize reviewed sanitized broker HTML and live FMP coverage;
those remain PROVISIONAL/UNVERIFIED. This review does not approve real trades.
