# Research skills

The six research bundles orchestrate earnings, political contributions, news,
competitive comparisons, management/insiders and fund diligence. They are part of
[13 host-readable skills](skills.md), tracked under `skills/` and packaged for
installation. Docker validates and persists research JSON; it does not run an AI
agent, browser or prompt service. The host agent uses its authorized capabilities.

```sh
./scripts/invest research skills list
./scripts/invest research skills show investobot-earnings
./scripts/invest research skills install --agent codex --workspace /app
./scripts/invest schema
```

The project bind makes `.agents/skills` visible to the host. Claude Code uses
`--agent claude-code` and `.claude/skills`. Review modified files before explicit
`--confirm` replacement; unrelated skills are preserved. Installation needs no
provider credentials. See [skills](skills.md) for trust/path safeguards.

News skill version is `1.0.1`; management/insider skill and input contract are
`1.1.0` and `1.1`. Other research skills use `1.0.0` and input contract `1.0`.
These input versions are separate from checksum-identified SQLite schema **1**.
Canonical metadata/hash identities remain independent for every specialty.

Research JSON is untrusted evidence. Structural validation establishes neither
source truth nor reuse rights. Humans review original disclosures; imports
preview before explicitly authorized `--yes` acceptance. Research changes no
holdings, classifications, financial marks or provider caches. Political evidence
requires an independently reviewed rights policy; installing a skill grants none.
Fund diligence requires original registrant/series/exact-class identity and sourced
class-specific disclosures. Missing specialty/window coverage remains explicit.

[Earnings](earnings-research.md) · [Political contributions](political-research.md) ·
[News](news-research.md) · [Competitive](competitive-research.md) ·
[Management/insiders](insider-research.md) · [Fund diligence](fund-diligence.md).
Offline examples are fictional; real disclosures, source permissions and live
provider responses remain separate manual gates. General prompt CRUD is retired;
operator overrides belong in ordinary host notes after explicit preservation.
