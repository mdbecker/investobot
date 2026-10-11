# Paired 20-plan baseline measurement

The PRD's ≤2× elapsed-time and size regression gate passed for the measured
`89798cf` image against the original local `5120897` source. Both unchanged
version-specific benchmark drivers ran sequentially in fresh offline containers
on the same Docker hardware, without a source bind mount or private ledger.
This is local measurement evidence, not remote CI or a claim about later images.

The baseline image's entire `src/` tree, benchmark driver and synthetic market
fixture matched the pinned local Git archive byte-for-byte. Baseline/current
financial fixture SHA was
`04478eb4a40c7d23efb3a006c106bd111e519aa70471c32278cd1422cacc0acd`:
10 accounts, 100 securities, 1,000 positions, 2,000 lots and 200 snapshots.
Canonical hashing retained financial inputs and source dates while excluding
generated timestamps, storage representations and added source-precision metadata.
The market fixture also had identical SHA. Each driver generated 20 actual plans;
the original table was `plans`, and the normalized implementation used `plan_runs`.

| Metric | Original | Current | Current/original |
|---|---:|---:|---:|
| Generate 20 plans | 1.648 s | 1.285 s | 0.780× |
| List 20 plans | 0.0400 s | 0.0229 s | 0.572× |
| Compare 20 plans | 0.0411 s | 0.0241 s | 0.588× |
| Database growth | 10,493,952 bytes | 8,622,080 bytes | 0.822× |
| Average plan detail | 479,184.9 bytes | 479,338.9 bytes | 1.000× |
| Average summary | 601.95 bytes | 729.95 bytes | 1.213× |

The hardware fingerprint matched: ARM64, 16 visible CPUs, 8,216,731,648 kernel
physical memory bytes, Python 3.12.12 and Linux 6.12.5-linuxkit/glibc 2.36.
Exact image hashes, driver hashes, complete raw reports, query plans and ratios
are retained in [benchmark-plan-comparison.json](benchmark-plan-comparison.json).

This is one sequential paired sample per version. Host scheduling and OS cache
were not controlled; no cold-cache or fixed throughput claim is made. The
existing original timed-save wrapper was retained unchanged. A preliminary
concurrent pair was discarded from gate calculations to avoid paired contention.
Run again on identical hardware/fixtures when storage or planning changes could
materially affect these workloads. The separate 100,000-chunk search benchmark
measures a different requirement and is not covered by this gate.
