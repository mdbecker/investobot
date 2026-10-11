# Shared research acceptance

The shared envelope routes an explicitly reviewed research package through its
existing specialist validator. It adds provenance without replacing specialty
schemas or changing their trusted skill identities and canonical run hashes.
Supported kinds are `NEWS`, `POLITICAL`, `EARNINGS`, `COMPETITIVE`, `INSIDERS` and
`FUND_DILIGENCE`. The last preserves exact-class fund diligence behavior.

An envelope has exactly six fields: `kind`, `issuer_id`, `as_of`,
`data_environment`, `skill_name` and `package`. `as_of` is an ISO calendar date
and must equal the package's researched-as-of date. Environment is `REAL` or
`SYNTHETIC`. The skill name must match the bundled specialist; agents cannot
choose their own trusted skill/schema versions. The package retains its strict
specialist schema, source references and limitations. Unknown extra envelope
fields are rejected.

`issuer_id` is a research-universe reference. Preserving it does not verify a
real-world issuer relationship or register a security. Specialist canonical
security references still undergo the existing identity checks. Portfolio
coordination must establish sourced identity links before treating an opaque
reference as portfolio coverage.

## Preview and explicit acceptance

`import_run(ledger, envelope, confirmed=False)` previews without writes.
`import_batch(ledger, envelopes, confirmed=True)` validates all packages and
accepts the batch in one SQLite transaction. Existing specialist inserts, shared
run projections and envelope artifacts either all succeed or all roll back.
An identical repeat is a no-op. Changed issuer/environment/date provenance
cannot overwrite an accepted run's envelope. Research acceptance does not alter
holdings, marks, cash, confirmed financial activity or financial fingerprints.

The original reviewed package is retained in the immutable envelope artifact;
specialist tables retain their established canonical representation. Artifact
hashes cover the stored metadata bytes. `show` verifies that hash before returning
the original package and trusted identity. Existing specialty runs remain
queryable even if they predate envelopes; their missing envelope provenance stays
unknown. Political specialty storage is preserved, with a common run projection
added only during explicitly confirmed envelope acceptance.

`list_runs` returns bounded metadata projections, optionally filtered by kind or
issuer. It does not deserialize packages. `show` retrieves one full package.
These domain functions use an already-open ledger; read-only CLI callers must
open an existing ledger without creating the selected path.

## Source rights and human review

Validation establishes structure, not source truth or legal permission. Humans
must review original sources and permitted use. Named political contributor
evidence still requires an independently reviewed local rights policy, passed
through `policy_path` to the existing political validator. Confirmation cannot
override this requirement. Other specialties retain their existing source,
filing, locator and identity checks. The envelope adds no scraping, personal-data
collection, source-rights assertions or political scores.

Offline examples must use fictional evidence and SYNTHETIC provenance. Real
research must never be made actionable by mixing it with synthetic portfolio
inputs. Research revisions remain separate accepted runs; consumers retain
source chronology, disputed facts, missing coverage and existing news continuity
semantics when comparing them.
