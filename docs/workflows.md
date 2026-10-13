# Human-operated agent workflows

Run all application commands in Docker from this checkout. `-T` disables terminal
allocation so stdin and JSON redirection remain clean. Create an ignored
`local-data` directory for private files; `/app/local-data` is the same directory
inside the project bind mount. Replace example dates with known dates and example
IDs with IDs returned by the CLI. Never place private files or credentials in Git.

## Synchronize an account

The human signs into Vanguard, Fidelity NetBenefits or PNC directly and saves HTML.
Institution aliases remain provisional until anonymized real pages pass tests.
The agent receives only the supplied local file, never broker credentials/cookies.
Phase 1 uses fictional supplied pages. Phase 2 reviewed original pages and live
provider validation follow foundation acceptance; the example below is a manual
real-data intake recipe for that later phase. Use `SYNTHETIC` for fictional pages.

```sh
docker compose run --rm -T app invest portfolio import - \
  --account taxable --institution vanguard --tax-status TAXABLE \
  --as-of 2026-10-08 --data-environment REAL < local-data/account.html > local-data/snapshot.json
docker compose run --rm -T app invest portfolio reconcile - < local-data/snapshot.json
```

Inspect quantity, valuation, basis, lot quantities, identifiers, cash and warnings.
The explicit source date above must be supported by the page or human confirmation;
otherwise omit it. `imported_at` does not prove freshness. Default incomplete
coverage and typed parser issues remain review evidence; explicitly overriding an
environment does not resolve omitted or inconsistent source rows. Default incomplete
coverage updates observed inventory without deleting absent rows. Add
`--positions-complete` and/or `--lots-complete` only when the human confirms the
entire relevant inventory is represented. Do not infer activity from differences.

Explicitly accept only after review/authorization:

```sh
docker compose run --rm -T app invest portfolio apply - --confirm < local-data/snapshot.json
docker compose run --rm -T app invest portfolio overview
```

Reconciliation reports `source_date_status`, `latest_known_source_date` and
`override_required`. Status is `KNOWN_CURRENT`, `OLDER_THAN_ACCEPTED`,
`UNKNOWN_SOURCE_DATE`, or `NO_PRIOR_DATED_STATE`. First undated imports and
updates without prior dated state carry warnings. Same-date/newer observations
remain subject to ordinary reconciliation.

Identical repeated snapshots are no-ops. Older source snapshots and changed
undated snapshots superseding dated state fail unless explicitly overridden
with a recorded justification:

```sh
docker compose run --rm -T app invest portfolio apply - --confirm --allow-older \
  --justification "Human verified correction to the previously accepted source page" \
  < local-data/corrected-snapshot.json
```

Actual changes make plans with different source state stale. Raw HTML is never
persisted; keep or delete your own private file deliberately.
An override records `OLDER_SOURCE_OVERRIDE` or `UNKNOWN_SOURCE_DATE_OVERRIDE`.
It does not date an undated observation or restore authoritative tax freshness.
Removing a known source date counts as a change even if quantities and values
match: a nonidentical undated import over dated state still requires review.

## Correct classification and account configuration

Find the canonical security ID in `portfolio overview`. Verify classification
using issuer documentation, then preview and explicitly confirm:

```sh
docker compose run --rm -T app invest security classify SECURITY_ID \
  --asset-type ETF --source "Human-verified issuer documentation and date"
docker compose run --rm -T app invest security classify SECURITY_ID \
  --asset-type ETF --source "Human-verified issuer documentation and date" --confirm
```

Replace the ID and provenance with verified facts. Only an existing OTHER
classification can change to a known type; a different known type is rejected.
Current positions inherit the correction without changing quantity, valuation,
basis or lots. Historical snapshots stay unchanged. Subsequent unknown source
classifications preserve the correction; contradictory known types require review.

During reconciliation, inspect `classification_reviews`. Each suggestion contains
the canonical `security_id`, `ticker`, `canonical_type`, `observed_type` and
`action_required: EXPLICIT_CLASSIFICATION`; review this through the CLI.
Accepting an otherwise valid holdings snapshot leaves an existing `OTHER` type
unchanged. Verify the suggested type against issuer documentation, then run the
preview and confirmed commands above with the actual ID and sourced provenance.
Confirmed corrections are audited and identical repeats are no-ops. New securities
can retain their initially accepted observed type. An established known type
conflicting with another known type rejects the entire snapshot, including its
holdings, cash and metadata changes.

Routine snapshots preserve existing `account_type`, `tax_status`,
`history_complete`, `currency`, `institution`, `name` and `active`. Initial accepted
metadata establishes a new account's configuration. Reconciliation reports
`account_metadata_discrepancies` while allowing valid holdings updates. Change
configuration separately, using a file such as `local-data/account-changes.json`:

```json
{
  "account_type": "Roth IRA",
  "tax_status": "TAX_FREE",
  "reason": "Correct the previously entered account classification",
  "source": "Human-verified account documentation"
}
```

Replace the example with the account's actual verified fields and provenance:

