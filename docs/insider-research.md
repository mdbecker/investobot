# Management, compensation and insider research

V2.9 records source-backed management roles, reported executive compensation,
SEC Section 16 transactions and beneficial ownership observations for one issuer.
The external agent researches through its authorized browser; a human reviews
original sources; Investobot validates and stores immutable research. No filing
API, scraper, monitoring job, brokerage connection or new credential is needed.

## Setup and acceptance

Build and run everything in Docker. Discover the authoritative input model and
portable skill before preparing research:

```sh
docker compose build
docker compose run --rm -T app invest research skills show investobot-management-insiders
docker compose run --rm -T app invest research skills install --agent codex --workspace /app
docker compose run --rm -T app invest schema
docker compose run --rm -T app invest tools describe research.insiders.import
```

For Claude Code use `--agent claude-code`. This copies all bundled instructions
into project-local skills; it never executes them. Modified canonical files
require reviewed `--confirm`; unrelated user files remain preserved.

Ask the agent to research the verified legal issuer, ticker, CIK and requested
period/cutoff with `investobot-management-insiders`. Verify any linked canonical
security ID; research cannot register or reclassify a security. Save complete JSON
under ignored `local-data/insiders.json`, without raw filings or personal contact
details. Validate and preview before a human authorizes acceptance:

The current insider input contract is `1.1`, trusted skill version `1.1.0`, and
fresh SQLite schema 9. Explicitly review and update older `1.0` JSON before a new
import; optional new linkage/locator fields default to null. Accepted historical
packages are never rewritten. Existing research domains retain their versions.

```sh
docker compose run --rm -T app invest research insiders validate /app/local-data/insiders.json
docker compose run --rm -T app invest research insiders import /app/local-data/insiders.json
# After original-source review and explicit human approval:
docker compose run --rm -T app invest research insiders import /app/local-data/insiders.json --yes
docker compose run --rm -T app invest research insiders list --ticker TICKER
docker compose run --rm -T app invest research insiders show RUN_ID
docker compose run --rm -T app invest research insiders summary RUN_ID
docker compose run --rm -T app invest research insiders activity RUN_ID --person PERSON_ID
docker compose run --rm -T app invest research insiders ownership RUN_ID --person PERSON_ID
```

Validation, preview and reads do not create the selected database. Confirmation
writes research only in one atomic transaction; identical canonical input is
UNCHANGED, while corrections create another immutable run. Financial state,
prices and plan stale status stay unchanged. List projects compact stored metadata;
only show retrieves the full package. Unknown run/person IDs fail explicitly.

## Complete fictional walkthrough

[tests/fixtures/insiders.json](../tests/fixtures/insiders.json) is a complete offline
package for Fictional Systems Inc. (`FCSI`), with two reporting owners, proxy
compensation, Form 3 ownership, Form 4 activity, an amendment and Form 5 duplicate/
unresolved rows. URLs and identities are fictional test evidence, not verified
SEC records. Use a disposable container database without mounting the private
ledger or installing host packages:

```sh
docker build -t investobot-insiders-demo .
docker run --rm -i --network none \
  -e INVEST_DB=/tmp/insiders-demo.db -e INVEST_PROMPTS=/data/prompts \
  investobot-insiders-demo sh <<'SH'
uv run --locked invest research insiders validate tests/fixtures/insiders.json
uv run --locked invest research insiders import tests/fixtures/insiders.json
# Explicit acceptance of fictional demo data in this disposable database:
uv run --locked invest research insiders import tests/fixtures/insiders.json --yes
uv run --locked invest research insiders list --ticker FCSI
SH
```

The database disappears with the container. To inspect reports in the same demo,
append `uv run --locked invest research insiders summary RUN_ID` (or `activity`
or `ownership`) inside the heredoc, replacing RUN_ID with the import result ID.

Expected effective observations include 100 purchased common shares, 120 sold
common shares after the amendment, 200 derivative exercise units, a grant of 50,
tax/exercise payment of 10, gift of 5 and OTHER code J quantity 3. The original
100-share sale, linked repeat and unresolved 999-share row remain inspectable but
do not inflate effective totals. P purchase venue remains UNKNOWN. Reported
salary is 100000 USD, stock-award grant-date value 200000 USD and summary total
300000 USD; these are separate disclosures, never a fabricated 600000 total.
Ownership shows 100 then 125 common shares as dated observations, never 225.

## Reviewing corrections

An amendment alone does not prove that a specific earlier row was corrected.
For ownership, supply `supersedes_id` pointing to its same-run original row and
`correction_source_locator` identifying the quantity/date correction disclosure.
Verify the same issuer/owner CIK, instrument title, table, direct/indirect form and
nature, matching Form 3/A, 4/A or 5/A base form, exact original accession and
nonpredating amended filing. Retain both original and amended quantities/dates.
Later amendments reference the immediately preceding amended row and accession;
branches, cycles, cross-run links and duplicate/unresolved targets are rejected.

