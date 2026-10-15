# Investobot — post-refactor codebase review

**Review date:** October 14, 2026 (America/New_York)  
**Repository:** [mdbecker/investobot](https://github.com/mdbecker/investobot)  
**Reviewed head:** [`2ecf01cbb55211afcea13e7d00eff03efe7ffd4e`](https://github.com/mdbecker/investobot/commit/2ecf01cbb55211afcea13e7d00eff03efe7ffd4e) (`main`)  
**Review basis:** user-supplied `code_review(8).md`, `code_smell_review(9).md`, repository code, tests, active documentation, Git history and GitHub Actions.  
**Confidence:** source-level review and CI/recorded evidence; **not a new local execution or live-data certification**. The linked GitHub connector provided source files and history. I did not run the project test suite or load real brokerage records in this review.

## Executive decision

**The current architecture is substantially aligned with the intended product, and another sweeping refactor would be counterproductive.** The external AI agent runs on the **host**, reads the tracked/installed agent skills there, and calls `./scripts/invest`; Docker owns the deterministic Python CLI and the GET-only local viewer. SQLite and private files remain host-backed. The formerly duplicative planner/exposure and prompt-service arrangements have largely been retired. These changes are material improvements, not just formatting.

**Do not yet regard real-money trade proposals as verified.** Three policy/evidence-contract issues deserve a tightly scoped corrective pass *before relying on real proposals*: an omitted `cash_known` flag can be inferred as true merely because a cash amount was supplied; some target constraints are accepted and documented but never consulted by the planner; and the annual tax-budget evidence is not checked for the proposal's year and evidence cutoff. An additional buy/hold permission inconsistency belongs in the same pass. These are code-path findings, not claims that an end-to-end exploit has been dynamically reproduced.

Keep this as a **single bounded corrective pass**, not a new multi-phase PRD. Fix the contracts, write observable BDD regressions first, run the focused tests and one final complete locked Docker suite, update only affected docs/skill wording, then stop. The real-broker/provider readiness gate stays separate.

### Snapshot of observed status

| Area | Assessment |
|---|---|
| Host agent ↔ deterministic Docker CLI | **Aligned.** `scripts/invest` is a shell bridge to `docker compose run --rm -T app invest`; agent skills are host-readable; no AI model runs in Docker. |
| Human dashboard | **Aligned.** A thin loopback-published viewer, GET/query-only API, POST 405, no brokerage execution. |
| Immutable/approval model | **Strong synthetic design.** Snapshots, approvals, recorded activities, explicit lots, plans, recovery and typed issues have substantial tests. |
| Financial calculations | **Plausible and heavily regression-covered**, including Decimal precision, provenance, sale-fee residues, incomplete evidence and source paths. Important contract gaps below remain. |
| Skills | **Good division of labor.** Thirteen host-oriented bundles; research and interpretation outside, deterministic computation inside; minor copied-path documentation issue. |
| CI at head | GitHub **Docker checks: succeeded** at the reviewed head. At review time, the latest fixed-performance workflow was **in progress**; prior fixed-performance CI failed, consistent with the documented exception. |
| Documented local acceptance | `docs/implementation/correctness-status.md` reports **1,390 passing pytest tests**, passing Ruff and focused/host-bridge/backup/viewer checks against the latest product changes. These are *recorded project results*, not new tests run by this reviewer. |
| Look-through performance | **PERFORMANCE EXCEPTION — NOT PASSED.** Recorded confirmation pair: reference **4.404951 ms**, candidate **6.268134 ms**, **+42.30%**. Extra source/provenance output means not identical reporting work. Do **not** optimize or recalibrate for this review. |
| Real-source readiness | Vanguard HTML, Fidelity NetBenefits 401(k) HTML, PNC HTML and entitled FMP responses: **NOT TESTED / UNVERIFIED**; current HTML profiles are provisional. Synthetic tests cannot upgrade this status. |

## Review method and history check

I followed the requested order: **intent → architecture → implementation → polish**, tracing sync/reconcile/apply, permissions/target → plans, tax lots/annual allowance → rebalance/harvest, performance and fund look-through, and the agent → Docker/viewer boundaries. I treated the five code-smell families (Bloaters, Object-Orientation Abusers, Change Preventers, Dispensables and Couplers) as risk indicators, **not automatic refactoring orders**. The review uses the supplied guide's priorities and feedback types, with exact code references and one recommended fix for each finding.

Recent history matters:

- [`33b3822`](https://github.com/mdbecker/investobot/commit/33b38227a907606c9a915b6ee630b7db6050e3d7) / [`4fdc877`](https://github.com/mdbecker/investobot/commit/4fdc8776f564d9ef96ed461d2e11817edd514f18): host-Docker bridge/persistence, retirement of agent-inside-Docker assumptions and protection of host agent config in builds.
- [`de173e0`](https://github.com/mdbecker/investobot/commit/de173e0db35fd6e3f7abc3549a72bac9362c9a15): consolidated exposure, sale estimates and policy-governed planning.
- [`dc894c8`](https://github.com/mdbecker/investobot/commit/dc894c8c6ce72db25c44e12da4034c6874b61e0f), [`a6d3efa`](https://github.com/mdbecker/investobot/commit/a6d3efa2aae48c6a1aa592e33d357e89766178f9), [`04246f0`](https://github.com/mdbecker/investobot/commit/04246f0be9f55f444dedb23001c53874a5bc58e8): bounded source-gate, exact-amount, repeated/partial-import and observed-price fixes, with preceding test-only red commits.
- [`2ecf01c`](https://github.com/mdbecker/investobot/commit/2ecf01cbb55211afcea13e7d00eff03efe7ffd4e): current documentation/testing handoff.

The October 14 completion addendum explicitly accepts the performance exception and halts broad refactoring. This fresh user-requested review is a reason to investigate concrete new issues, **not** a reason to restart the old scope or add a framework.

---

## Findings: material contracts

### 1. Missing `cash_known` can silently become an attestation

**Priority: Should fix now · Type: TODO · Category: correctness / Primitive Obsession / implicit state**  
**Code:** [`src/invest/models.py:80-116`](https://github.com/mdbecker/investobot/blob/2ecf01cbb55211afcea13e7d00eff03efe7ffd4e/src/invest/models.py#L80-L116), [`src/invest/ledger.py:545-564`](https://github.com/mdbecker/investobot/blob/2ecf01cbb55211afcea13e7d00eff03efe7ffd4e/src/invest/ledger.py#L545-L564).

`Snapshot` declares `cash_known: StrictBool = False`, but its **before** validator `explicit_cash` changes that to `True` when JSON contains a `cash` field and omits `cash_known`. A value of `"cash":"0"` therefore counts as independently confirmed cash coverage even when the source/caller has not attested this. In `Ledger.apply`, `cash_known` is the signal that allows replacing accepted cash with the supplied value. The docs and the product explicitly distinguish *a numeric cell* from *complete cash evidence*. The generic HTML parser deliberately emits its own `cash_known` boolean, so the bug is mainly in **manual/agent-generated snapshots and interchange**, not a claim that the existing HTML parser forgets its flag.

**Best fix:** delete the `explicit_cash` validator. Retain the declared default `False` and require the caller to supply an affirmative `cash_known:true` only with evidence of the actual account balance. Do not infer completeness from the presence of any number, including zero. Update the synthetic fixtures that previously relied on this shortcut; **do not add a compatibility mode**.

**Red-first BDD:** a previously accepted account has `$500` known cash; a later partial snapshot includes `cash:"0"` but omits `cash_known`. Acceptance must preserve `$500`, report unknown new cash coverage, and must not allow a plan to treat the unverified zero as a fresh balance. Separately, `cash_known:true` with independently reviewed zero should be accepted as zero. This is one rule and needs no new class or service.

**No-user consequence:** no migration is needed; only fixture/doc JSON that incorrectly omitted the attestation must be corrected now.

### 2. Stored target constraints can be ignored by an otherwise valid trade proposal

**Priority: Should fix now · Type: TODO · Category: correctness / Shotgun Surgery / misleading public contract**  
**Code:** [`src/invest/models.py:134-142`](https://github.com/mdbecker/investobot/blob/2ecf01cbb55211afcea13e7d00eff03efe7ffd4e/src/invest/models.py#L134-L142), [`src/invest/targets.py:18-47`](https://github.com/mdbecker/investobot/blob/2ecf01cbb55211afcea13e7d00eff03efe7ffd4e/src/invest/targets.py#L18-L47), [`src/invest/planning.py:133-416`](https://github.com/mdbecker/investobot/blob/2ecf01cbb55211afcea13e7d00eff03efe7ffd4e/src/invest/planning.py#L133-L416), [`docs/targets.md`](https://github.com/mdbecker/investobot/blob/2ecf01cbb55211afcea13e7d00eff03efe7ffd4e/docs/targets.md).

`PlanningConstraints` accepts and `targets.save` persists/validates `permitted_securities`, `cash_minimums`, `trade_increments`, `price_max_age_days` and `target_tolerance`, but `_propose` only meaningfully reads `eligible_accounts` and `excluded_positions` from the target. Trade eligibility/increments/floors/freshness are controlled solely by the separate policy, without applying the overlapping target values. Consequently, an operator could save a target apparently disallowing purchases of one security or requiring a `$500` cash minimum; a separately approved policy allowing that trade or specifying a lower floor wins silently. This is misleading even if the planner's isolated policy logic is correct.

**Best fix:** preserve **one authority for executable constraints: the immutable approved trading policy**. Remove the *duplicate/inactive execution fields* from `PlanningConstraints` and its validation/active docs/tests: `permitted_securities`, `cash_minimums`, `trade_increments`, `price_max_age_days`. Define target as **weights plus eligible accounts and excluded positions**. Keep `target_tolerance` only if actually used to compute a presentation-level deviation/interpretation; if it has no caller, remove it too rather than suggesting it controls execution. An operator who wants security permission, a floor, precision or freshness must explicitly put it in the approved policy. Update the target documentation before real use. **Do not implement two interacting trade-constraint engines.**

**Red-first BDD:** express the supported contract explicitly: target weights do not confer trade permission; a policy missing or denying a security blocks that trade, policy floor remains inviolate, and a target cannot save legacy execution fields that will be ignored. If a same-named policy and target field is used in tests, the test must document that such a target field is invalid after cleanup.

**No-user consequence:** no legacy target compatibility is necessary, and eliminating these duplicative fields is safer and simpler than attempting precedence rules for several independent constraints.

### 3. `can_hold` is captured but not enforced when buying

**Priority: Should fix now · Type: TODO · Category: correctness / incomplete authorization contract**  
**Code:** [`src/invest/planning.py:29-52`](https://github.com/mdbecker/investobot/blob/2ecf01cbb55211afcea13e7d00eff03efe7ffd4e/src/invest/planning.py#L29-L52), [`src/invest/planning.py:264-298`](https://github.com/mdbecker/investobot/blob/2ecf01cbb55211afcea13e7d00eff03efe7ffd4e/src/invest/planning.py#L264-L298), [`docs/trading-policy.md`](https://github.com/mdbecker/investobot/blob/2ecf01cbb55211afcea13e7d00eff03efe7ffd4e/docs/trading-policy.md).

The docs describe independent strict `can_buy`, `can_sell`, **`can_hold`** permissions. `_validate` verifies their Python types **when present**, rather than requiring all three, and the planner's `add()` checks `can_buy` for BUY or `can_sell` for SELL but never checks `can_hold`. Thus a policy with `can_buy:true, can_hold:false` can generate a purchase that immediately creates a prohibited holding. `can_hold` has no demonstrated planner enforcement, giving the field ceremonial rather than protective value.

**Best fix:** make all three boolean fields required in each approved policy permission entry, and reject internally inconsistent **buy-allowed/hold-forbidden** rules during policy approval. Keep `can_hold` to make a holding restriction meaningful (the user explicitly requested independent hold eligibility); do **not** auto-liquidate an existing forbidden holding. Report existing restricted inventory for human review; buy generation must never increase it. This is a few validations and one behavioral test, not an authorization framework.

**Red-first BDD:** a reviewed policy forbids holding an instrument but otherwise describes an executable purchase. Policy approval rejects the contradictory rule; an existing restricted holding remains visible but no automatic forced sale occurs. A legitimate buy/hold permitted case still works. Ensure a missing field cannot silently represent a permission.

**No-user consequence:** any fictional fixtures with partial permissions can be made explicit; no backwards compatibility layer.

### 4. Annual tax headroom is not pinned to the proposed sale date and evidence cutoff

**Priority: Should fix now · Type: TODO · Category: financial correctness / temporal evidence invariant**  
**Code:** [`src/invest/planning.py:244-260`](https://github.com/mdbecker/investobot/blob/2ecf01cbb55211afcea13e7d00eff03efe7ffd4e/src/invest/planning.py#L244-L260), [`src/invest/tax_policy.py:97-206`](https://github.com/mdbecker/investobot/blob/2ecf01cbb55211afcea13e7d00eff03efe7ffd4e/src/invest/tax_policy.py#L97-L206), [`src/invest/harvest_proposals.py:39-77`](https://github.com/mdbecker/investobot/blob/2ecf01cbb55211afcea13e7d00eff03efe7ffd4e/src/invest/harvest_proposals.py#L39-L77).

`planning._propose` calls `annual_budget(baseline, policy['annual_tax_budget'])` and then consumes its reported `remaining_allowance`. `annual_budget` selects confirmed sales by `policy.year` and (when supplied) its `policy.as_of` date; **the planner does not check those against the requested sale `as_of`**. A 2027 trade could be screened against a 2026 allowance, or an October 15 proposal could ignore confirmed October 5 sales because the approved annual attestation's cutoff was October 1. `conditional_harvest` also accepts a nested annual budget without a visible year/cutoff alignment check, despite separately checking the harvest date. These are static control-flow observations; demonstrate the actual outcome with an isolated test rather than assuming a specific portfolio fixture.

**Best fix:** implement one small shared validation of an approved annual budget against the actual **planned trade date**, called by rebalance and conditional harvest before calculating sale actions. Require year == planned trade year; the attested history cutoff must cover all confirmed activity used by the proposed sale and must not postdate the proposal with unknowable future evidence; and confirm the policy's recorded data environment matches the portfolio. Where the approved attestation is stale or its source coverage is unknown, return a typed blocking issue for taxable sale generation, preserving cash-only proposals where independently safe. Use an updated explicitly approved budget/policy, not a silent date replacement.

**Red-first BDD:** (a) the policy is for 2026 but proposal date is in 2027; (b) a taxable sale is confirmed **after** the budget's evidence cutoff but **before** the requested planned sale. Both must block an authoritative taxable sale tax-headroom claim and retain known facts; a correctly attested matching-year example passes. Run these through **both** rebalance and conditional-harvest paths.

**No-user consequence:** there is no accepted historical policy that needs grandfathering; make the date requirement explicit now.

## Findings: polish, tests and readiness

### 5. The active target JSON example contains fields forbidden by its model

**Priority: Recommended now · Type: Nit · Category: documentation contract / Dead Code**  
**Code:** [`docs/targets.md`](https://github.com/mdbecker/investobot/blob/2ecf01cbb55211afcea13e7d00eff03efe7ffd4e/docs/targets.md), [`src/invest/models.py:134-142`](https://github.com/mdbecker/investobot/blob/2ecf01cbb55211afcea13e7d00eff03efe7ffd4e/src/invest/models.py#L134-L142).

The displayed target JSON includes `short_term_gain_budget` and `long_term_gain_budget` under `planning_constraints`. The model uses `extra='forbid'` and does not define either field. They were deliberately retired in recent policy simplification. A user following the live docs receives a validation failure.

**Best fix:** replace the example with JSON that is *actually accepted* under the simplified target contract; place tax allowances exclusively in the separately approved trading policy and link the single authoritative end-to-end flow in `docs/workflows.md`. Add a quick example/schema regression test if this example is used for onboarding. This is an immediately useful documentation fix; no migration.

### 6. Copied skill bundles contain checkout-relative docs links that change meaning when installed

**Priority: Recommended now · Type: Nit · Category: leaky path assumption**  
**Code:** [`skills/investobot-monthly-investing/SKILL.md`](https://github.com/mdbecker/investobot/blob/2ecf01cbb55211afcea13e7d00eff03efe7ffd4e/skills/investobot-monthly-investing/SKILL.md), [`skills/investobot-portfolio-strategy/SKILL.md`](https://github.com/mdbecker/investobot/blob/2ecf01cbb55211afcea13e7d00eff03efe7ffd4e/skills/investobot-portfolio-strategy/SKILL.md), [`src/invest/research_skills.py`](https://github.com/mdbecker/investobot/blob/2ecf01cbb55211afcea13e7d00eff03efe7ffd4e/src/invest/research_skills.py).

The skill files link to `[docs/workflows.md](../../docs/workflows.md)`. That resolves from the canonical `skills/<bundle>/SKILL.md`, but an installed copy at `.agents/skills/<bundle>/SKILL.md` or `.claude/skills/<bundle>/SKILL.md` resolves to `.agents/docs/workflows.md` / `.claude/docs/workflows.md`. The installer copies the text rather than rewriting relative links. The actual CLI invocation remains correct; this is a documentation lookup failure for the host agent.

**Best fix:** refer to the checkout-root relative **path as text** (`docs/workflows.md`, opened relative to the repository working directory), not an installed-SKILL-relative Markdown URL. Repeat for any other links crossing out of the skill bundle. Add a single copied-skill smoke assertion; no new installation layer and no migration.

### 7. Some synthetic BDD specifications still read like implementation case dispatch

**Priority: Recommended now · Type: TODO · Category: fragile / less informative tests**  
**Code:** [`tests/features/mvp/decisions.feature`](https://github.com/mdbecker/investobot/blob/2ecf01cbb55211afcea13e7d00eff03efe7ffd4e/tests/features/mvp/decisions.feature), [`tests/test_mvp_decisions_bdd.py`](https://github.com/mdbecker/investobot/blob/2ecf01cbb55211afcea13e7d00eff03efe7ffd4e/tests/test_mvp_decisions_bdd.py), [better example `tests/features/mvp/exposure_consistency.feature`](https://github.com/mdbecker/investobot/blob/2ecf01cbb55211afcea13e7d00eff03efe7ffd4e/tests/features/mvp/exposure_consistency.feature).

`decision B31 satisfies its financial acceptance contract` and `B39` etc. name a case ID rather than a business outcome; the corresponding Python test branches by case. A developer cannot tell the intended behavior from the feature text, which is the point of BDD living documentation. The newer exposure scenarios demonstrate a more useful form: `$600` attributed, `$400` unknown, one verified issuer across two paths, no denominator when cash is missing.

**Best fix:** **do not rewrite the whole test suite**. Make the *new regressions in findings 1–4* readable, concrete business scenarios with observed outputs and invariants. Only replace an existing opaque BDD case when directly touched by those fixes; leave untouched functioning tests alone. This balances the guide's BDD standard with the repo's prior over-refactoring history. No compatibility constraints.

### 8. Real broker/provider validation is an external acceptance gate, not a code refactor

**Priority: Must fix before first real-data reliance (not a blocker to synthetic MVP handoff) · Type: Follow-up · Category: readiness / missing real oracle**  
**Code:** [`src/invest/parsers/generic.py`](https://github.com/mdbecker/investobot/blob/2ecf01cbb55211afcea13e7d00eff03efe7ffd4e/src/invest/parsers/generic.py), [`src/invest/parsers/profiles.py`](https://github.com/mdbecker/investobot/blob/2ecf01cbb55211afcea13e7d00eff03efe7ffd4e/src/invest/parsers/profiles.py), [`docs/readiness.md`](https://github.com/mdbecker/investobot/blob/2ecf01cbb55211afcea13e7d00eff03efe7ffd4e/docs/readiness.md).

The generic parser processes recognized HTML table columns and the institution files supply provisional aliases, **not verified fixtures from your actual pages**. Consequently, correctness of holdings, cash, dated balances, missing rows, stable broker lot identity and adjusted basis on your real statements remains unestablished. The project appropriately labels this PROVISIONAL / NOT TESTED; this is a **hard precondition** to trusting live imports and actionable trade estimates, regardless of how many synthetic tests pass.

**Best fix:** after the bounded code-contract pass, manually provide **one permission-cleared and sanitized real example for one institution**, together with independently confirmed expected positions, cash, dates, source price precision, lots, adjusted basis and account identity; capture a golden red/green acceptance test through import → reconcile → approved apply → summary/return or typed blockers. Then repeat by institution, and separately validate entitled FMP exact-class holdings and source rights. Do not request brokerage passwords or cookies; do not invent adapters or extensive parsing frameworks without a failing actual example. This remains separate from synthetic MVP release and requires human source evidence, not code alone.

### 9. The CLI and planner have complexity hotspots, but not a justified rewrite trigger

**Priority: Can defer · Type: Follow-up · Category: Bloaters / maintainability**  
**Code:** [`src/invest/cli.py`](https://github.com/mdbecker/investobot/blob/2ecf01cbb55211afcea13e7d00eff03efe7ffd4e/src/invest/cli.py), [`src/invest/ledger.py:207-570`](https://github.com/mdbecker/investobot/blob/2ecf01cbb55211afcea13e7d00eff03efe7ffd4e/src/invest/ledger.py#L207-L570), [`src/invest/planning.py:133-416`](https://github.com/mdbecker/investobot/blob/2ecf01cbb55211afcea13e7d00eff03efe7ffd4e/src/invest/planning.py#L133-L416).

`cli.py` is ~1,297 lines, `Ledger.reconcile` ~219 lines and `_propose` ~284 lines. Some nested functions and mutable accumulators carry real change pressure. But the CLI's numerous Typer command handlers are mostly thin wrappers around domains, and history shows duplicate engines were recently removed. Raw line count is not evidence that a new command framework, service layer, or package taxonomy will make this easier to maintain. The most risk-sensitive coupling was *duplicated financial calculations*, now mostly unified.

**Best fix:** **do not split `cli.py` or `Ledger` as an independent work package**. During findings 1–4, only extract the small shared tax-date validation and make the few affected policy rules explicit. If a later real-source bug demonstrates that reconcile mixes independently changing responsibilities, extract that one validated operation then. Preserve one CLI, one exposure engine, one planner, and predictable Docker-only dependencies. No migration.

### 10. Multi-year tax-aware optimal transition planning is not present

**Priority: Can defer · Type: Follow-up · Category: product scope / transparent limits**  
**Code:** [`src/invest/planning.py:350-415`](https://github.com/mdbecker/investobot/blob/2ecf01cbb55211afcea13e7d00eff03efe7ffd4e/src/invest/planning.py#L350-L415), [`docs/trading-policy.md`](https://github.com/mdbecker/investobot/blob/2ecf01cbb55211afcea13e7d00eff03efe7ffd4e/docs/trading-policy.md).

The current planner is explicitly **greedy and contribution-first**. It supplies same-date conservative trades constrained by cash, lots, approved permissions and a year's positive tax allowance; it **does not solve** global optimality, multi-year budget allocation, tax-bracket interaction, or complex mixed-integer trade scheduling. It can leave drift if full planned sales exceed remaining allowance. That is a real gap versus the aspirational use case of an *optimal multi-year tax-minimizing transition*, but not a defect in a product clearly described as heuristic and manually reviewed.

**Best fix:** keep the honest scope label in outputs/docs ("constrained, non-optimal proposal") and include remaining target drift/blocked trade reasons. Defer an optimizer until real workflows establish the objective, tax assumptions, fees, timing and hard constraints. Do not build an abstract optimizer in response to code-smell findings. No migration.

---

## End-to-end use-case coverage

The following is a **capability and readiness assessment**, not a claim that a live source has passed tests:

| Requested workflow | Foundation now | What remains before trusting real results |
|---|---|---|
| 1. Import brokerage HTML, ledger, total return/CAGR | Host skill, HTML normalization, reconcile/apply, dated performance, typed gaps | Reviewed institution HTML; source cash/lot history; complete dated checkpoints/flows; missing evidence must remain unavailable |
| 2. Rebalance with tax budget and exact trades | Saved targets/policies, deterministic constrained plan, specific lots/fee/tax estimate | Findings 1–4; independently approved restrictions and taxable-history cutoff; live account saleability |
| 3. Harvest losses and propose replacement trades | Conditional harvest, 30-day household review, sourced replacement price, specific lots, no automatic execution | Findings 3–4; outside/IRA/spouse/DRIP and substantially-identical human review; live verified lots |
| 4. Find alternative TLH funds | Screening/diligence skills, fund comparisons, evidence gates | Licensed current exact-class holdings, sourced similarity and separate substantial-identity review |
| 5. Find funds matching goals | Screening and source-backed research skill | Human criteria, provider rights, source coverage; no invented score |
| 6. Full look-through of fund holdings | Single recursive exposure and issuer aggregation with known/unknown coverage | Licensed/pinned actual fund constituents, publication/vintage/identity validation; approved performance exception |
| 7. Political contributions for top companies | Verified issuer research universe and specialist political evidence contracts | Original FEC/public sources and legal reuse rights; no inferred political score or corporate/executive conflation |
| 8. News/event impact on portfolio companies | Frozen issuer universe + news, earnings, competitive, insiders research | Agent qualitative evaluation; verified events and coverage; no deterministic causal impact guarantee |
| 9. New targets, historical simulations, transition under tax budget | Target versioning, historical backtests, saved plan compare and greedy transition | Comparable return series/pinned assumptions; no global multi-year optimizer yet; constrained-result labeling |

The discretionary **one trading session/month and up to four rebalances/year** should remain an **agent recommendation**, not an executable calendar ban. The existing skills correctly express the preference while allowing a human-requested necessary exception and avoiding auto-orders.

## Recommended execution plan — finite, test-first

1. **Write focused failing public-behavior scenarios** for the four material contract findings: missing cash attestation, ignored/duplicate target restrictions, conflicting buy/hold permissions, wrong tax year or stale attestation in rebalance/harvest. Confirm red for the intended reason; do not manufacture unrelated reds.
2. **Change only the actual contracts:** delete the implicit cash validator; make immutable policy the one execution constraint authority; require/validate the three permissions; align the annual budget and proposed trade date in one shared helper.
3. **Repair only touched supporting material:** invalid target example, affected skill paths, and fictional fixtures that used inferred coverage/partial permission. Leave historical PRDs, old case matrices, unrelated domain code and performance machinery alone.
4. **Run focused green tests and one final locked Docker full test + Ruff pass**. Keep synthetic CLI/host-skill/dashboard/backup checks valid; rerun only those whose dependencies changed. Inspect current CI and preserve its real reported conclusion; do not disguise the fixed-performance failure.
5. **Stop after verified handoff.** Next human task: supply one sanitized, independently reviewed broker page (one institution at a time). Add real-source golden tests before importing actual financial facts or relying on exact trades.

### Acceptance conditions

- Explicit `cash_known` cannot be inferred from a numeric balance, and partial observations cannot overwrite independent accepted cash without attestation.
- A saved target contains **no misleading executable restrictions**. All permissions, floor, increment, fee, and freshness rules used by trades have **one source of truth** in the approved policy. No permitted trade increases a `can_hold:false` restricted position.
- Taxable proposed sales use an explicitly matching tax year and sufficiently current household tax-history evidence. Missing evidence produces a blocking typed issue rather than a false remaining allowance; cash-only suggestions remain independently evaluated.
- No accidental accepted-portfolio mutations from previews, research, backtests or dashboard GETs. Recorded confirmed activity is idempotent and retained by immutable IDs.
- Actual current onboarding JSON is accepted by its schema; installed host skills have valid workspace guidance. New BDD scenarios show concrete business outcomes.
- Docker CI/lint and targeted regression suite pass after changes; performance remains candidly **NOT PASSED** under the approved exception; real brokerage/FMP status remains **NOT TESTED / UNVERIFIED** until original-source golden tests.

## Bottom line

**This is no longer a repository that obviously needs another general refactor.** The high-level separation you asked for is in place, major duplicate engines were removed, and the synthetic acceptance evidence is meaningful. The remaining worthwhile immediate work is narrower but important: **make every accepted fact and every policy field mean exactly what the agent/operator will think it means, especially for cash coverage, security eligibility and annual tax dollars.** Once those specific issues are verified, move to one real-world broker sample rather than launching yet another broad code-smell campaign.

**Review limitations:** Static findings are grounded in inspected head source and active documentation. GitHub CI success and in-repo local test counts were checked as reported, but this review did not run a fresh checkout or tests locally. A targeted reproducer may reveal a mitigating caller check not evident in the traced path; a falsified finding should be dropped rather than fixed ritualistically. No commits or code changes were made in this review.
