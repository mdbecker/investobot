# Canonical local data model

SQLite schema **version 3** uses standard `sqlite3`; no ORM is involved.
Portfolio and target tables store an `id` primary key and normalized JSON `data`.
Plans use dedicated baseline, summary and detail columns.
Financial amounts, quantities and fractional weights are Decimal strings; dates
are ISO 8601. Historical risk statistics/correlations can be JSON numbers.

| Table | Meaning |
| --- | --- |
| `accounts` | Synthetic aliases, tax classification, currency and explicit history completeness |
| `securities` | Canonical UUIDs, verified classifications and ticker/CUSIP/ISIN/FIGI aliases |
| `positions` | Accepted account/security quantity, valuation marks, known basis and lot state |
| `lots` | Original quantity/basis, acquisition date and remaining quantity |
| `cash_balances` | Known accepted account cash; absent rows mean unknown cash |
| `activities` | Confirmed manual facts, activity IDs, timestamps and executed lot allocations |
| `snapshots` | Immutable normalized audit snapshots and acceptance provenance; never raw HTML |
| `market_data_cache`, `fund_holdings_cache` | Normalized public provider observations and provenance |
| `trade_proposals` | Retained legacy proposal storage |
| `targets`, `target_versions` | Current target metadata/pointer and immutable full target versions |
| `plan_baselines` | Content-addressed immutable planning inputs, shared by alternatives |
| `plans` | Baseline reference, dates/status, compact summary, immutable details and assumption hashes |

