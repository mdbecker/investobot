# Performance reference review proposal

Status: **PENDING HUMAN DECISION**. No reference metadata, recipe, threshold or
timeout has been changed. This proposal does not establish release acceptance.

## Decision

Recommend a separately reviewed local **performance rebaseline** to
`d0940a12c44831095492efcd7091fb7b937ad6b3`, followed by complete native paired
capture. Preserve the original `7cbf2bed13a0447865403e986662119571217bc6`
reference and all raw evidence. Keep current-main comparisons, workload counts,
200 ms floor, 300 ms calibration, relative gates, absolute budgets and 20/60-minute
measurement limits unchanged. The user's no-push instruction means review and
approval must happen locally; no remote PR or branch-protection result is claimed.

The existing reference remains functionally comparable. Rebaselining is proposed
as a reviewed scheduling choice, not because every optimization needs a new
reference. A faster immutable reference also tightens cumulative import regression
detection. Approval would authorize the reference change, not certify all cases.

## Actual evidence

- Identical stress inputs: original reference import **460.992 s**, `77a8515`
  import **23.241 s**, each processing 4,000 positions, 8,000 lots and 40 accounts.
  Input/output hashes and independent financial proofs match. One observation
  each is scheduling evidence, not a confirmed regression or statistical gate.
- Separately matched medium/fourfold inputs, three fresh observations per size:
  `77a8515` medians **1.713/23.784 s** (13.88x growth); history filtering alone
  **0.702/5.854 s** (8.34x); account-local inventory **0.464/1.879 s**
  (4.05x). Final `d0940a1` observations are **0.470/1.885 s**
  (**4.01x**, passing the 6x growth limit). Exact hashes/proofs match between
  revisions at each size. These dimensions differ from the preceding stress
  comparison; the reports must not be merged into full acceptance.
- Raw evidence: `reference-stress-import-feasibility.json`,
  `candidate-stress-import-feasibility.json`, `import-account-history-scaling.json`
  `import-account-inventory-scaling.json` and
  `import-account-inventory-final-scaling.json`, in this directory. Profiles retain
  the offenders and state profiler overhead explicitly.

At the observed reference rate, its stress warm-up plus three import samples
would consume about **31 minutes**. The current nominal interactive schedule
alone uses **49.35 minutes**, including matched scaling, before other bulk work.
This forecast is not a measured complete-suite timeout, but warrants resolving
scheduling before spending another full capture. Rebaselining may not resolve
every remaining budget offender; actual complete captures remain mandatory.

An intermediate integrated run found two redundant-lookup read-count failures
(`df2f4b0`: 1,665 passing, two failing). Additional red `bd4112d` and green
`d0940a1` remove lookups for known own IDs without reusing deleted financial rows;
unknown IDs retain indexed global collision checks. All 31 focused import tests
and Ruff pass, and the final native measurement above retains identical hashes.
Exact `d0940a1` image `447ff8d5596a` passes **1,668 tests in 243.60 seconds**
and Ruff offline, with locked dependencies and no source mount or private ledger.

Alternative: retain the original reference and document a PRD-compatible workload
restructuring that retains complete coverage and aggregate limits. Do not silently
drop observations, increase limits or reset the reference.

The review requirement comes from W2 of the preserved
[performance PRD](../../PRD-performance-ai-fuzz-2026-10-10.md): reference changes
require separately reviewed, explicitly labelled performance rebaseline changes
with before/after JSON and retained history. Human approval is still pending.
