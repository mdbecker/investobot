# Brokerage HTML is candidate evidence

Vanguard, Fidelity, Fidelity NetBenefits and PNC profiles are **PROVISIONAL**.
Their current aliases use the conservative generic table reader. No reviewed real
anonymized HTML has been supplied, so these profiles return
`UNVALIDATED_INSTITUTION_ADAPTER` and require human review. Synthetic tests establish
parser behavior; they do not validate a provider's current statement layout.

Supply an HTML file you obtained yourself. Investobot does not log in, scrape,
request brokerage credentials or retain the page. Identify its account, source
date and REAL/SYNTHETIC environment explicitly. A download/import date cannot
establish source freshness. Undated positions, lots and cash keep unknown source
dates. Coverage is independent for each domain, and remains partial unless you
explicitly supply complete coverage and every relevant row can be interpreted.

The reader recognizes financial column labels, rejects duplicate/contradictory
rows, and excludes explicit account summary tables and total rows from holdings.
An excluded ambiguous summary returns a review issue, so it cannot silently
support complete coverage. Unsupported numeric units and omitted fields stay
unknown; the reader never substitutes zeros or invents securities/classifications.
Cash coverage requires an explicit usable cash balance row.

Displayed precision comes from printed financial lexemes such as `100.00`, not
from reformatted Decimal values. Financial cell references retain source hash,
table/row/column coordinates and the financial text needed to review rounding.
Unrelated page text, account-page prose and raw HTML are not included. Aggregated
lot positions retain references to every contributing financial cell.

A candidate lot without a reviewed original broker reference or acquisition
mapping is `UNRESOLVED` and unsaleable. A recognized original lot ID is preserved
with its source-cell reference, but remains a candidate requiring human review.
Candidate IDs exclude mutable quantities, basis and valuation marks; they are
not proof of canonical lot identity. Never approve a generated row ID as a broker
ID. Review original acquisition evidence, remaining quantity and adjusted basis
before marking a lot verified through the accepted-input workflow.
An ordinary `Cost Basis` heading does not establish whether the number is original
or remaining adjusted basis. The printed value remains candidate evidence with
`UNKNOWN_LOT_BASIS_SEMANTICS`; remaining adjusted basis stays unknown unless its
source heading explicitly identifies that meaning or a reviewed input supplies it.

Before real-world use, provide safely anonymized original HTML for each intended
institution, review original field meanings and coverage, and add golden parser
acceptance cases. Check reconciliation issues before explicit acceptance. Real
provider validation and human source review remain separate release gates.
