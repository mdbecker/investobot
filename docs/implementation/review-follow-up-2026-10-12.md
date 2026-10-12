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

Verification: 49 targeted tests and Ruff pass in offline Docker. Representative
pair and final committed-tree acceptance are pending.

Human next step: configure main branch rules requiring the Docker `test` and
fixed-performance `performance` jobs, using their actual check names shown by
GitHub. Then prioritize reviewed sanitized broker HTML and live FMP coverage;
those remain PROVISIONAL/UNVERIFIED. This review does not approve real trades.
