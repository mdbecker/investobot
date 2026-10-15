# Current product and architecture contract

Investobot is a local portfolio ledger and deterministic research toolkit. An
independently supplied host agent gathers authorized evidence and invokes the
Docker CLI; humans approve accepted facts and execute every trade manually.
This living contract replaces historical PRDs. Detailed commands belong in
[workflows](workflows.md), setup in [operations](operations.md), and evidence in
[readiness](readiness.md). Git history preserves earlier specifications.

## Execution and storage

One application image/service provides the JSON CLI and thin persisted read-only
viewer. `./scripts/invest` is a POSIX bridge to `docker compose run --rm -T app
invest`. No host Python, agent runtime, scheduler, prompt service, RPC layer,
sidecar, ORM or database service is needed. Dependencies live in `/opt/venv`.

The project binds to `/app`; private host `local-data/state` binds to `/data` and
holds SQLite, sidecars, referenced artifacts and receipts. Input, work and agent
notes are ordinary private host files. Pre-create restrictive directories and
verify invoking-user access. Exclude private data, secrets, HTML, SQLite/backups,
generated Investobot skill copies and host environments from Git/builds; exclude
whole `.agents/` and `.claude/` trees from images, preserving canonical `skills/`.
Unrelated skills and files must remain intact.

Initialize fresh host-backed state through existing application behavior; no
migration, development-state copy, schema alteration or volume deletion is part
of setup. There is no shipping schema-upgrade command. Schema version/checksum
validation remains mandatory; specify the first actual upgrade when needed.

Bind mounts are not backups. Never copy live SQLite files. Online backup verifies
integrity, foreign keys and artifact hashes before atomic owner-only publication.
Restore stages and verifies before explicit confirmation and holds restore locks.
Every DB handle holds a shared filesystem lock until close, including read-only
queries; query-only enforcement is independent of mount permissions. Cleanup
removes only unreferenced managed staging under the publication lock.

Canonical skills are host-readable; installation is explicit/project-local,
rejects traversal/symlinks/nonregular destinations and protects edited resources.
Host notes are untrusted context, never automatically trusted skill instructions.
Installed skills use repository-root text for outside documents and relative
Markdown links only for resources copied within their bundle.

## Financial invariants

- SQLite is the sole writable financial truth, with FK ON, WAL, synchronous FULL,
  busy timeout 5000 and atomic related writes. No ORM/service framework. Schema 1
  includes the foundation checksum.
  Any separately specified future migration must be transactional/checksummed
  with verified pre-migration backup; no upgrade runner ships today.
  DuckDB is ephemeral/read-only; Parquet artifacts have manifests/hashes; vec0 is
  pinned/baked and derived indexes are rebuildable. Recovery loads verified vec0
  when required and verifies corpus retrieval as well as financial facts.
- Exact Decimal values use plain normalized strings. Scale calculation context to
  magnitudes; conserve low-order residues. Identifiers/source lexemes stay exact.
  Printed precision is explicit source evidence, never inferred from storage.
  Read-only summaries need the same magnitude-aware arithmetic as proposals.
  Import evidence completeness requires explicit position, lot and cash coverage;
  an unchanged import must retain its typed source diagnostics.
  Printed precision cannot supply a missing observed price: reconciliation must
  report typed incomplete valuation and retain other review evidence.
  Never invent identity, lots, basis, prices, classifications or cash coverage.
- Explicit REAL/SYNTHETIC provenance reaches parser and accepted facts. Mixed inputs
  cannot yield actionable proposals; blocking parser evidence cannot become clean
  accepted holdings. Unknown never means zero/current/complete/safe. Gate on typed
  issue fields, not warning prose. JSON success stdout/errors stderr use codes
  1 input, 2 external, 3 blocked/inconsistent, 4 internal; incomplete outcomes retain issues.
- Human-confirmed idempotent commands alone change facts. No trades, broker credentials
  or raw account HTML persistence. Partial imports preserve unobserved inventory;
  old observations cannot erase confirmed activity. Source/import dates differ;
  date-only same-day ambiguity requires reviewed ordering. Fresh reads on every
  command; no cross-command caches. Account settings remain authoritative.
- Strong IDs and sourced aliases share `security_identity.resolve`; ambiguous or
  conflicting matches fail. OTHER reclassification requires sourced preview/confirm;
  registration cannot bypass it. Lot IDs are globally unique; missing local IDs
  require indexed global checks. Protected exhausted confirmed lots remain history;
  identity membership never permits stale financial values.
- Specific executions preserve exact remaining adjusted basis and final residues;
  unknown selection is never FIFO. Fees stay separate; execution prices are not
  marks. REAL sales require verified sourced broker lot identity, identity review
  and explicit saleability. Retirement share sales need verified inventory but may
  have null basis/dates; never invent retirement gain/term. Taxable lots need basis/dates.
- No currency aggregation without FX. Quote TTL is 900 seconds; dataset TTL differs.
  Caches are not historical evidence and never update canonical marks/quantities.
  Hypothetical research/plans/backtests preserve holdings, marks, caches/events and
  fingerprints. Look-through preserves known numeric exposure and unknown residual,
  cycles/depth/path/vintage; completeness needs matching environment/source/date and
  visible persisted typed issues. Numeric coverage is separate from evidence quality.
