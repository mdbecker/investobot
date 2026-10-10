# Research method

## Scope and identity

Confirm the company legal name, ticker/share class and corporate relationships
from issuer leadership pages and filings. Include publicly identified senior
officers who served during the requested period, rather than all employees or
only current officers. Retain role sources and known role dates.

Verify each contributor with corroborating role/employer/occupation evidence;
a name-only match is insufficient. Transaction evidence needs a source beyond
the biography establishing the executive's role. Put ambiguous matches in
unresolved findings rather than accepted contributions. No donor home addresses,
ZIP codes, contact details, birthdays or raw contributor pages.

## Rights before collection

Check the intended investment-research use before collecting named transactions.
FEC individual-contributor disclosures carry commercial-use restrictions.
Consult the source's terms and official guidance:
[sale or use](https://www.fec.gov/updates/sale-or-use-contributor-information/),
[contributor information](https://www.fec.gov/updates/use-of-contributor-information/).
Human-reviewed policy configured independently through `INVEST_RESEARCH_POLICY`
must support the specific intended use; agent-written `rights_basis` and `--yes`
cannot authorize it. Mirrors retain the original data restrictions.

If permission is pending/blocked, continue permitted public executive and
committee identity research only. Omit named transactions and explain the
limitation. Never generate or change policy to approve your own findings.

## Recipient and transaction accounting

Distinguish candidate campaigns, party committees, PACs, joint fundraisers and
other committees. Preserve official committee/candidate IDs and verify the
relationship and affiliation for the relevant election cycle. A PAC's spending
does not transform a PAC contribution into a candidate contribution. Unknown
affiliation remains unknown; recipient party never means donor party.

Preserve evidence-backed dates, exact USD decimal strings, original record IDs,
underlying transaction keys, transaction kind and routing. Resolve amendments,
refunds, reattributions, redesignations and memo entries conservatively. Count
conduit and ultimate-recipient reports once. Do not manufacture identity keys
from matching dates and amounts.

Counted refunds link explicitly to the original counted contribution in the
same package, with matching executive/recipient and evidence supporting the
relationship. Unresolved adjustments or duplicate reports remain uncounted.

## Completeness and acceptance

Check all executives and years in scope, reporting delays, unitemized activity,
unresolved identities, recipient relationships and source permissions. Normally
exclude state/local records. No accepted donation does not mean no donation.
Report complete-within-declared-scope, partial or blocked coverage with evidence.

Save JSON in the user's ignored local-data directory. Use the Docker CLI where
the project requires Docker; install no host dependencies. Validate and preview
before explicit import acceptance. Research informs human judgment alongside
business fundamentals; never recommend trades solely from reported donations.
