# Preparing the authoritative JSON contract

Read `invest schema` for `InsiderResearchInput` and
`invest tools describe research.insiders.validate` / `research.insiders.import`
for arguments and mutation scopes. This guide explains the model; it is not a
second schema.

Use schema_version `1.0`, research_type `MANAGEMENT_INSIDER_ACTIVITY`, one company,
scope, sources, people, compensation, transactions, ownership and limitations.
Period start/end and research cutoff are explicit. Verify any supplied security
ID against the existing canonical security and ticker/accepted aliases; never
register or classify securities through research.

Source IDs are package-local. Retain original issuer/reporting-owner CIKs,
accessions, filing/acceptance/access dates, safe public URLs and precise locators.
SEC Forms 3/4/5 require valid accession, filing date and matching issuer CIK;
amendments identify original accession. Source dates cannot exceed cutoff.
Safe URL normalization strips credentials, unknown queries and fragments;
do not use URLs as storage for secrets or raw pages.

People need identity evidence, INDIVIDUAL/ENTITY type and at least one sourced
OFFICER/DIRECTOR/TEN_PERCENT_OWNER role. Transactions require verified owner CIK
matching the cited filing. Unknown tenure dates remain null; known end cannot
precede start. Similar names do not establish identity.

Quantities/prices/compensation are exact plain Decimal **strings**, never JSON
numbers, exponent notation, floats or fabricated zeros. Transaction quantity is
positive; disclosed price and holdings/compensation can be zero. Unknown price
and currency are both null; known price requires explicit source-backed currency.
No implicit USD, FX, ownership percentage or reconstructed balance is allowed.

Transaction rows preserve as-filed code, A/D, table type, instrument, direct/
indirect form, venue evidence and plan status. `(source_id, source_row_id)` is
unique. VERIFIED effective unique rows count; UNRESOLVED rows require notes.
supersedes_id and duplicate_of_id are mutually exclusive same-run links, without
self-reference, cycles or incompatible person/instrument/event identity.
Corrections require matching amendment/original evidence. Never infer links.

Save a complete package under ignored `local-data/`; validate and preview with
`research insiders validate FILE` and `research insiders import FILE`.
After independent source review and explicit human approval, `import FILE --yes`
accepts immutable research only. Read with `list --ticker TICKER`, `show RUN_ID`,
`summary RUN_ID`, `activity RUN_ID [--person PERSON_ID]` and
`ownership RUN_ID [--person PERSON_ID]`. List is compact; show retrieves the full
package. Reordered identical evidence is a no-op; corrections create new runs.
