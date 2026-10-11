---
name: investobot-portfolio-research
description: Coordinate source-backed specialist research over a frozen portfolio exposure universe.
metadata:
  version: "1.0.0"
---

# Portfolio Research

## Prerequisites and discovery

Use the selected local Docker ledger; never install host dependencies. The human
supplies account settings, reviewed source permissions and any external API
entitlements. Offline fictional fixtures need no secrets. Never request brokerage
credentials or persist raw account HTML. Install only when requested into the
project `.agents/skills` (Codex) or `.claude/skills` (Claude Code).

Start with `invest tools list`, `invest tools describe TOOL` for each command below,
and `invest schema`. Discovery is authoritative for flags, strict input schemas,
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

Trigger: research the companies underlying a portfolio. Batch deterministic top
20 issuers by default; freeze requested top-N, minimum exposure and date window.

1. `invest portfolio exposure --as-of DATE`; inspect residual unknown exposure,
   path provenance, cycles, depth and constituent vintage.
2. `invest portfolio research-universe --as-of DATE --top 20 --min-exposure 0`.
   Use the discovered canonical frozen-universe contract without agent arithmetic;
   retain unknown and filtered exposure. `invest data snapshot --file universe.json`.
3. `invest research portfolio plan --universe-manifest MANIFEST_ID` with discovered
   window flags. Follow existing earnings/news/competitive/political-contributions/
   management-insiders skills for every requested issuer; fund diligence remains
   independently reusable. Track each task, original source rights and skill hash.
4. For each specialty use discovered validate → import preview → human review →
   explicitly authorized import confirmation. For news: `invest research news validate news.json`; `invest research news import news.json`; only after approval
   `invest research news import news.json --yes`.
5. `invest research portfolio report --plan PLAN_ID`. Preserve issuer-level
   NOT_RESEARCHED/PARTIAL/REVIEW_REQUIRED/AVAILABLE and exposure coverage.

Success walkthrough: a frozen two-issuer fictional queue receives accepted sourced
specialty runs. Report coverage by required specialty/window, source links, hashes
and exposure-weighted factual watchlist ordering; no forecast or trade instruction.

Blocked walkthrough: only news for one issuer is available, source permissions
are unreviewed or evidence falls outside the window. Report PARTIAL coverage;
never claim full-company/portfolio diligence. Named contributions need an
independently reviewed rights policy; executive, employee and corporate PAC facts
remain distinct. Prompt copying does not execute research or authorize imports.
