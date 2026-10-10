# Research sequence

1. Confirm the legal issuer, ticker, verified CIK, any existing canonical
   `security_id`, requested start/end dates and source-access cutoff. Read saved
   research as context only; keep separate runs distinct. If issuer CIK cannot be
   verified, omit individually attributed Form 3/4/5 transactions.
2. Identify publicly disclosed current/former officers, directors and ten-percent
   owners. Record sourced titles, role types and known tenure dates. Unknown dates
   remain null. Distinguish individual and entity owners; a reporting owner is not
   automatically an executive. Never merge similar names without identity evidence.
3. Locate original Forms 3/4/5 and amendments, XML tables and footnotes, DEF 14A
   compensation/CD&A, and relevant issuer agreements or leadership disclosures.
   Verify issuer CIK, each reporting-owner CIK, accession, filing/acceptance dates
   and exact person association. Record omissions and reporting lag.
4. Extract both table types with as-filed codes, A/D markers, instrument titles,
   dates, units, disclosed prices/currencies and direct/indirect ownership. Preserve
   indirect nature and plan disclosures. Cite venue explicitly or leave UNKNOWN.
5. Reconcile amendments and repeated events using source evidence. Link corrected
   or duplicate rows only within this package; preserve originals. Ambiguous rows
   remain UNRESOLVED with explanatory notes and cannot contribute to totals.
   For ownership corrections verify original accession, matching base form,
   owner/instrument identity and the specific quantity/date correction locator.
   Transaction date/code corrections likewise require an explicit amended-field
   locator, not notes alone. Read both original and amended disclosures manually;
   matching figures or an amended form alone do not prove a linked correction.
6. Capture Form 3 initial and Form 4/5 post-transaction holdings as dated
   observations. Never reconstruct balances, conversions or percentages from
   incomplete disclosures. Link corrected holdings only within this package;
   retain unsupported amended holdings as unresolved. Equal or conflicting
   unlinked balances on the same latest date require review, never selection or
   summation. Earlier runs do not automatically supply original-row links.
7. Capture disclosed compensation and material vesting, performance, severance,
   change-in-control and clawback terms. Retain fiscal year and valuation basis;
   distinguish arrangements from payments.
8. Review unmatched identities, late/missing filings, corrections, unknown prices,
   missing plan indicators, indirect holdings and compensation-period differences.
   Explain incomplete coverage; filing availability is not exhaustive coverage.
9. Emit one complete strict JSON file in ignored `local-data/`. Discover commands
   with `invest tools describe research.insiders.import`, validate and preview.
   A human verifies original sources and explicitly approves acceptance before
   any `--yes` import; an agent cannot self-authorize it.
10. Retrieve deterministic `summary`, `activity` and `ownership` reports. Preserve
    limitations and citations in explanations without advice scores or ledger edits.

Use [SEC Forms 3/4/5 overview](https://www.sec.gov/about/forms/forms-3-4-5.pdf)
and original filings for source interpretation. Research uses the external
agent's browser; Investobot has no filing API, scraper or required service account.
