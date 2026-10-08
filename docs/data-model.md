# Canonical local data model

SQLite schema **version 2** uses standard `sqlite3` and small explicit migrations;
no ORM is involved. Tables store an `id` primary key and normalized JSON `data`.
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
| `plans` | Immutable hypothetical plans with their reproducible inputs/results |

Migration from version 1 adds `targets`, `target_versions` and `plans` without
replacing existing tables or historical financial rows. Databases with a newer
unsupported schema are rejected. Back up the local database before changing
runtimes or versions. Compose uses `/data/portfolio.db`; native defaults are
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
identifiers and excessive lot quantities atomically. Older snapshots need an
explicit override plus recorded justification. Identical acceptance is a no-op.
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

A persisted plan stores target version, actual source state/hash and snapshot IDs,
source dates, hypothetical prices with provenance, tax assumptions, constraints,
proposed actions, exact proposed taxable lots, exposure/tax calculations,
remaining drift, account cash, turnover, warnings and generated status. It never
modifies accepted holdings or provider caches. The heuristic is deterministic,
conservative and not globally optimal.

Displayed plan status becomes `STALE` when its source-state hash differs from the
current canonical state; the persisted row is not rewritten. Recalculation creates
a new plan. `READY_FOR_HUMAN_REVIEW` is not approval to trade and is unavailable
when critical planning data remains unresolved. Report rendering uses persisted
inputs/results without recalculation. Its saved status is historical, so check
current `plan show` before considering an old report. Export confirms path and
SHA-256 content hash.

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
