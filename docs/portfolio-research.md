# Portfolio research

Portfolio research creates a frozen research queue and summarizes individually
accepted specialist evidence. It does not browse, forecast prices, recommend
trades or infer political beliefs. External agents obtain permitted evidence;
humans review original sources and permissions before explicit import.

## Frozen inputs and queue

`freeze_universe` adapts a sourced look-through universe into ordered issuers.
Each exposure weight uses the whole household value in one verified currency.
Partial holdings are not normalized to 100%. Identity fields, contribution paths,
source manifest IDs, unknown/filtered exposure and existing issues survive the
adapter. Missing environment, nonpositive denominator or duplicate issuer
identity blocks freezing. Freezing alone changes no accepted financial facts.

Save the frozen universe as a `RESEARCH_UNIVERSE` data snapshot, with its flat
contents under `metadata.universe`. `plan(ledger, universe_manifest_id)` verifies
that accepted manifest and pins the issuer order, cutoff, research window and
bundled skill versions. Its queue includes news, political contributions,
earnings, competitive and management/insider tasks for each issuer. All tasks
start `NOT_RESEARCHED`. The default window is the 30 days ending at the frozen
cutoff; callers may provide explicit bounded dates. Repeated identical planning
returns the same ID and does not insert another plan.

Plans use immutable SQLite snapshot metadata. They do not alter holdings, cash,
marks, financial fingerprints or market caches. The common research envelope
also preserves the existing exact-class fund diligence family; fund research is
not automatically treated as an operating issuer task.

## Reports and coverage

`report(ledger, plan_id)` reads accepted runs against the frozen queue. It never
imports evidence or refreshes data. Explicit envelope issuer references or
sourced compatible specialist identities establish linkage. A ticker alone is
insufficient. Runs with future source dates, incompatible environment or a skill
version different from the frozen plan are excluded with typed diagnostics.

Coverage distinguishes requested and researched issuer counts, selected and
researched whole-household weights, and unresolved source exposure. Researching
12 of 20 selected issuers is partial coverage even if every returned source is
valid. Completing the selected queue does not establish whole-portfolio coverage.
Legacy specialist evidence without accepted environment provenance remains
queryable and may establish descriptive research coverage, but is explicitly
`REVIEW_REQUIRED`; its missing environment is never invented.

Reports include every required skill under each company's `specialty_statuses`
and report researched counts/weights separately under `coverage.specialties`.
One complete news run cannot complete the other four tasks. Selected and whole
portfolio completeness require all pinned specialties to be available for every
selected issuer. Missing tasks remain `NOT_RESEARCHED`.
An incomplete requested task set returns the typed `RESEARCH_TASKS_INCOMPLETE`
issue with the affected issuer and skill names; callers need not interpret prose
to distinguish complete research from missing or partial evidence.

Interval specialties must cover the requested window to be complete. Overlapping
partial windows count as researched with partial coverage; evidence entirely
outside the window counts only as historical context and cannot increase current
researched counts or weights. Historical news retains its source/date with an
explicit `NOT_REOBSERVED` observation marker and window diagnostic. Point-in-time
specialties keep their actual reporting-period definitions; their research date
must fall inside the requested window rather than inventing interval evidence.

Each company retains accepted run hashes, source citations and specialty
summaries. Issuer order follows the frozen exposure selection, not an investment
ranking. News observations share stable issuer/event identity: syndicated stories
retain their separate citations under one development. Occurrence and publication
dates remain distinct. Disputed claims stay disputed. Older active observations
omitted from a later run are `NOT_REOBSERVED`, with their prior run/date and source
provenance retained. Cited terminal observations prevent older active records
from being revived; omission alone never establishes resolution.

Reports select compact issuer and skill metadata before loading accepted
packages. Unrelated accepted research is not read or validated by a selected
issuer report. At most 1000 matching runs per issuer are inspected; a larger
history returns a truncation diagnostic and review status rather than claiming
complete historical context. Full selected specialty summaries still retain their
source links; this bound is a read limit, not a claim that every report payload
has a fixed byte size.

Executive personal, employee personal and corporate PAC contribution categories
remain separate. Unverified contributor permission/identity or issuer-PAC linkage
excludes the contribution and increases excluded coverage. Human confirmation
does not override permissions. Existing political imports supply independently
validated executive evidence; they do not invent a corporate PAC relationship or
employee category that their specialist schema does not support. No stance score
or issuer corporate-policy conclusion is calculated.

`summarize` is a pure projection helper for already validated domain evidence,
not an agent-package acceptance API. Use the strict shared envelope and specialist
validators for imports. Its reviewed-permission/linkage fields describe prior
validation; structural checks cannot establish real-world truth or legal rights.

## Manual setup and limits

Synthetic demonstrations use fictional issuers and sources, require no secrets
and cannot authorize REAL portfolio actions. Before real operation, establish
reviewed issuer mappings and original-source permission, and supply explicit
REAL provenance. Named political contributor evidence requires the independent
local rights-policy review described in [research-envelope.md](research-envelope.md).
Missing mappings or rights remain blocked/unknown coverage. Institution HTML
adapters and live FMP entitlement require their separate human validation gates.
