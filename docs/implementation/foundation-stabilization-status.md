# Foundation stabilization — 2026-10-12

Active specification: [foundation PRD](../PRD-mvp-foundation-stabilization-2026-10-12.md).
Phase 1 is synthetic foundation work; Phase 2 original brokerage/provider validation
has not begun. Historical wrap-up acceptance remains a prior checkpoint.

## Baseline before implementation

On `main`, unchanged production baseline `6af9cc6f7942c3c6554a11eed92637b6f4cdb40c`; all A–F changed scenarios
were authored before production edits. Offline Docker `investobot-review-final`,
mounted source, `INVEST_PROMPTS=/data/prompts`, no private ledger or network:

- Focused foundation/dashboard/policy/decision suite: **46 failed, 96 passed**.
- Additional live-policy schema scenario: **1 failed** (retired calendar fields).
- Expected failures: POST mutation routes and retired UI; missing saved-backtest
  reads; provider call on overview cache miss; calendar/month gates; basisless
  retirement accounting and intake; untyped impossible/taxable sales; CLI parser
  environment mismatch and omitted environment; ignored blocking parser issues;
  false look-through completeness or discarded known values; weekday holiday
  inference and missing unverified-calendar disclosure.
- Green controls preserve contributions-only, explicit invalid environment,
  sourced nested exposure/residual/mismatch, pinned-calendar backtest gaps,
  invalid/duplicate/nonpositive history, approved policy identity, tax/TLH guards,
  accepted balance/plan reads and GET error handling.

The first draft used stored snapshot metadata as an intake payload in two tests;
this was corrected to the public Snapshot fields before the recorded run.
Raw logs: ignored `benchmark-results/foundation-2026-10-12/`; retain 90 days,
and unresolved failure evidence until resolution. No generated logs are tracked.
The referenced review guides were not supplied; review uses the PRD's explicit
intent → architecture → implementation → polish order and smell criteria.

Implementation and integrated acceptance are pending.