- Actual performance needs complete dated checkpoints/flows and boundary marks.
  Household transfers need explicitly reviewed linked atomic legs with matching
  currency/environment/order, never inferred balance differences. Dense conventional
  XIRR retains every flow; nonconventional complexity remains typed review. Risk
  aligns every requested session; weekdays never establish exchange-calendar evidence.
- Targets are immutable fractions totaling 1 ±0.000001. Separate approved immutable
  policies have independent strict buy/sell/hold booleans and exact increments,
  floors/minimum notionals/freshness. Unknown permissions/fees remain review gates.
  Targets contain weights, eligible accounts and excluded positions; tolerance is
  presentation-only. Reject retired target execution fields. All three permission
  booleans are mandatory; buying requires holding permission. Restricted existing
  inventory gets human review, never automatic liquidation. Cash amounts alone
  never attest coverage: require explicit `cash_known:true`, including zero.
  Contributions-only never sells; rebalance uses cash first on any valid date without
  calendar/month/drift gates. Quarterly strategy is explicitly historical only.
- Annual USD positive tax-cost allowance uses confirmed taxable sales and explicit
  ST/LT rates/coverage. Losses do not replenish it; saved plans do not spend it.
  Rebalance and harvest share planned-date validation: match year/environment,
  require tax-history coverage through the planned date even without intervening
  recorded sales, and reject future attestations.
  Preserve independently safe cash-funded suggestions when tax evidence blocks sales.
  Mandatory household/IRA/spouse/DRIP/substantially-identical wash review remains;
  never certify legality or guaranteed savings. Harvest uses approved policy identity,
  verified loss lots, sourced replacement prices and both exact cash legs/fee residue.
- Plans pin source/policy/manifest/algorithm and simulate cash/lots/value before save.
  Current staleness is separate from immutable history. List/compare use compact
  projections; full detail stays explicit. No historical recalculation with fresh prices.


Use one recursive exposure engine and one planner. Synthetic preview saves nothing;
REAL proposals require saved targets and approved policies. Dataset publication
requires confirmation. Preserve source-only constituent amounts without ticker-based
identity claims, and combine compatible household dates without inventing chronology.

## Viewer and research

The dashboard is persisted/provider-free, GET-only and query-only. POST returns
405 before body/application-data access. Close handles before every response.
Publish on loopback only. No command/job/agent launch is exposed. Backtest lists
stay compact; detail and comparisons use immutable saved runs.

External agents research; humans verify original sources and rights. Strict
immutable structures cannot establish source truth or permissions. No scraping,
FEC/SEC clients, political scores, forecasts, monitoring or trade signals.
Acceptance is atomic/run-scoped and cannot register/reclassify securities or
refresh fund/market caches. Named-contributor evidence requires independently
reviewed rights, never an agent assertion or `--yes` alone.

Every requested specialty task needs explicit coverage. Preserve native hashes,
exact issuer/entity/period/definition/unit/basis comparability and independent
skill identities. News absence means NOT_REOBSERVED; terminal evidence controls
history. Insider corrections preserve filing/owner/person associations and
transaction codes. Fund diligence uses original exact-class identity and <=100
descending TOP_N holdings, without normalized weights or invented residuals.

Corpus adapters require explicit indexing permission and canonical
model/dimension/content compatibility before ranking; keyword fallback stays
explicit. No automatic personal/broker embeddings or generation adapter is
provided. Explicitly supplied vectors remain supported. Plain bonds use SciPy
cash flows; complex instruments remain unavailable, and fixed redemption does
not price embedded options.

## Acceptance boundaries

Vanguard, Fidelity NetBenefits and PNC remain PROVISIONAL; live FMP remains
UNVERIFIED. Synthetic tests and the CLI demo establish development behavior only.
No real documents/secrets are needed offline. See [data sources](data-sources.md)
for human account, entitlement and sample review requirements.

Use existing behavioral tests for pure refactors/deletions. New behavior and
confirmed bugs require the complete changed scenario set and observed test-only
red commit before implementation, followed by verified green. Run application,
dependency, test and lint work only in Docker, offline against disposable state;
install nothing on the host. No artificial internal mocks, skips or xfails.

Reuse valid checks when their relevant inputs have not changed. Mounted-source
verification may reuse a checked locked image when dependency and packaging
configuration is unchanged; label the bound source and image separately and do
not claim a newly baked image or wheel.

Keep `main` and conventional local commits; no remotes/fetch/push. Freeze parallel
writes before final verification. Stop after finite acceptance. Benchmark rules
and the approved NOT PASSED exception are in [performance](performance.md).
No new benchmarking, profiling, optimization, broad audit or fuzz campaign is
authorized by cleanup. Fuzzing requires explicit human invocation and
[fuzz/SKILL.md](../fuzz/SKILL.md); CI runs fixed regressions only. Never execute
untrusted PR code on personal runners.
