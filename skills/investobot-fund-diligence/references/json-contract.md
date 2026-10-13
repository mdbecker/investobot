# Authoritative JSON and explicit acceptance

Retrieve `./scripts/invest schema` and `./scripts/invest tools describe research.funds.import` before
writing JSON. Their `FundDiligenceInput` schema is authoritative; this reference
explains semantics without maintaining a second JSON schema.

One object has `schema_version="1.0"` and
`research_type="ETF_MUTUAL_FUND_DILIGENCE"`, with `fund`, `scope`, `sources`,
`methodology`, `holdings_snapshot`, `holdings`, `metrics`, `findings` and
`limitations`. Every nested object rejects extra keys. Supply required nullable
fields explicitly as null when unknown. Fund identity requires original SEC
registrant/series/class evidence; verify SEC URL CIK/accession against the cited
filing. Source credentials or ambiguous locators are rejected. Preserve observation,
publication, filing and access dates independently.

Use unique IDs across all collections and valid same-run citations. Use plain
Decimal strings, never JSON floats or exponent notation. Metric code/unit/scope
and date constraints come from the schema. Negative metrics are permitted only
for average premium/discount. Fee/distribution facts are class-specific; duplicate
code/scope/period/observation facts are rejected. Unavailable numerical components
and PARTIAL/BLOCKED coverage need meaningful limitations. Findings preserve fact,
optional interpretation and uncertainty separately.

Save reviewed JSON on the host as `local-data/work/fund-diligence.json`, then
pass its container path:

```sh
./scripts/invest research funds validate /app/local-data/work/fund-diligence.json
./scripts/invest research funds import /app/local-data/work/fund-diligence.json
```

Both are read-only previews and do not create a selected database. Present the
preview and original source evidence to the human. After explicit human approval:

```sh
./scripts/invest research funds import /app/local-data/work/fund-diligence.json --yes
./scripts/invest research funds list
./scripts/invest research funds show RUN_ID
./scripts/invest research funds summary RUN_ID
./scripts/invest research funds holdings RUN_ID
```

Acceptance writes immutable research only. Equivalent reordered evidence is
UNCHANGED; a genuine correction creates a new run. Accepted trusted skill identity
comes from the bundle, never agent JSON. `show` reads the complete package;
other reports use compact relational projections. Schema 10 requires a fresh
ledger; do not delete, migrate or reset an existing private ledger to make import
work. Ask the owner to choose an explicit disposable research database instead.
