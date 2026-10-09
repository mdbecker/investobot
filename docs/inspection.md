# Local inspection and planning dashboard

The dashboard displays the same domain calculations and SQLite ledger as the
`invest` CLI. It has no broker connection, trading controls, chatbot or agent
runner. The external agent supplies research; the human decides and executes
trades manually.

Start with `docker compose up --build -d`, then open
[the local dashboard](http://localhost:8765). Compose publishes only on host
loopback. Keep that binding: this single-user app has no authentication and must
not be published to a network. Stop with `docker compose down`; `--volumes`
deletes persisted local state. Dependencies stay in the Docker runtime volume,
not inside the project bind mount. No host installation is required.

## Five primary areas

**Overview** shows accepted account/holding values, available known cash, the
active target's allocation drift, major household exposures, unresolved exposure,
tax-lot warnings and snapshot freshness/coverage. Source time and import time are
shown separately. Missing dates, cash, basis and classifications remain unknown.
Dollar and allocation calculations come from the server; browser formatting does
not calculate financial results. Household currencies cannot be combined without
an FX model.

**Targets** lists candidate portfolios and immutable versions. Inspect a saved
target to edit its complete JSON, or start a new cash-only draft template and
replace its allocations with your chosen registered canonical security IDs.
The template is not a recommendation. Registered IDs are visible in the security
catalogue. Weights are fractions totaling one; account eligibility, permitted
investments, cash floors, trade increments and ST/LT gain budgets belong in
planning constraints. Empty eligibility permits no planning. Saving an edit
creates another version. Activation selects the one active target; archiving
retains its history. Neither changes actual holdings. Compare a chosen version
with accepted holdings to inspect target-minus-current drift.

**Plans** generates hypothetical manual trades from a saved target/version.
Optional dated price observations must include price, currency, source and as-of
information; they do not update actual marks. Review proposed trades by account,
exact taxable lots, ST/LT gains, estimated tax effect, cash balances, assumptions,
warnings and remaining drift. The heuristic can leave a plan incomplete. Select
multiple saved alternatives to compare turnover, tax, trades and allocation;
source/price/tax differences remain explicit. `STALE` is visibly flagged when
actual source state changes. Regenerate before considering stale trades.
Generation, listing and comparison use the CLI's shared compact summary contract,
including tax totals, maximum remaining drift and an ordered preview of at most
five warnings. Choose **Review plan** to fetch full trades and assumptions for
one alternative. Full retrieval can produce a large response; use a Markdown
report download when reviewing without loading full JSON into an agent's context.
Markdown and JSON downloads reproduce persisted inputs/calculations and include
manual-execution guidance. Verify current status before acting on an old report.

**Prompt Library** displays full plain Markdown for copying into your coding
agent. Choose a bundled prompt or create a user prompt with a lowercase slug.
Editing a bundled prompt creates a local user override; deleting that override
restores the immutable bundled default. Only user prompts can be deleted.
Content stays text and is never interpreted as commands or executed. User prompts
live under `INVEST_PROMPTS` when explicitly configured, otherwise the Investobot
local data directory's `prompts` subdirectory. Compose explicitly uses
`/data/prompts` in its persistent ledger volume. Native listeners default to
`127.0.0.1`; Compose binds within the container and publishes only host loopback. Path traversal,
symlinks, oversized files and invalid slugs are rejected.

**Import & Reconcile** preserves preview → reconcile → explicit accept:

1. Choose a synthetic account alias, provisional institution profile and tax
   status. Supply a source date only when it is known.
2. Leave positions/lots coverage unchecked unless you know the page covers the
   whole relevant inventory. Partial pages must not silently delete known rows.
3. Paste or open HTML. Raw HTML remains in memory, is cleared after preview and
   never enters SQLite or server logs. Keep saved private files outside Git.
4. Preview normalized quantities, valuations, lots and warnings, then compare
   with accepted state. Differences do not establish transactions. Account
   metadata discrepancies show incoming and accepted values and explain that
   holdings acceptance preserves account configuration. Use the CLI's separate
   previewed `account update --file` and confirmed `--yes` for corrections.
   Classification suggestions identify the canonical security ID, accepted type
   and observed type. An existing `OTHER` security stays `OTHER` when the page
   suggests a supported type; otherwise valid quantity and value updates can
   still be accepted. The warning provides the explicit classification command
   for review with a verified source. A contradiction between two known types
   rejects acceptance of the whole snapshot.
5. Review source-date status and latest known source date. Ordinary acceptance
   is blocked when an older dated or changed undated snapshot would supersede
   dated state. A separate deliberate override requires a nonempty explanation.
   First undated imports remain available with warnings. No source date is
   inferred from import time, even after an override.

Correct an existing unknown security type through the CLI's previewed
`security classify SECURITY_ID --asset-type ETF --source "Verified reference"`,
then explicitly confirm with `--confirm`. Current holdings retain quantities,
values, basis and lots; historical snapshots remain fixed. Later incomplete imports
preserve the corrected type. Classification/account corrections and accepted
snapshot changes can make saved plans stale, so inspect current plan status
before considering a previously exported report.
Newly imported securities may retain their source-supplied initial classification;
this does not authorize later changes to an existing canonical security. Snapshot
suggestions do not create classification history or establish verification.

Vanguard, Fidelity NetBenefits and PNC aliases remain provisional until real
anonymized HTML samples validate their table shapes. No real samples have been
provided. Never supply broker credentials or cookies.

## Secondary tools

**Record activity** is for transactions already executed by the human. Supply a
stable unique `activity_id`; preview before confirming. Identical retries are
no-ops, conflicting IDs fail. Taxable sales should include exact executed
`lot_allocations`. Unknown selection marks basis/lot state unresolved and never
becomes FIFO silently. Execution prices do not replace portfolio market marks.
Cross-account/security transfers require classification and manual review and
remain unsupported for recording.

**Analysis workbench** exposes household exposure, tax lots, hypothetical sale
analysis, harvesting, scenarios, historical risk, fund holdings/comparison and
known-bond calculations. Edit synthetic templates with loaded identifiers and
researched assumptions. Risk is hypothetical current-weight historical behavior,
with disclosed cash-return assumptions. Every analysis uses the same domain
function as the CLI and a read-only provider cache. It changes neither accepted
state nor cache contents. Market-dependent analysis needs configured FMP data or
explicit synthetic fixtures; see [data source setup](data-sources.md). Missing
external data remains an error/warning, not an invented observation.

## Local API and protections

GET routes: `/api/overview`, `/api/summary`, `/api/state`, `/api/targets`,
`/api/targets/ID?version=N`, `/api/targets/ID/diff?version=N`, `/api/plans`,
`/api/plans/ID`, `/api/plans/ID/report?format=markdown|json`, `/api/prompts`, and
`/api/prompts/SLUG`.

POST routes: `/api/import`, `/api/reconcile`, `/api/apply`, `/api/activity`,
`/api/analyze`, `/api/targets/save`, `/api/targets/activate`,
`/api/targets/archive`, `/api/plans/generate`, `/api/plans/compare`,
`/api/prompts/save`, and `/api/prompts/delete`. Target save wraps the validated
input in `target`; activation/archive require `target_id` and `confirm: true`.
Plan generation accepts `target_id` plus optional `as_of`, `version`, `prices`
and `name`. Comparison accepts `plan_ids`. Prompt writes accept `id` and, for
save, `content`.

`GET /api/plans` returns `{"plans": [summary, ...]}`; generation returns
`{"plan": summary}`; comparison returns compact summaries plus compatibility
flags, warnings and `ranking: null`. These summaries use saved financial values
and current stale status. `GET /api/plans/ID` retains complete detail, and report
downloads retain the original persisted report without truncation.

Requests require local Host headers; POSTs require matching Origin and JSON.
Bodies larger than 2 MB are rejected. Invalid inputs return HTTP 400, inconsistent
state 409, internal errors 500 and origin/host rejections 403. JSON errors include
the CLI's domain exit code; inspect that code to distinguish external data errors
from invalid input. Responses disable caching
and include same-origin content protections. No endpoint runs arbitrary agents,
commands, shell processes or trades. Source financial data and HTML never enter
server access logs.
