# As-filed transaction codes

Preserve the original short uppercase SEC code and independent acquisition (`A`)
or disposition (`D`) marker. Inspect original tables and footnotes rather than
inferring the marker from the code.

| Code | Investobot category | Interpretation boundary |
| --- | --- | --- |
| P | PURCHASE | Reported open-market **or private** purchase; venue stays UNKNOWN without explicit evidence. |
| S | SALE | Reported sale; no inference of discretionary timing. |
| M | OPTION_EXERCISE_OR_CONVERSION | Exercise/conversion, distinct from purchase. |
| A | AWARD_OR_GRANT | Award/grant, distinct from discretionary purchase. |
| F | TAX_OR_EXERCISE_PAYMENT | Securities used for exercise price or tax obligations, distinct from sale. |
| G | GIFT | Gift, distinct from purchase/sale. |
| Other, including J/compound codes | OTHER | Preserve verbatim; do not invent supported meaning. |

Form 3 primarily reports initial ownership. Form 4/5 may report derivative and
non-derivative rows; option units do not automatically equal common shares owned.
Transaction date differs from filing date. Require verified owner CIK and exact
filing-person association for every transaction.

Keep Rule 10b5-1 status REPORTED_YES, REPORTED_NO or NOT_DISCLOSED. A reported plan
indicator does not establish intent, knowledge or legality. Historical absence
stays NOT_DISCLOSED. For OPEN_MARKET or PRIVATE venue retain the explicit filing
statement locator; code P alone is insufficient.

Amendments require original accession and explicit same-package supersedes links.
Repeated economic events require supported duplicate links; matching numerical
fields alone cannot establish duplication. Exclude ambiguous rows as UNRESOLVED.

A documented transaction amendment may change its date or code while retaining
the same verified issuer/owner, title, table, ownership form/nature and A/D
direction. Supply `correction_source_locator` identifying the corrected field;
notes alone are insufficient. Verify the matching Form 4/A or 5/A, original
accession and filing order. Only the verified corrected date/code drives effective
classification and ordering. Unsupported changes remain UNRESOLVED and excluded;
do not link incompatible identities. Reject branching, cycles and duplicate
targets; later amendments form a linear chain to the immediately previous row.
Corrected P still has UNKNOWN venue without separately cited venue evidence.

Consult [Form 4 and instructions](https://www.sec.gov/about/forms/form4.pdf),
[SEC dataset caveats](https://www.sec.gov/data-research/sec-markets-data/insider-transactions-data-sets)
and [SEC Rule 10b5-1 disclosures](https://www.sec.gov/newsroom/modernizing-rule-10b5-1-insider-trading-plans).
These references guide interpretation, not automated data collection.
