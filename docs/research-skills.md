# Research skills

Agent skills describe how an external agent researches evidence. Investobot's
CLI validates, stores and calculates; installing a skill does not run research.
Skills follow the [Agent Skills specification](https://agentskills.io/specification).
Canonical portable instructions live in `skills/` and are also bundled in the
distribution. News uses version `1.0.1`; competitive, earnings and political use `1.0.0`. Their JSON contracts use
schema `1.0`. Management/insider research uses version `1.0.0`. These are
different from SQLite schema 8.

## Discovery and project-local installation

Use Docker throughout; no host packages, new API account or secret are needed.

```sh
docker compose build
docker compose run --rm -T app invest research skills list
docker compose run --rm -T app invest research skills show investobot-earnings
docker compose run --rm -T app invest research skills show investobot-news
docker compose run --rm -T app invest research skills show investobot-political-contributions
docker compose run --rm -T app invest research skills show investobot-management-insiders
docker compose run --rm -T app invest research skills install --agent codex --workspace /app
```

Installation copies all five skills into project-local `.agents/skills` for Codex.
For Claude Code use `--agent claude-code`, which selects `.claude/skills`. The
workspace must be mounted in the container; `/app` is the repository bind mount.
No global agent configuration changes. Files can also be copied manually from
the canonical directories. Installation reports copied files and skill versions.

Identical files are preserved. Modified files require explicit `--confirm` before
replacement; inspect your changes first. Unsafe symlinks and traversal are
rejected even with confirmation. Unrelated skills remain untouched.

Ask the agent to use `investobot-earnings` for quarterly/annual company financial
research, or `investobot-political-contributions` for verified executive and
recipient evidence. Codex may invoke the skills by name with `$`; Claude Code
uses its normal project-skill discovery. Each skill's `SKILL.md` routes to focused
references. Discover current authoritative models with `invest schema` and
command behavior with `invest tools describe`; skill text does not maintain a
second JSON Schema.
Use `investobot-news` for incremental material developments, catalysts and
hypothesis assessments; load `research news context --ticker TICKER` first.
Existing earnings and political skills retain their versions and content.

## Research boundary

The agent uses its existing browser and authorized sources. Investobot neither
browses nor executes an LLM. Research JSON remains untrusted: validation checks
structure, references and consistency, while a human verifies that original
disclosures support the facts. Import previews by default; `--yes` accepts an
immutable run and changes research records only.

The political skill replaces its bundled V2.5 prompt. Other general prompts and
user-created overrides remain available in the existing Prompt Library. Political
source rights remain independently enforced; installing the skill does not grant
permission to collect individual contributor information.

See [earnings research](earnings-research.md), [political research](political-research.md)
and the preserved [V2.6 PRD](PRD-v2.6.md). Automated fixtures are fictional and
offline. Their success does not validate real SEC disclosures, institution HTML,
live provider access or a remote GitHub Actions result.

Use `investobot-competitive` (version `1.0.0`, JSON schema `1.0`) for sourced
operating-company peers, segment overlaps and reported financial comparisons.
Its method and comparability references link back to the authoritative CLI model.
See [competitive research](competitive-research.md) for Docker commands and human
source review. Earlier skill files and pinned versions remain unchanged.

Use `investobot-management-insiders` for sourced officer/director tenure,
compensation, SEC Forms 3/4/5 and reported ownership. It distinguishes purchases,
sales, exercises, grants, tax/exercise payments, gifts and other codes; neither
filing availability nor validation establishes comprehensive or factual coverage.
See [management and insider research](insider-research.md) for a complete fictional
example, original-source human review and the schema-8 boundary.
