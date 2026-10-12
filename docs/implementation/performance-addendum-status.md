# Performance and fuzz addendum status

The original additive specification is preserved in
[`PRD-performance-ai-fuzz-2026-10-10.md`](../PRD-performance-ai-fuzz-2026-10-10.md).
It preserves the unified MVP and strengthens its performance policy.

## Evidence

- MVP reference: `7cbf2bed13a0447865403e986662119571217bc6`.
  Its 1,249 existing tests and lint passed again in offline Docker.
- Global red checkpoint: `f59b5f8`. All 226 missing addendum contracts failed
  intentionally; the existing no-AI-in-CI control passed. No collection errors.
- Performance foundation: all 1,443 MVP/performance tests pass in offline Docker
  (185.62 seconds), including all 114 named workloads and matched-slice tests.
  Exploratory-harness contracts are a separate pending phase; this is not release
  certification or a claim of native paired measurements.
- Additional red checkpoint: `4c7ab7f` recorded four missing scaling contracts
  and two dense-flow failures. Green fix `b2ac5c6` retains every conventional
  flow while resolving the uniquely bracketed root; 23 focused tests passed.

## Remaining acceptance

The checked-in reference metadata records pending human review and capture,
not invented measurements. Run the paired medium and extended suites on the
documented native x86-64 Docker runner, retain their reports, investigate any
offenders, and review the initial reference. The local ARM64 test profile is
diagnostic only. Remote CI and branch-protection results are unverified because
no changes have been pushed.

The fuzz contracts and fixed offline harness are implemented after the green
performance foundation. A real exploratory campaign must be explicitly human-invoked after
performance acceptance. Fixed harness tests do not establish live agent novelty.
No provider keys or brokerage credentials are needed for offline acceptance.

Reviewed real broker HTML, live FMP entitlement and research rights remain the
manual gates listed in the unified MVP status; this addendum does not bypass them.

## Subsequent implementation progress

- Automatic extended paired scaling now measures candidate-only matched 1x/4x
  slices and applies the shared scaling gate, preserving native observations.
- The historical-metrics boundary now calculates one adjusted series instead of
  duplicating whole-fund comparison. Six focused scaling/boundary tests pass.
- The offline fuzz driver, strict schema, retained novelty history, independent
  oracles, local reports, replay, minimization and triage are implemented.
  All 40 fixed harness contracts pass in Docker (25.31 seconds); repository lint
  passes. No AI campaign was launched.
- Final combined verification follows this checkpoint. This remains development
  evidence, not native release certification.

Remaining engineering review: deterministic benchmark fixtures are currently
rebuilt outside the measured interval in each fresh worker, rather than prepared
once as reusable templates. Confirm preparation cost and complete template reuse
before asserting the PRD's fixture-reuse and total-job acceptance requirements.
Review actual scaling drivers against timed work (especially bounded provider and
specialty inputs), then retain native paired/extended reports. The current fuzz
operation adapters cover the fixed campaign; additional adapters are needed for
full P01–P15 exploratory workflow coverage. Five fresh human-invoked campaigns,
coverage/novelty review, native budgets and baseline approval remain unverified.
