---
name: investobot-competitive
description: Research a company's operating competitors, overlapping markets and segments, comparative advantages and disadvantages, and source-backed financial facts; prepare validated Investobot peer-comparison JSON.
metadata:
  version: "1.0.0"
---

# Competitive position and peer comparison

The external host agent reads this skill, retrieves authorized source evidence and
requests human approval. From the repository root, invoke
`./scripts/invest tools list`; this bridge runs the deterministic CLI in Docker, including calculations,
existing provider integrations and approved writes. Pass private file arguments as
`/app/local-data/...` or use supported stdin `-`; install no host Python packages.

Research one operating company and 1–8 operating peers through your authorized
browser. Investobot validates and preserves evidence and computes conservative
descriptive comparisons. The human decides whether any security merits ownership.

Follow [research-method.md](references/research-method.md) in order. Read
[comparability-rules.md](references/comparability-rules.md) before collecting
financial metrics and [json-contract.md](references/json-contract.md) before
preparing JSON. `./scripts/invest schema` provides the authoritative
`CompetitiveResearchInput` contract; these references explain its use.

A business competitor is not automatically a portfolio substitute. Do not rank
stocks, recommend trades, produce scores, infer correlation or tax equivalence,
register securities, or change holdings, targets or plans. Missing evidence and
private-company numbers stay unknown. Qualitative interpretations remain separate
from independently authored factual summaries and cited reported observations.

Validate and preview locally. Obtain explicit human approval before
`./scripts/invest research competitive import FILE --yes`. Presence of citations and
successful validation do not establish source truth, rights or comparability;
review the original sources before acceptance.