```sh
docker compose run --rm -T app invest account update ACCOUNT_ID \
  --file /app/local-data/account-changes.json
docker compose run --rm -T app invest account update ACCOUNT_ID \
  --file /app/local-data/account-changes.json --yes
```

Only supplied supported fields change. ID is immutable; currency changes require
no existing positions or cash balances. Nonempty reason/source are required.
Previews never write; confirmed updates are atomic and audited; identical repeats
add no audit entry. Recheck saved plans after either correction: current status
can become STALE while saved assumptions and historical report content remain fixed.

## Tax-loss harvesting and fund comparison

```sh
docker compose run --rm -T app invest tax lots --as-of 2026-10-08
docker compose run --rm -T app invest tax harvest-candidates --as-of 2026-10-08
docker compose run --rm -T app invest tax analyze \
  --account taxable --security VTI --quantity 25 --price 200 \
  --sale-date 2026-10-08 --method HIFO --fee 5
docker compose run --rm -T app invest fund holdings VTI
docker compose run --rm -T app invest fund compare VTI ITOT
```

The price/date/quantity are hypothetical inputs to replace with researched
assumptions; these are not recommended trades. Missing basis, unresolved lots or
unknown source dates prevent reliable tax estimates. Review ST/LT results,
household purchases including retirement accounts, unknown outside histories,
future purchases and substantially-identical limitations. Current tax effects
require explicitly configured rates and are never guaranteed savings.

Use Chrome for current issuer disclosures and qualitative research. Compare all
available fund holdings, partial/unresolved coverage and usable history periods.
Similarity does not establish wash-sale legality. [FMP setup](data-sources.md)
is required for live market data; explicit fixture mode works offline:

```sh
docker compose run --rm -T \
  -e INVEST_FIXTURES=/app/tests/fixtures/fmp-synthetic.json \
  app invest fund compare AAA BBB
```

## Register researched investments and save targets

Targets use canonical registered security IDs plus `CASH`, not ticker/class labels.
Inspect `portfolio overview`'s `state.securities` or position `security_id` fields.
For a researched candidate not already registered, write a verified metadata
payload to `local-data/security.json`:

```json
{
  "ticker": "VTI",
  "name": "Vanguard Total Stock Market ETF",
  "asset_type": "ETF",
  "currency": "USD",
  "source": "Replace with your human-verified dated issuer reference"
}
```

Verify every field and source before registration; this example illustrates the
payload and is not a recommendation. Strong identifiers may be included when
verified. Registration updates the local security catalogue, never holdings.

```sh
docker compose run --rm -T app invest security register - < local-data/security.json
```

Copy the returned `id` into target/constraint inputs. Research account access:
restricted 401(k) accounts must name only permitted investments. Unknown access
must not become unrestricted trading. A complete target file has this shape:

```json
{
  "name": "Balanced candidate",
  "description": "Explain the researched allocation rationale",
  "target_allocations": {
    "VERIFIED_EQUITY_SECURITY_ID": "0.65",
    "VERIFIED_BOND_FUND_SECURITY_ID": "0.30",
    "CASH": "0.05"
  },
  "planning_constraints": {
    "eligible_accounts": ["taxable", "ira"],
    "permitted_securities": {
      "taxable": ["VERIFIED_EQUITY_SECURITY_ID", "VERIFIED_BOND_FUND_SECURITY_ID"],
      "ira": ["VERIFIED_EQUITY_SECURITY_ID", "VERIFIED_BOND_FUND_SECURITY_ID"]
    },
    "cash_minimums": {"taxable": "500", "ira": "0"},
    "short_term_gain_budget": "0",
    "long_term_gain_budget": "5000",
    "target_tolerance": "0.01"
  }
}
```

Replace every placeholder with actual canonical IDs and loaded account aliases.
The allocation is an illustrative template, not an investment recommendation.
Weights total one within `0.000001`; dollar gain budgets and weights are Decimal
strings. Save three separately researched candidates, for example conservative,
balanced and growth, as complete files with their own names, rationale, actual
security choices and valid weights:

```sh
docker compose run --rm -T app invest target save - < local-data/conservative.json
docker compose run --rm -T app invest target save - < local-data/balanced.json
docker compose run --rm -T app invest target save - < local-data/growth.json
docker compose run --rm -T app invest target list
docker compose run --rm -T app invest target diff BALANCED_TARGET_ID
```

Editing supplies an existing `id` in a complete new payload and creates an
immutable version. Inspect older versions with `target show TARGET_ID --version 1`.
`target activate TARGET_ID` explicitly chooses one active target; archive retains
history. These operations do not execute trades or change actual account state.

## Generate, compare and export manual trade plans

