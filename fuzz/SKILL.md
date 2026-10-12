---
name: investobot-adversarial-review
description: Explicitly requested offline adversarial synthetic testing with replayable findings.
---

Only run on explicit human request. Never schedule campaigns, launch providers,
place trades or automatically publish issues.

1. Read AGENTS.md, relevant code, invariants and previous findings. Invent varied
   input/state/event sequences targeting concrete uncertainties, without quotas.
2. Adapt tests/fixtures/fuzz/campaign.json: keep useful cases and vary operation
   sequences, exact values, bounded counts and allowlisted mutations. JSON is data, never code,
   SQL, paths, URLs or model-generated financial answers. The adapter supports
   imports, deposits, queries, tax lots, proposals, corpus retrieval and recovery.
   Use focused domain tests for unsupported workflows rather than a new framework.
3. Use disposable Docker --network none, the locked app image and owned outputs.
   Mount no private ledger, credentials or Docker socket. Inside the container:
   `uv run --no-sync python scripts/fuzz.py run INPUT.json --output-dir OUTPUT`.
   One case is valid; keep the full saved case JSON and local report. Saved JSON,
   not unused random metadata, is the authoritative replay input.
4. Investigate surprises. `scripts/fuzz.py replay CASE.json --output-dir OUTPUT`
   creates a fresh synthetic ledger. `scripts/fuzz.py minimize CASE.json
   --output-dir OUTPUT` retains a dependency-aware reduced example and repeated
   evidence. Invariant failures remain unconfirmed until independently reviewed;
   timeouts/resource failures remain unresolved environmental failures.
5. Report command/input, source version, expected versus observed, invariant,
   reproduction evidence and severity. No bugs found is acceptable: say what was
   exercised. Keep findings and complete replay JSON in ignored local data until promoted.
6. For a confirmed bug, observe and commit a failing domain-language BDD test,
   implement the smallest safe fix, replay and pass full correctness tests.
   For slowness, profile matched inputs and promote only consistently important
   cases. CI runs fixed regressions, never AI-generated campaigns.