Version 3 initializes a fresh database. Incompatible older databases are rejected
with reset instructions; startup never deletes data. There are no migrations,
backfills or legacy saved-plan readers. See the deliberate
[reset procedure](development.md#deliberate-schema-reset). Compose uses `/data/portfolio.db`; native defaults are
platformdirs Investobot directories. `INVEST_DB` selects an explicit path; two
paths are the same ledger only when they refer to the same mounted file.

## Accepted snapshots and security identity

Snapshots distinguish `source_timestamp` from `imported_at`, and carry
`positions_complete`, `lots_complete` and `cash_known`. Generic imports default
to incomplete positions/lots; missing rows do not imply liquidation. Incomplete
snapshots update observed positions and retain unobserved inventory. Explicit
complete coverage can remove inventory after validation. Retained lot quantities
that disagree with a position mark `lot_state=UNRESOLVED`, suppressing reliable
tax calculations. Known source dates stay source dates; absent dates stay unknown.
A position's fallback `as_of` does not make an unknown source timestamp current.

Application rejects inconsistent duplicates, invalid amounts, conflicting
identifiers and excessive lot quantities atomically. Older dated snapshots and
changed undated snapshots superseding dated observations need an explicit
`allow_older` override plus recorded justification. Accepted audit records
distinguish `OLDER_SOURCE_OVERRIDE` and `UNKNOWN_SOURCE_DATE_OVERRIDE`.
An override never turns import time into a source date. Identical acceptance is a no-op.
Accepted normalized snapshots and activity audit history survive later changes;
no raw account HTML is persisted in any table or server log. Reconciliation reports
values/conflicts and never invents activities from state differences.

Security UUIDs persist through ticker changes when strong verified identifiers
identify the same security. Explicit ISIN/CUSIP/FIGI bridges are shared by fund
comparison, household exposure and wash-sale analysis. Tickers are lower-confidence
aliases and cannot merge conflicting strong identities. Names alone do not prove
identity. Registration permits a researched future investment without creating
holdings or prices; unknown classification must never be guessed. Targets use
canonical UUIDs plus reserved `CASH`.

`security classify` previews an existing security correction and requires
`--confirm` plus nonempty provenance to write. OTHER can become a supported known
type; different known classifications conflict. `classification_history` stores
`previous_type`, `new_type`, `source` and `changed_at` on the security JSON record.
All corresponding current positions inherit the type, preserving financial
amounts and lots. Unknown later imports cannot revert the accepted type;
contradictory known types are rejected atomically. Historical snapshots are fixed.

Snapshot acceptance can create a genuinely new security with its observed initial
classification, but cannot upgrade an existing `OTHER` security. Reconciliation's
`classification_reviews` records `security_id`, `ticker`, `canonical_type`,
`observed_type` and `action_required: EXPLICIT_CLASSIFICATION` for those suggestions.
Otherwise valid holdings updates preserve the existing canonical/current position
type and create no classification-history entry. A known-versus-known conflict
rejects the entire snapshot atomically. Only a separately sourced, previewed and
confirmed `security classify` correction changes established classification.

Existing account configuration (`account_type`, `tax_status`, `history_complete`,
`currency`, `institution`, `name`, `active`) survives routine snapshot application.
New accounts start with their initially accepted metadata. Observed holdings,
lots, known balances and dates can update separately. Reconciliation exposes
`account_metadata_discrepancies` entries with `field`, `before` and `after`; it
also reports `source_date_status`, `latest_known_source_date`, `override_required`.

`account update` previews a supported partial update; `--yes` confirms it.
`metadata_history` entries store `reason`, `source`, `changed_at` and `changes`.
Account ID is immutable, unsupported fields fail, and currency cannot change
when positions or cash balances exist. Updates are atomic and idempotent.
Audit histories live in existing JSON rows and default safely for legacy records;
no new table or schema-version change is required.

## Confirmed activity and valuation

Every confirmed activity requires `activity_id`. Identical repeated facts are
no-ops; conflicting reuse fails atomically. `record-activity` previews until
explicit confirmation. A taxable sale's exact executed `lot_allocations` reduce
only named lots and known aggregate basis. Omitted allocations leave lot/basis
state unresolved rather than selecting FIFO. Purchase cost/fees become the new
lot's basis, while unknown pre-existing aggregate basis stays unknown.

Execution price is an activity fact and never replaces the remaining position's
accepted market price. Quantity changes can extend an existing accepted valuation
mark; missing marks remain unresolved. Scenario prices are explicitly hypothetical
assumptions. Public quote refresh only writes provider cache, never positions or
lots. Security/cross-account transfers need classification/manual review and
remain unsupported for recording.

## Targets and plans

A target contains name, description, status (`DRAFT`, `ACTIVE`, `ARCHIVED`),
fractional security allocations and validated planning constraints. Constraints
hold eligible accounts, permitted securities, excluded position IDs, cash floors,
trade increments, target tolerance, ST/LT gain budgets and price-age assumptions.
Unknown eligibility is never unrestricted access.

`targets` identifies the current version and current status; each full
`target_versions` row has its own `version_id`, integer version, target `id`,
allocations, constraints and timestamps. Edits append new versions. Activation
allows one active target, changes metadata only and never trades. Status changes
are overlaid for latest-version display; historical rows remain immutable.
Archive preserves versions and historical plan references.

A persisted plan references an immutable baseline by its SHA-256 planning-state
fingerprint. The baseline contains current accounts, identities, positions, lots,
cash, confirmed activity history and compact latest observation provenance.
Historical snapshot payloads remain in the ledger and are not copied into plans.
Identical planning inputs reuse one baseline; baseline and plan insertion are one
transaction. Plan-specific details store target version and snapshot IDs,
source dates, hypothetical prices with provenance, tax assumptions, constraints,
proposed actions, exact proposed taxable lots, exposure/tax calculations,
remaining drift, account cash, turnover, warnings and generated status. It never
modifies accepted holdings or provider caches. The heuristic is deterministic,
conservative and not globally optimal.

Displayed plan status becomes `STALE` when its source-state hash differs from the
current planning state; the persisted row is not rewritten. Unrelated older
audit snapshots do not invalidate it. Relevant quantities, basis, prices,
classification, account configuration, activity and observation provenance do.
Recalculation creates
a new plan. Classification corrections, account configuration changes and accepted
snapshots participate in this detection. `READY_FOR_HUMAN_REVIEW` is not approval to trade and is unavailable
when critical planning data remains unresolved. Report rendering uses persisted
inputs/results without recalculation. Its saved status is historical, so check
current `plan show` before considering an old report. Export confirms path and
SHA-256 content hash.

Compact generation/list/comparison responses share one domain summary derived
from saved metrics, with current stale status overlaid and original generated
status retained. Warnings are previewed in saved order (at most five), with their
total count. Unknown metrics remain null or safely empty. List and compare read
only `summary_json`, baseline IDs and required metadata/assumption hashes;
neither reads `details_json` or baseline `state_json`. The current planning state
is hashed once per operation. Explicit `plan show` joins one selected plan with
its baseline to reconstruct full details. Reports use those saved inputs/results.
The creation-order index is `plans_created_idx (created_at DESC, id DESC)`;
baseline and plan lookup use their primary keys. Foreign keys remain enforced
and SQLite uses a 5,000 ms busy timeout.

## Contracts, arithmetic and prompts

`invest schema` retains snapshot JSON Schema and adds registered tool contracts.
CLI parameter schemas come from registered commands; financial validation schemas
reuse Pydantic models where present. Success is JSON; failures are JSON on stderr
with documented domain exit codes. Read-only financial commands that write market
cache disclose that scope; simulation suppresses cache writes too.

Household summary, exposure, risk, drift and simulation reject mixed currencies;
no FX model is implemented. Unknown fund coverage/exposure remains visible and
weights are not silently rescaled to complete coverage. Tax outputs disclose
prerequisite completeness, hypothetical sale assumptions and wash-sale limitations.

Prompts do not add database tables. Bundled Markdown files are immutable; user
files/overrides live in configured `INVEST_PROMPTS` or the local Investobot data
`prompts` directory. Safe slugs identify files. User deletion restores a bundled
default where available. Prompt text is never interpreted as executable commands.


## Conservative input defaults

Omitted tax status becomes `OTHER`; it never establishes taxable treatment.
Omitted cash remains unknown and leaves previously accepted cash unchanged.
Explicit supplied cash asserts a known balance unless `cash_known: false` is
provided. Coverage and history assertions require JSON booleans.

An unchanged-quantity partial valuation refresh can retain known aggregate basis
when retained lots resolve it. Complete lot inventory must agree with supplied
aggregate basis within one cent. Conflicting strong identities for an already
held ticker require manual resolution. Fresh price observations do not establish
fresh holdings; stale or unknown quantity source dates force plan review.
