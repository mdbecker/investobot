# Executive political-contribution research

Investobot stores reviewed company research separately from household financial
state. External agents research public executive roles and permitted evidence;
Investobot validates the resulting JSON and calculates descriptive USD totals.
Research never changes holdings, classifications, targets or saved plans. The
requirements are preserved in [PRD-v2.5.md](PRD-v2.5.md).

## Setup and workflow

No API account, secret, brokerage credential or host package installation is
needed for the offline synthetic MVP. Build and run the existing Docker image.
Keep research files in ignored `local-data`; container paths begin `/app`.

```sh
docker compose build
./scripts/invest research skills show investobot-political-contributions
./scripts/invest research skills install --agent codex --workspace /app
./scripts/invest tools describe research.political.validate
./scripts/invest tools describe research.political.import
./scripts/invest schema
./scripts/invest research political validate /app/local-data/political-research.json
./scripts/invest research political import /app/local-data/political-research.json
```

The project-local skill is recognized by the external agent. Ask that agent to
use `investobot-political-contributions`; for Claude Code install with
`--agent claude-code`. Investobot does not execute the skill, scrape political
sites or provide an FEC client. General prompt CRUD is retired. Preserve operator
overrides as host notes for review; see [research skills](research-skills.md).

Review the company and executive identity evidence, reporting period, source
permissions, recipient relationships, ambiguities and transaction identifiers.
Only then explicitly accept the preview:

```sh
./scripts/invest research political import /app/local-data/political-research.json --yes
./scripts/invest research political list --ticker EXAMPLE
./scripts/invest research political show RUN_ID
./scripts/invest research political summary RUN_ID
```

`RUN_ID` is returned by import. Identical normalized packages reuse that ID;
changed packages become separate immutable runs. List returns compact metadata,
show returns the evidence package, and summary calculates counted transactions.
Validation and preview are read-only. Confirmation writes research records only.
Stdout is JSON; errors use stderr and existing input/external/state/internal exit
codes 1/2/3/4.

## Source review and privacy

Named contributor disclosure data is not automatically reusable merely because
it is public. Before researching person-attributed transactions, a human must
review the intended use and applicable source restrictions. The attached PRD
identifies the FEC's [sale/use guidance](https://www.fec.gov/updates/sale-or-use-contributor-information/)
and [contributor-information guidance](https://www.fec.gov/updates/use-of-contributor-information/)
as references for that review.

Agent-written `rights_basis`, package `rights_status`, and `--yes` never grant
permission. The importer checks independently configured reviewed policy.
Restricted FEC-derived donor information remains blocked unless a separate
reviewed policy authorizes its specific intended use. Copies on aggregators or
mirrors do not remove the original restriction. Candidate/committee metadata
and executive biographies can support research without named transactions.
When permissions remain unresolved, submit no contribution records and preserve
the blocked/partial coverage and limitations.

Save the reviewed policy separately from agent-produced research, for example
`local-data/research-policy.json`, and set `INVEST_RESEARCH_POLICY` to its
container path. Do not accept a generated policy as a substitute for human
review. The following illustrates the format for a fictional offline source;
it does not authorize any real disclosure source:

```json
{
  "intended_use": "INVESTMENT_RESEARCH",
  "review_reference": "Documented human review for this intended use",
  "sources": [
    {
      "origin": "https://records.example",
      "allow_individual_contributor_data": true,
      "fec_derived": false,
      "allow_fec_derived": false
    }
  ]
}
```

An origin includes scheme and host (and port when present), without a path.
Permissions apply only to origins explicitly reviewed. FEC records and mirrors
identified as FEC-derived require the additional `allow_fec_derived` permission;
leave it false unless the separate review supports that intended use. Missing
policy denies person-attributed transactions by default. Invoke both validation
and import with the same reviewed policy:

```sh
docker compose run --rm -T -e INVEST_RESEARCH_POLICY=/app/local-data/research-policy.json app invest research political validate /app/local-data/political-research.json
docker compose run --rm -T -e INVEST_RESEARCH_POLICY=/app/local-data/research-policy.json app invest research political import /app/local-data/political-research.json --yes
```

Retain source links and necessary evidence, never raw contributor pages, home
addresses, ZIP codes, personal contact details, birthdays or unrelated personal
identifiers. Do not use the feature for fundraising, advertising, solicitation,
resale or donor lists. Recipient party describes the recipient; it is never an
executive's personal party or an ideological score.

## Reading results conservatively

Only verified records belong in `contributions`; uncertain matches belong in
`unresolved_matches`. Name alone is insufficient evidence. Candidate committee
relationships and recipient affiliation need evidence for the relevant period.
A PAC payment remains a PAC payment; its spending cannot create an executive's
candidate contribution.

USD amounts are decimal strings. Counted contributions are positive, documented
refunds are negative, and unresolved adjustments/memos do not affect totals.
Counted refunds require `original_contribution_id` referencing the original
counted contribution in the same package; evidence must support that link.
Contribution evidence must include a source beyond the executive's role biography.
That additional source must use `INDEPENDENT_DISCLOSURE`, `CONTRIBUTION_RECORD`,
`IDENTITY_CORROBORATION`, `EXECUTIVE_STATEMENT` or `PERMITTED_DISCLOSURE` as its
`source_type`; unrelated committee metadata cannot verify a contributor.
The validator checks structure and consistency. A human must still verify that
the cited evidence establishes identity, source origin and recipient relationships;
it cannot establish factual truth or legal permission from supplied assertions.
Underlying transaction keys prevent counting conduit and recipient reports
twice. Preserve real record identifiers rather than manufacturing identities
from a date/amount pair. Empty results mean no accepted evidence in the declared
scope, never proof that an executive made no contributions. Partial reporting,
unitemized activity and unresolved findings remain visible limitations.

## Schema and verification

Checksum-identified SQLite schema 1 initializes empty ledgers and rejects incompatible
development ledgers unchanged. Preserve private state; do not reset it to try a feature.
Future migrations require a verified pre-migration backup. Use disposable synthetic
ledgers for evaluation; see [operations](operations.md).

All test records are fictional. Reproduce checks without private ledger mounts:

```sh
docker build --tag investobot-ci .
docker run --rm --network none investobot-ci uv run --locked pytest
docker run --rm --network none investobot-ci uv run --locked ruff check --config pyproject.toml src tests
```

Local Docker evidence does not establish a GitHub Actions result. Work remains
on local `main` with conventional red/green commits and no pushes. Institution
HTML validation and live market-provider setup are separate manual release
gates; this feature adds neither an institution adapter nor market-data setup.

V2.6 hardening preserves a narrow set of public query locators: `record_id`,
`filing_id`, `transaction_id`, `committee_id`, `candidate_id` and
`accession_number`. Values must be short public identifier strings; duplicated
or unsafe locators are rejected. Other query parameters, URL credentials and
fragments are removed. Use optional `source_locator` for a disclosure section or
record that cannot be represented safely in a URL. Never put credentials there.

A supplied canonical `security_id` must exist. A supplied ticker must match that
security's canonical ticker or an explicitly sourced `ticker_aliases` entry
accepted through `security register`; company-name similarity and different
share-class tickers are insufficient. Research cannot register or reclassify a
security. Recipient groups retain verified committee and candidate identifiers.
