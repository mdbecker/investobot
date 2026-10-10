---
name: investobot-earnings
description: Research company earnings and financial disclosures with verified periods and source evidence.
metadata:
  version: "1.0.0"
---

# Earnings and financial-statement research

Research company earnings through your browser and authorized disclosures.
Investobot validates structured facts, retains immutable history and calculates
descriptive comparisons; it does not fetch filings or execute an LLM.

Read [research-method.md](references/research-method.md) for evidence collection,
[accounting-rules.md](references/accounting-rules.md) when extracting metrics,
and [json-contract.md](references/json-contract.md) when preparing results.
Confirm the reporting entity, original fiscal periods and source support.

Keep exact values, currencies, units, definitions, GAAP/non-GAAP bases and segment
scopes. Separate historical facts, future guidance and agent interpretation.
Unknown values remain unknown. A recent retrieval never makes old results current.

Use `invest schema` and `invest tools describe research.earnings.import` for the
authoritative contract. Validate, preview and obtain explicit acceptance before
`--yes`. Research leaves holdings, tax lots, targets and saved plans untouched.
