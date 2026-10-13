# Local read-only dashboard

Start with `docker compose up -d` and open `http://localhost:8765`.
Only host-loopback publication is supported. This single-user local viewer has
no authentication; do not expose it to a network. Missing ledgers are inspected
through disposable in-memory data and are never created by viewing.

The dashboard shows accepted holdings/cash, known value, freshness/coverage,
actual performance, tax-lot warnings, active/saved targets and drift, immutable
plans with downloadable reports, and saved historical backtests. Unknown values
remain unknown. Hypothetical reports do not establish real account performance,
wash-sale safety or live provider readiness.

All application reads are query-only. Exposure uses compatible persisted holdings
observations; missing/stale evidence remains visibly unknown or requires review.
No GET refreshes a provider or writes a cache. Saved backtest comparisons use
`invest.backtest.compare` over stored results; different assumptions remain
`INCOMPARABLE` with explanations. No viewing operation runs a new simulation.

## GET routes

- `/api/overview`, `/api/summary`, `/api/state`: accepted account facts.
- `/api/check?as_of=YYYY-MM-DD`: accepted coverage review.
- `/api/performance?from=YYYY-MM-DD&to=YYYY-MM-DD`: dated actual performance.
- `/api/targets`, `/api/targets/ID`, `/api/targets/ID/diff`: saved target evidence
  and deterministic accepted-state drift; optional `version=N` selects a version.
- `/api/plans`, `/api/plans/ID`: saved immutable plans and current staleness.
- `/api/plans/ID/report?format=markdown|json`: download stored plan evidence.
- `/api/backtests`, `/api/backtests/ID`: stored historical runs.
- `/api/backtests/compare?run_id=ID&run_id=OTHER_ID`: compare saved runs.
- `/api/search?query=TEXT`: local permitted corpus search, without remote providers.

Local Host validation and safe response headers remain. Every POST, including
unknown routes and malformed bodies, returns HTTP 405 with a small JSON error
before reading application data. The dashboard has no import, activity, policy,
target-edit, prompt-edit, plan-generation or analysis-execution interface.

Agents use discovered CLI contracts for new calculations and human-authorized
writes. See [workflows](workflows.md) and [trading policy](trading-policy.md).
Phase 1 is synthetic foundation acceptance. Reviewed original Vanguard, Fidelity
NetBenefits and PNC HTML and live FMP validation belong to separate Phase 2 work.

Fund coverage reports numeric completeness separately from verified evidence
completeness. Persisted typed source issues remain visible even at 100% numeric
weight; known dollars and unknown residuals are preserved. `/api/backtests` returns
only IDs, dates, status, creation date and headline metrics. Full immutable
histories/manifests/curves remain at `/api/backtests/ID`; stored comparison retains
assumption mismatch outcomes. Host persistence is described in [operations](operations.md).
