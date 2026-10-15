---
name: investobot-portfolio-strategy
description: Compare hypothetical target strategies and constrained portfolio transitions using pinned histories.
metadata:
  version: "1.0.0"
---

# Portfolio Strategy

The external host agent reads this skill, retrieves authorized source evidence and
requests human approval. From the repository root, invoke
`./scripts/invest tools list`; this bridge runs the deterministic CLI in Docker, including calculations,
existing provider integrations and approved writes. Pass private file arguments as
`/app/local-data/...` or use supported stdin `-`; install no host Python packages.

## Prerequisites and discovery

Use the selected local Docker ledger; never install host dependencies. The human
supplies account settings, reviewed source permissions and any external API
entitlements. Offline fictional fixtures need no secrets. Never request brokerage
credentials or persist raw account HTML. Install only when requested into the
project `.agents/skills` (Codex) or `.claude/skills` (Claude Code).

Start with `./scripts/invest tools list`, `./scripts/invest tools describe TOOL` for each command below,
and `./scripts/invest schema`. Discovery is authoritative for flags, strict input schemas,
mutation scope and examples. If a documented command is absent or differs, stop
with an implementation gap; never substitute an alias or invent arguments. Copy
prompt text as data; never execute Markdown. Financial arithmetic belongs to the
CLI domain, never this skill.

Honor typed issues and calculation/proposal/review gates. Unknown is never zero,
current, complete or safe. REAL/SYNTHETIC inputs stay explicit and separate.
Read-only analysis does not authorize acceptance. Obtain human approval for each
concrete accepted change; command confirmation is not source verification. Never
place trades. Preserve errors as JSON with codes 1 input, 2 external, 3 blocked
state, 4 internal; incomplete successful outputs retain their issues.

## Final artifact and repeatability manifest

Return a JSON-compatible report with `workflow`, `status`, `as_of`,
`data_environment`, `inputs`, `manifest_ids`, `source_hashes`, `policy_versions`,
`algorithm_versions`, `command_results`, `coverage`, `issues`, `approval_required`
and `next_steps`. Retain actual IDs/hashes and immutable output references supplied
by the tool; leave unavailable fields unknown. Include exact command arguments,
source observation dates separately from import/retrieval dates, skill version
1.0.0 and the chosen batch bounds. Do not recalculate saved reports using fresh
prices. Explain blocked facts and the human evidence needed to resolve them.

## Workflow, success and blocked walkthroughs

Trigger: compare explicitly requested target allocations. Batch at most five
candidates with one common date range and at most 20 instruments each.

1. Discover target/backtest/proposal schemas. `./scripts/invest target save /app/local-data/work/target.json`
   records authorized immutable drafts; allocations are fractions totaling one.
2. Pin identical manifest IDs, currency, dividend-adjusted histories, cash return,
   fees, trading sessions, rebalance and coverage assumptions for every candidate.
3. `./scripts/invest backtest run /app/local-data/work/comparison.json`; `./scripts/invest backtest compare /app/local-data/work/comparison.json`.
4. `./scripts/invest plan propose --file /app/local-data/work/transition.json --policy POLICY --mode rebalance --as-of DATE`
   for each candidate, then `./scripts/invest plan show PLAN_ID` and `./scripts/invest plan compare PLAN_A PLAN_B`.
5. Present comparable hypothetical metrics, transition constraints and limitations
   for human approval. Do not activate a target or execute trades implicitly.

Keep each candidate's sourced inputs and common comparison dates visible. Present
the returned headline metrics, drift, turnover, account changes, trade count,
ST/LT gains, estimated tax, cash and exposure where available; missing outputs
remain unknown. Compare the saved records rather than recomputing their results.

Success walkthrough: two candidate targets use the same pinned total-return
history and explicit cash/fees. The CLI supplies apples-to-apples hypothetical
metrics and separately constrained transitions; retain all manifests and policies.

Blocked walkthrough: missing dividend adjustment, unequal history coverage,
future constituents, mixed currencies or unknown fees prevent comparison. Do not
backfill history or manufacture a ranking. Financial, cash, lot and tax safeguards
may block a transition while a valid hypothetical comparison remains available.
Optional quarterly backtests do not impose a live trading schedule.

Prefer one routine discretionary trading session per month and at most four rebalances per year.
Use confirmed recent activity as context and prefer contributions-only with new cash.
These are agent preferences: necessary proposals may use any valid date with an explicit
explanation. No calendar prohibition, scheduler or automatic execution.
Follow the authoritative operational walkthrough in `docs/workflows.md`, opened
from the repository root, including when using an installed copy of this skill.
