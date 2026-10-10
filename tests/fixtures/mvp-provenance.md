# Unified MVP fixture provenance

All unified MVP account IDs, issuer identities, holdings, events, policy inputs,
research text and source URLs are invented. They are not redacted real data and
do not validate Vanguard, Fidelity NetBenefits, PNC, FMP entitlement or any real
company filing. Financial strings are exact decimal strings; dates are fixed.

`mvp-history.parquet` contains one invented adjusted-history row:
`DEMO`, `2026-10-09`, `100`. Generated in a disposable Docker container with
DuckDB **1.4.1**, using `COPY (SELECT 'DEMO' AS security_id, DATE '2026-10-09'
AS date, '100' AS adjusted_close) ... (FORMAT PARQUET)`. It is prepared before
production dependency changes so red scenarios never fail because their fixtures
require a missing runtime package. Tests hash the file and use an independent
copy for corruption checks; the tracked original is never modified.

BDD fixtures are built in the matching `test_mvp_*_bdd.py` files and stored only
in temporary SQLite databases. No private ledger, credentials, donor data or raw
broker HTML is read. Synthetic HTML is inline candidate evidence and never a
claim that institution-specific patterns have been reviewed.
