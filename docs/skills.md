# Host agent skills

Tracked `skills/` is the canonical instruction source. Thirteen bundles cover
seven portfolio workflows (sync, performance, contributions, harvesting,
screening, portfolio research and strategy) and six research specialties
(earnings, political contributions, news, competitive, insiders and fund diligence).
The independently supplied host agent reads these files and retrieves permitted
sources; Docker performs deterministic calculations and accepted writes.

```sh
./scripts/invest research skills list
./scripts/invest research skills show investobot-portfolio-sync
./scripts/invest research skills install --agent codex --workspace /app
```

Use `--agent claude-code` for `.claude/skills`; Codex installs to `.agents/skills`.
`/app` is the host project bind, so the external agent can read the copied files.
No agent runtime or prompt volume is created. Installing copies does not execute
instructions or grant source rights. Skill commands use `./scripts/invest` from
the checkout; file arguments use `/app/local-data/...` or stdin `-`.

Identical files remain unchanged; reviewed `--confirm` is required to overwrite
modified canonical resources. Traversal, symlinks and nonregular destinations
are rejected; unrelated operator skills and custom resources remain intact.
Keep ordinary private context in `local-data/agent-notes/`. The retired prompt
library is replaced by existing skills; ordinary operator context is untrusted
host Markdown. Host-agent configuration stays outside Docker images; canonical
tracked skills remain packaged for installation.

Skills discover current `tools describe`/`schema` contracts, do no financial
arithmetic and require concrete human authorization for accepted changes.
Scripted offline tests validate CLI workflows; original-source truth, rights and
whether a host agent follows instructions require human review.
See [research skills](research-skills.md), [workflows](workflows.md) and
[testing](testing.md).
