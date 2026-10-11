# Structured fund screening

`invest fund search filters.json` evaluates supported fund type, expense-ratio,
AUM and issuer criteria against provider screening and metadata evidence. Discover
actual input units and flags with `invest tools describe fund.search`; the adapter
preserves provider units and never fills missing characteristics.

The result includes `criteria`, `coverage`, typed `issues`, and candidate
`source_ids`. A source ID is the actual metadata cache resource key
`PROVIDER:metadata:TICKER`; source observation and retrieval dates remain in
`metadata_provenance`. Candidate exclusion due to unknown requested data produces
`REVIEW_REQUIRED`, with missing fields reported per ticker. A known criterion
mismatch is an ordinary exclusion, not missing evidence. Zero matches does not
establish that no suitable instruments exist outside the bounded provider screen.

Search creates no rankings or investment scores and never registers instruments,
changes classification, holdings or marks. Provider cache writes are research
observations only. Compare candidates with disclosed source dates and coverage;
verify original issuer identity and obtain explicit approval before registration.
Live FMP access requires a human-provisioned key and independently verified
entitlement. Offline fictional fixtures require no credentials; provider failures
remain external errors rather than invented results.
