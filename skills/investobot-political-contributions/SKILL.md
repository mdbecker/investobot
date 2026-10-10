---
name: investobot-political-contributions
description: Research verified senior executive political contributions and permitted source evidence.
metadata:
  version: "1.0.0"
---

# Executive political-contribution research

Research publicly identified company executives and permitted U.S. federal
contribution evidence using your browser and authorized external sources.
Investobot validates and remembers structured JSON; it does not execute research.

Read [research-method.md](references/research-method.md) before collecting evidence
and [json-contract.md](references/json-contract.md) when preparing the package.
Verify the company, role dates, contributor identity and recipient relationships.
Never infer an executive's political party, ideological score or trading signal.

Named contributor data requires independent reviewed source-use permission.
Public availability and import confirmation do not supply that permission.
With unresolved rights, retain public executive/recipient metadata but no named
contributions. Keep uncertainties and partial coverage visible.

Use `invest schema` and `invest tools describe research.political.import` for
current authoritative inputs and mutation scope. Validate, preview, then obtain
explicit acceptance before `--yes`. Imports change research records only.