For example, Form 4 reports 125 directly held common shares on May 2 and its
linked 4/A specifically corrects that row to 120 on May 2. Ownership observations
retain both: 125 is SUPERSEDED and 120 is EFFECTIVE. Only 120 appears in
`latest_observations`; balances are never added. The new optional linkage fields
on the corrected ownership observation are:

```json
{
  "supersedes_id": "original-holding",
  "duplicate_of_id": null,
  "correction_source_locator": "Form 4/A footnote 1 correcting shares held to 120"
}
```

This is a field excerpt, not a complete import. Use `invest schema` for the full
model. A verified duplicate requires the same holding identity, date and quantity
plus explicit `duplicate_of_id`; numerical equality alone is insufficient.
Unlinked amended holdings remain UNRESOLVED. Two unlinked observations at the
same latest effective date, whether quantities disagree or agree, appear under
`conflicting_latest_observations` with warnings and no uniquely current selection.
Every observation includes status, `is_effective` and `exclusion_reason`; historical
rows and source references remain inspectable. Reports cover one run only.

A transaction correction may change date or SEC code when the matching Form 4/A
or 5/A and `correction_source_locator` explicitly support the changed field.
Verify issuer/owner, instrument/table, ownership form/nature and A/D direction
remain identical. Notes alone do not establish this evidence. A documented
May 2 M row corrected to May 3 P retains both filings; the original is superseded,
and only the amended P contributes under May 3. Purchase venue remains UNKNOWN
without separate explicit evidence. Unsupported corrections stay UNRESOLVED and
excluded, rather than doubling activity or erasing the original.

For human acceptance, read the original and amendment side by side, verify the
exact row and accession chain, and check the cited explanation against every
changed field. Structural validation cannot prove what the filing actually says.

## Interpreting reports

P means reported open-market **or private** purchase; only explicit cited venue
evidence establishes OPEN_MARKET/PRIVATE. S is reported sale. M exercises/
conversions, A grants, F tax/exercise payments and G gifts retain separate
categories. Other or compound codes stay OTHER with their original code. A/D
direction, instrument title, derivative table and direct/indirect ownership remain
distinct. Disclosed 10b5-1 status is not a claim about intent or legality; missing
historical disclosure is NOT_DISCLOSED.

Only verified unique effective rows contribute to totals. Explicit supported
same-run correction/duplicate links preserve earlier rows; unresolved rows stay
visible with warnings. Known P/S prices produce reported gross line values by
currency, not realized gains, tax basis, returns or cash compensation. Unknown
prices are null, not zero; no FX is inferred. Ownership reports latest as-filed
observations plus dated history, not reconstructed current balances. Compensation
retains person/fiscal year, valuation basis and arrangements separately.

Primary issuer disclosures need matching sourced issuer CIK or exact legal issuer
publisher attribution. Future tenure is accepted only from `ISSUER_AGREEMENT`
evidence whose locator explicitly describes an expected/scheduled event. Vesting,
performance and clawback conditions use `UNQUANTIFIED_TERMS` and null value/currency.
If indirect nature is absent, limitations must explicitly explain that indirect
ownership disclosure gap. Corrections link the original economic row and matching
form type; they cannot replace an excluded duplicate.

## Human source review and release gates

For real acceptance, independently check the original SEC/issuer pages:

- Confirm issuer CIK, owner CIK/name and exact filing-person association; a
  ten-percent entity holder is not automatically an executive.
- Compare Forms 3/4/5 rows, table type, code, A/D, quantity, price/currency,
  footnotes, indirect nature, dates and plan/venue disclosures.
- Check amendment/original accessions and supported row links. Numerical
  similarity alone does not prove a repeated economic event.
- Verify proxy fiscal year, grant-date fair values, reported totals and cited
  tenure/compensation arrangements. Unknown dates and payments remain unknown.
- Record gaps, late filings, unresolved matches and limited scope. Citations and
  strict validation cannot establish factual truth, rights or exhaustive coverage.

The separate real-data gate additionally verifies an original Form 4 and available
Form 4/A correction, including both ownership balances and explanatory footnotes.
The broader V2.9 gate uses one U.S. issuer with Form 3 holdings, representative
Form 4 purchase/sale/exercise/grant/tax rows, an amendment if available and DEF 14A
compensation. Compare originals and footnotes and document mismatches. Offline
fictional tests do not establish real extraction accuracy or remote CI success.

Schema 9 initializes fresh databases and rejects schema 8 and earlier without
migration or automatic deletion. Keep private ledgers unchanged and backed up;
use disposable data for evaluation. If deliberately discarding a selected
disposable ledger, follow [reset instructions](development.md#deliberate-schema-reset)
and preserve prompt files. Requirements remain in [PRD-v2.9.md](PRD-v2.9.md) and
its [corrections addendum](PRD-v2.9-Addendum-Amendment-Corrections.md).
