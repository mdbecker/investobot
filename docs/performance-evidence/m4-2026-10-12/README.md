# Native ARM import investigation

These are actual offline Docker measurements on the user's M4 setup, constrained
to two CPUs and 4 GiB RAM, with numerical threads set to one. They are local
development evidence, not full PR/extended certification or human approval.

`paired-pr-interrupted.json` retains six completed three-revision cases, all
passing: CLI startup, tool list/describe, dashboard overview, HTML preview and
reconciliation. The coordinator deliberately interrupted the run during import
acceptance to investigate its cost. Its `KeyboardInterrupt` failure is an
interruption, not an application defect; remaining coverage is incomplete.

The comparators were reference `7cbf2bed13a0447865403e986662119571217bc6`
(`f3fd16cbffb4`), base `ed0796cf345128ffbe0fc36a7fd9e2cfd237c42b`
(`beae4dc917c5`) and candidate `9881546a18684abebd56215aee977b274903aa55`
(`d717bb68a4c4`). Each image used its own locked application dependencies and
the same archived harness. The first exploratory attempt was interrupted before
checkpoint support existed (exit 130); no timings from that attempt are claimed.

`import-acceptance-before.json` and `import-acceptance-after.json` measure the
same medium fixture: ten accounts, 1,000 positions, 2,000 lots and 200 accepted
snapshots. Each has one warm-up and three fresh observations; preparation,
fixture copies, reset and correctness checks are outside timing.

| Measurement | Before (`9881546`) | After (`2e38c4a`) |
|---|---:|---:|
| Median | 29.556865472 s | 1.635071043 s |
| Maximum | 29.638057723 s | 1.645774708 s |

The after image is `46bc149bcf60`. Logical input/output hashes, processed counts
and persisted bytes agree. Every native financial invariant passes; no records
were omitted. A separate untimed diagnostic profile found 10,130 inventory reads
accounting for 28.868 of 30.752 seconds. The fix reuses transaction-local
inventories and retains the existing central identity resolver and guarded
historical-lot deletes. Red checkpoint `a009b47` recorded ten intended failures
and two controls for bounded reads and preserved full/partial financial facts.

These three observations establish a measured improvement and all measured
imports below the 5-second target; they do not establish a 21-observation p95 or
complete same-runner reference/base/candidate acceptance. Full medium/extended
captures, matched scaling, budget certification and human reference review remain
the next priority. Preserve these original reports alongside later captures.
