# Compensation and ownership

Use original DEF 14A tables/CD&A and issuer filings or agreements. Attribute each
item to its person, fiscal year when disclosed, type, exact reported value,
currency, valuation basis, terms and precise citation. Unknown values stay null.

Stock/option award values use GRANT_DATE_FAIR_VALUE; they do not represent cash
received, exercise proceeds or realized gains. Keep salary, bonus, non-equity
incentives, awards and reported SUMMARY_COMPENSATION_TOTAL separate. Never add a
reported total to its components, combine currencies, or treat policy/vesting/
performance/severance/change-in-control/clawback terms as actual payment.
Unquantified terms require null value/currency and explanatory terms.

Ownership is an as-filed observation with date, source, table type, instrument
title and direct/indirect form. Retain disclosed indirect nature and explain
omissions. Never sum dates, different classes, derivative/non-derivative units,
or direct/indirect observations into a reconstructed current balance. Form 3
initial holdings are not purchases. Latest observations are still reported
observations, not verified current holdings.

For Form 3/A, 4/A or 5/A ownership corrections, link `supersedes_id` to the exact
original same-run row, with matching base form/original accession and verified
owner/issuer, security title, table, ownership form and indirect nature. Quantity
and date changes require a specific `correction_source_locator`; verify its
actual disclosure manually. Preserve both records. Further amendments must
reference the immediately previous row/accession; no branches or cycles.

Use `duplicate_of_id` only for an evidenced repeat with identical holding
identity, date and quantity. A duplicate cannot be a correction target. A missing
supported original link on an amended source makes the holding UNRESOLVED,
excluded from effective latest observations. Never infer linkage from balances.

Ownership reports retain EFFECTIVE, SUPERSEDED, DUPLICATE and UNRESOLVED statuses.
Select latest by effective observation date, not filing/import date. Multiple
unlinked rows at that latest date, even with equal quantities, go to
`conflicting_latest_observations` and require review; no uniquely current answer
can be asserted. This report covers one immutable run, without cross-run merging.

Keep former roles and unknown tenure dates explicit. A ten-percent entity holder
must remain an ENTITY with its sourced role rather than becoming a human officer.
No inferred personal attributes, contact details or cross-company people registry.
