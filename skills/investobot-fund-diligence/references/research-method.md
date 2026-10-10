# Identity and research procedure

1. Verify the exact fund series and share class in original SEC EDGAR evidence:
   `registrant_cik` is a 10-digit string, `series_id` is `S` plus nine digits and
   `class_id` is `C` plus nine digits. Preserve official class name and optional
   ticker, exchange, ISIN and adviser. Similar names or tickers cannot substitute
   for legal identity. Do not use another series's holdings or another class's fees.
2. Establish `researched_as_of`, observation dates, filing/publication dates and
   coverage limitations separately. Source dates must fit the research cutoff.
   Read the actual public N-PORT filing and reporting date; public availability
   and schedules may change. Do not assume every monthly observation is public.
3. Read the latest available prospectus, supplements and shareholder report.
   Keep reported share-class fees, waivers and shareholder costs separate.
4. Verify whether the strategy is INDEX or ACTIVE. INDEX needs a named index
   and source-backed methodology; preserve provider, selection, weighting,
   rebalance/reconstitution and replication only as disclosed. Distinguish index
   rules from fund rules. ACTIVE needs the decision approach and benchmark
   status; a benchmark does not establish index tracking. Licensed or absent
   rules remain null with explicit uncertainty.
5. Extract one dated holdings snapshot, fiscal-period turnover and applicable
   liquidity disclosures. Preserve cash, bond, fund-of-funds and derivatives
   coverage limits; never imply look-through exposure.
6. Inspect historical per-share distributions and any documented in-kind
   mechanism. Retain event dates and unresolved questions, separate disclosed
   facts from interpretations and omit unverified numbers.
7. Produce exactly one strict package, validate, preview and obtain explicit
   human approval before research-only acceptance.

Eligible structures are ordinary registered 1940 Act ETFs and open-end mutual
funds, including an ETF unit investment trust when original disclosures establish
eligibility and exact identity. ETNs, commodity/grantor trusts, closed-end or
money-market funds, leveraged/inverse products and opaque derivative-dominated
products are outside scope. Do not relabel them to make JSON validate.

Use SEC prospectus/summary prospectus, N-1A/497, shareholder reports and public
N-PORT, original sponsor disclosures, index-provider methodology and distribution
records. Record concise locators (form, accession, section/table and date), not
page copies. A source genuinely about the series may omit class attribution;
class fees and distributions require class-specific evidence. Optional canonical
`security_id` must already exist and its ticker must match sourced accepted
aliases; research never registers or reclassifies securities.

[SEC public N-PORT data](https://www.sec.gov/data-research/sec-markets-data/form-n-port-data-sets)
is a discovery starting point, not evidence that a particular current observation
is publicly available. Open the specific filing before asserting availability.
