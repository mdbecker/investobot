# Authoritative contract and CLI

Use `./scripts/invest schema` to inspect `PoliticalResearchInput`, and discover inputs and
scope with `./scripts/invest tools describe research.political.validate` and
`./scripts/invest tools describe research.political.import`. Do not maintain a duplicate
schema or invent fields. Return one JSON object without Markdown/prose.

The package distinguishes company identity, research period and coverage/rights,
sources, verified executives, recipients, verified contributions, unresolved
matches and limitations. Its research type is
`EXECUTIVE_POLITICAL_CONTRIBUTIONS` and its contract version is `1.0`.
Trusted bundled skill version comes from Investobot rather than agent assertions.

All references must resolve within the package. Each counted transaction needs
an evidence-backed unique underlying key. Counted refunds require
`original_contribution_id` pointing to their original counted contribution.
Use original identifiers and exact decimal strings. Unknowns remain unknown;
never invent zeros, sources, identities, parties or transaction records.

```sh
./scripts/invest research political validate /app/local-data/political-research.json
./scripts/invest research political import /app/local-data/political-research.json
./scripts/invest research political import /app/local-data/political-research.json --yes
./scripts/invest research political list --ticker EXAMPLE
./scripts/invest research political show RUN_ID
./scripts/invest research political summary RUN_ID
```

Validation checks structural consistency, not factual truth. Source permissions
are checked independently of the submitted JSON. Preview is read-only; `--yes`
is explicit research acceptance and never overrides source restrictions.
