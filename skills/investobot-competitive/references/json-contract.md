# Preparing the authoritative JSON contract

Use `invest schema` to inspect `CompetitiveResearchInput` and
`invest tools describe research.competitive.validate` or
`invest tools describe research.competitive.import` for CLI contracts and mutation
scopes. Do not maintain a separate schema or execute copied prompt text.

The package uses `schema_version: "1.0"` and
`research_type: "COMPETITIVE_POSITION_PEER_COMPARISON"`. Supply exactly one
`subject` with `entity_id: "subject"`, a declared `scope`, `sources`, 1–8 `peers`,
`overlaps`, `findings`, reported `metrics` and `limitations`. Use canonical
security IDs only when verified and already registered; omit unknown optional
identity fields rather than fabricating them. Tickers may be null for private or
unlisted companies; known CIKs are zero-padded strings.

Source IDs and references are local to this package. Each peer needs a valid
selection source and at least one overlap with subject and peer evidence.
Findings separate `factual_basis` from `interpretation`, `assumptions` and
`uncertainty`; optional overlap references belong to that peer. Metric citations
need exact source locators and verified issuer attribution. Sources use public
URLs, publication/access dates and locators; strip credentials, unknown query
parameters and fragments and avoid ambiguous record locators. SEC URL CIKs must
agree with recorded issuers.

Financial values are exact plain decimal **strings**, never JSON numbers,
exponents, floats, booleans, NaN or infinity. Preserve units, definitions,
accounting basis and actual dates; distinguish consolidated and segment scope.
No forecast or agent-computed comparison fields are accepted. Unknown keys,
duplicate identities/IDs and cross-run or inconsistent references are rejected.

Coverage `COMPLETE_WITHIN_DECLARED_SCOPE`, `PARTIAL` or `BLOCKED` describes only
the declared scope; it never promises exhaustive research. Explicit limitations
explain contested claims, absent private-company disclosures and incompatible
observations. A source or issuer that cannot be verified means omitting the
metric, disclosing the gap and marking coverage partial.

Save JSON under ignored `local-data/`, validate, preview import, inspect source
support and obtain explicit human acceptance before `import FILE --yes`.
Validation and preview do not create or modify the selected ledger. Confirmation
stores immutable research only; it does not mutate the portfolio or stale plans.
Earlier runs remain accessible, and identical canonical input is a no-op.