```sh
docker compose run --rm -T app invest policy approve --file /app/local-data/reviewed-policy.json
docker compose run --rm -T app invest policy approve --file /app/local-data/reviewed-policy.json --confirm
docker compose run --rm -T app invest plan propose --file /app/local-data/conservative-request.json \
  --policy APPROVED_POLICY_ID --mode contributions-only --as-of 2026-10-08
docker compose run --rm -T app invest plan propose --file /app/local-data/balanced-request.json \
  --policy APPROVED_POLICY_ID --mode contributions-only --as-of 2026-10-08
docker compose run --rm -T app invest plan propose --file /app/local-data/growth-request.json \
  --policy APPROVED_POLICY_ID --mode contributions-only --as-of 2026-10-08
docker compose run --rm -T app invest plan list
docker compose run --rm -T app invest plan show PLAN_A
docker compose run --rm -T app invest plan compare PLAN_A PLAN_B PLAN_C
docker compose run --rm -T app invest report export PLAN_A \
  --format markdown --output /app/local-data/conservative-report.md
docker compose run --rm -T app invest report export PLAN_A \
  --format json --output /app/local-data/conservative-report.json
```

Replace returned target and plan IDs. Keep actual source state and price/date/tax
assumptions the same across alternatives for a common baseline; comparison flags
differences and supplies no single ranking score. Optional `--version N` fixes a
target version. Optional `--prices /app/local-data/prices.json` supplies observations
keyed by canonical security ID, each containing `price`, `as_of`, `currency` and
`source`. Hypothetical prices never overwrite portfolio marks; stale/unknown
prices can block trades. Individual bonds do not receive automatic trade proposals.

Generate, list and compare return compact summaries: plan identifiers, current
and generated statuses, saved financial metrics and a preview of up to five
warnings. Comparison flags incompatible assumptions without ranking alternatives.
`plan show` intentionally retrieves the full saved plan and can return large JSON;
use it when detailed actions or assumptions are needed. Prefer the Markdown export
above for human review without loading complete portfolio histories into the
agent's conversation. Full warnings and analyses remain in show/report outputs.

Each request includes a saved `target_id` and explicit sourced `prices`; inspect
`tools describe plan.propose` and [trading policy](trading-policy.md) before filling
the request. Contribution-only planning uses confirmed same-account cash and
never sells. Quarterly rebalancing requires an approved window and sufficient
drift, prioritizes permitted retirement sales, and bounds taxable sales by annual
positive estimated tax-cost headroom. Known losses do not replenish headroom.
Review exact lots, fees, permissions, unknowns and remaining drift. Every proposal
requires a human decision and manual execution.

The preserved `plan generate` command is an unapproved hypothetical scenario
primitive. Its synthetic outputs always require typed policy review; REAL inputs
are blocked without actions or saving. It cannot substitute for policy approval.

Report export returns a JSON path/content-hash confirmation. Exports reproduce
saved inputs and calculations without recomputation; status in an old report is
historical. Recheck `plan show` for `STALE` before acting. Generate a new plan when
actual state changes instead of silently editing the old plan.

## Simulate without accepting activity

Supply a JSON array of hypothetical actions in `local-data/actions.json`:

```json
[
  {"type":"SELL","account_id":"taxable","security":"AAA","quantity":"5","price":"100","date":"2026-10-08","method":"HIFO"},
  {"type":"BUY","account_id":"taxable","security":"BBB","quantity":"5","price":"100","date":"2026-10-08"}
]
```

AAA/BBB and amounts here are synthetic examples. Substitute loaded/registered
identities and explicit assumptions; never fabricate basis or trading eligibility.

```sh
docker compose run --rm -T app invest portfolio simulate - < local-data/actions.json
```

Simulation returns before/after cash, allocations, exposure, selected lots,
ST/LT gains and wash-sale warnings, changing neither actual state nor cache.
Current-weight historical risk is hypothetical performance, with zero cash
returns and other assumptions disclosed. Household tools reject mixed currencies
because no FX conversion model is implemented.

## Confirm activity after manual execution

After the human executes a trade, write its actual facts and stable confirmation
alias. A taxable sale must use the broker's executed lots, not a guessed selection:

```json
{
  "activity_id": "unique-manual-confirmation-alias",
  "account_id": "taxable",
  "type": "SELL",
  "security": "REGISTERED_SECURITY_ID",
  "quantity": "2",
  "price": "100",
  "date": "2026-10-08",
  "fee": "1",
  "lot_allocations": [{"lot_id":"EXECUTED_LOT_ID","quantity":"2"}]
}
```

Replace placeholders and example values with confirmed facts. Preview first:

```sh
docker compose run --rm -T app invest portfolio record-activity - < local-data/activity.json
# Only after confirmation that the human executed these exact facts:
docker compose run --rm -T app invest portfolio record-activity - --yes < local-data/activity.json
```

Identical `activity_id` retries are no-ops; different facts with the same ID fail
atomically. Exact allocations reduce only those lots and known aggregate basis.
If lot selection is unknown, omit allocations: quantity/cash update but lot/basis
state becomes unresolved and tax tools cannot treat it as authoritative. Never
substitute FIFO for unknown executed selection. Execution price is an activity
fact, not the remaining portfolio's valuation mark. Cross-account/security
transfers require classification/review and remain unsupported for recording.
Reconcile a later broker snapshot to confirm post-trade holdings without inventing
additional activities from its differences.
