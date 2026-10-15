# October 14 contract review handoff

Scope: the owner's requested [post-refactor review](../investobot-code-review-2026-10-14.md),
implemented on `main` in one bounded corrective pass. The attached review is
preserved as historical evidence, including its original CI and readiness claims.
Its referenced `code_review(8).md` and `code_smell_review(9).md` were unavailable;
no new review against those guides or remote CI certification is claimed.

## Implemented contracts

- Numeric cash, including zero, no longer implies `cash_known:true`. An unattested
  partial observation preserves independently accepted cash and its source date.
- Targets retain weights, eligible accounts, excluded positions and a used
  presentation tolerance. Four inactive execution fields and their reference
  checks were deleted; approved policies remain the sole execution authority.
- Every permission entry requires three explicit JSON booleans. Buy permission
  requires hold permission. Existing restricted holdings remain visible for review,
  without forced liquidation or additional purchases.
- Rebalance and conditional harvest share annual tax evidence validation against
  the planned date: matching year/environment, no future attestation, and no
  confirmed pre-trade taxable sale after the attested cutoff. Invalid evidence
  makes remaining headroom unavailable and blocks taxable sales. Independently
  safe cash-funded purchases remain possible; approved evidence is never rewritten.
- Onboarding target JSON now validates. Copied host skills name repository-root
  documents without broken links outside their bundles. Fictional inputs explicitly
  attest cash where their scenarios require known balances.

The shared benchmark fixture drops only the rejected target field so existing
fixed regression tests can construct it. No performance gate, threshold, reference,
calibration, timing operation or stored measurement was changed or rerun.

## Verification and commits

Test-only checkpoint `e173caa` precedes production edits. The initial combined
Docker run observed 21 failures and 8 passes, reproducing the material gaps and
broken examples/skill links. One unnecessary assertion demanding an issue for an
explicitly denied purchase was removed; denial requires no purchase, not new prose.
Green implementation `d903ea2`: 39 focused tests passed. Supporting fixture/docs
checkpoint `cba6d35`: 58 focused acceptance checks passed, including public CLI demo,
conditional harvest, copied skills, online recovery and GET-only viewer checks.

An intermediate full run found obsolete synthetic inputs (27 failed, 1,380 passed,
12 setup errors); these were corrected without changing expected financial results.
The shared-fixture rerun passed 62 checks, with only the then-unupdated household
JSON fixture failing cash coverage. That fixture now explicitly attests its cash.
The final locked full Docker and configured Ruff results are recorded below.

- Final committed runtime/test tree `cba6d355b2f51f1e5bab6e4b4a28800f935cd391`:
  **1,419 passed in 47.95 seconds**, exit 0 (`uv run --locked pytest -q`).
- Ruff: **All checks passed**, exit 0 (`uv run --locked ruff check --config
  pyproject.toml src tests benchmarks scripts fuzz`).
- Only this handoff and links to it follow that verified tree; no production,
  fixture, skill, dependency or test changes invalidate these checks.

All execution used the existing native ARM64 `investobot-correctness-final` image
(`5bd5834db098`) with the committed checkout bound at `/app`, `UV_OFFLINE=1`, no
network and no private ledger mounts. Dependencies stayed in `/opt/venv`.
This verifies current bound source, not an image containing newly baked source.
No host packages were installed and no remote/fetch/push was used.

The full suite includes host shell boundary, both host skill formats, backup/restore,
viewer nonmutation/POST 405 and the disposable public CLI demonstration. Prior real
Compose persistence/loopback walkthrough and wheel/privacy evidence in
[the earlier handoff](correctness-status.md) remain applicable to unchanged bridge,
Compose, storage and packaging behavior; copied skill guidance is newly checked.
These are local results, not remote CI evidence. Raw final test output is retained
outside Git at `/tmp/investobot-review-final-pytest.log`.

## Remaining gates and stopping rule

No outstanding material correctness defect is known from this finite pass. The
large CLI and greedy planner remain deliberate maintenance limits; proposals are
constrained and non-optimal, with remaining drift and review issues. No optimizer,
parser framework, migration, provider client or compatibility layer was added.

**PERFORMANCE EXCEPTION — NOT PASSED; not rerun.** The recorded confirmation
look-through workflow measured reference **4.404951 ms**, candidate **6.268134 ms**,
**+42.30%**. It covers recursive exposure and top-issuer selection for four accounts,
200 positions, 400 lots, four funds with 12 constituents and three nested levels.
The candidate additionally reports provenance/coverage, so reporting work differs.
The approved exception and original failure remain visible; no speedup is claimed.

Vanguard, Fidelity NetBenefits and PNC remain **NOT TESTED / PROVISIONAL**; live
FMP remains **NOT TESTED / UNVERIFIED**. The next human action is one permission-cleared,
sanitized broker page with independently checked positions, cash, dates, price
precision, account/security identity, lots and adjusted basis. Add a golden test
before relying on that source, then repeat by institution. Never supply passwords
or cookies. Entitled FMP responses and reuse rights require separate review.

Use the existing [Docker setup](../../README.md), [account/secret instructions](../data-sources.md),
[private storage/recovery](../operations.md), [readiness matrix](../readiness.md) and
[authoritative workflow](../workflows.md). This correction needs no new account,
secret or host installation. Stop after final verification and handoff; real-source
work, benchmarking, profiling and further audits require a new human request.
