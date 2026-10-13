# Host-agent and persistence handoff — 2026-10-12

Baseline `17d6668e08ab10be6bdf6d31573520d4e1268180`, clean `main`.
All changed A–D scenarios were authored and frozen before production edits.
Offline Docker `investobot-foundation-final`, mounted source, disposable SQLite:
**30 failed, 28 passed** in 12.75 seconds. Raw evidence is ignored at
`benchmark-results/host-agent-2026-10-12/baseline-red.log` (retain 90 days;
unresolved failures until resolved).

Intended red: missing shell bridge (4), bare skill commands/host ownership (13),
named volume/runtime prompts and private ignores (4), retired prompt CLI/discovery
and supported bond guidance (6), hidden persisted fund issues (2), full backtest
list payloads (1). Existing green: skill installation and overwrite protection,
real SQLite backup/restore with saved plan and referenced artifact, failed-restore
preservation, read-only viewer/POST/provider/missing-ledger controls. These passes
confirm existing behavior; they were not weakened to manufacture failures.

The referenced `code_review(8).md` and `code_smell_review(9).md` were not attached.
Review follows the PRD's intent → architecture → implementation → polish and
specified smell categories; supplying those files remains a review limitation.

## Existing operator volume

Read-only inventory found `investobot_ledger/portfolio.db` (86,016 bytes), no
prompt override files. Current verification and explicit-path online backup return
`UNSUPPORTED_DEVELOPMENT_SCHEMA`; no verified archive was published. The initial
backup invocation lacked INVEST_DB and reported a missing default path; the
explicit-path retry establishes the schema blocker. Original volume and running
service are preserved. Actual handoff is stopped: do not start the new default
bind or initialize an empty replacement without an operator decision about the
unsupported legacy ledger. No reset, raw SQLite copy, volume deletion or private
financial test was performed. Synthetic valid-schema migration acceptance is
separate from this operator-state blocker.

## Prompt audit and green implementation

Nine defaults were checked against thirteen existing skills. Concentration,
fund comparison, stock research, recent developments, target generation and
harvesting duplicate portfolio/research/screening/strategy workflows. Bond
terms/call provisions and unsupported complex instruments were retained in
investment screening; alternative comparison metrics/context were retained in
portfolio strategy. The old separate ST/LT rebalance budgets conflict with the
current annual positive tax-cost policy and were not carried forward. No new
skills or instruction registry were added. PromptLibrary, nine defaults, four
prompt CLI commands/descriptors, prompt documentation and obsolete CRUD tests
were removed. Existing installed-skill overwrite/path protections remain.

A–D green checkpoint `33b3822`: **91 passed**, focused Docker suite including
all changed scenarios and retained installation/financial safeguards; Ruff passes.
Fresh image `29ecc4d6abeb` (native ARM64), no private mount/network:
**1,363 passed in 49.37 seconds** with `uv run --locked pytest -q`.
The existing demo completed **34 actual CLI steps**; recovery and corpus retrieval
pass, with accepted/restored financial fingerprint
`35797d61e6c31bc3ca1638399ae1917dc45fb197ad76ac2add0fcb859109e25b`.
Raw package/full-suite/build/demo logs remain in the ignored evidence directory.
Final host lifecycle, paired performance and documentation verification follow.

## Integrated acceptance and review

Final exact runtime/config/test/skill tree `0ab2714`, image `493e7cdb501f`
(native ARM64): **1,363 passed in 50.57 seconds**, locked offline Docker; Ruff
passes and viewer JavaScript syntax passes in Node Docker. Byte verification
matched **322 committed runtime/config/test/skill files**. Later handoff/lock/copy
safety documentation changes do not change that runtime. Wheel build/install in
a disposable Docker directory verified all **13 skills** and no retired prompt
module/defaults. No host dependencies were installed.

Real Compose acceptance used an isolated synthetic checkout and loopback port,
not operator storage. Actual bridge discovery/describe/stdin/JSON/error exit,
both host-visible skill installs, edited-resource protection and the README
preview → authorization → acceptance flow pass. Absent GET leaves the ledger
absent; present GET and rejected POST preserve bytes. Accepted inventory,
logical fingerprint, saved plan and referenced artifact survive CLI removal,
Compose down/up and a fresh image rebuild. README backup/verify/restore passes.
Host files are owned/readable by the invoking macOS user; private directories are
0700 and archives 0600. Ordinary `git add .` excludes private data/generated
Investobot bundles while allowing unrelated operator skills. Rebuilt image
inspection excludes private sentinels and generated bundles; unrelated skills
are intentionally outside the narrow ignore rules. Reports are under
`host-compose/` plus `host-compose-rebuild*.log` and `host-image-exclusions.log`.
Initial smoke-harness assumptions (wrong route, optional diagnostic code, absent
GET status and unrelated-skill build exclusion) were corrected; original outputs
remain evidence. They required no application changes.

A separate **actual disposable named volume → host bind** archive transfer passes
with matching complete logical inventory/fingerprint, saved plan and artifact
bytes; source SQLite bytes remain unchanged, and an invalid archive preserves
the accepted destination. Reports are `storage-*.json`. The initial read-only
source-directory mount blocked required shared-lock access; that failure is
retained as `storage-first-attempt-failure.txt`. Repeating with lock access and
verifying source bytes established the successful result. Disposable storage
resources were cleaned; the host Compose service is stopped, with fictional
archive/work files retained for evidence. None accessed operator storage.

Exactly **eight paired representative workflows PASS** against pinned
`d0940a12c44831095492efcd7091fb7b937ad6b3`. Candidate runtime `33b3822` and image
`29ecc4d6abeb` were source/lock byte-verified, as was reference image
`447ff8d5596a`. Same native ARM64 engine, 2 CPUs/4 GiB, network none, one warm-up,
five shared-batch samples; minimum raw sample **378.072 ms**, zero short/invalid
samples. Maximum median increase **9.92%**, so no complete confirmation pair was
required. Input/output hashes match with the existing explicitly reviewed calendar
projection; no reference, recipe or allowance was changed. Ratios: actual 1.01484,
tax 1.00317, contributions 1.02834, harvest 1.04825, look-through 1.09923,
backtest 0.99511, historical query 0.95873, corpus 1.04030.
Reports/source/image checks are in `performance/`. SHA-256 reference/candidate/
comparison reports:

```text
488c4b643842fb1a55d69ba1879dccaf14edf269f2e01fd67fb2e4a167e83c5b
99bcaf063413bba9744ebbd6d8c88e1e2c0a1eb18921e0a6b989caed106dd4ee
93537721d6d5cbdaad107aaddbc10b21e1b9cd9f19e1b494fc2ca0f38fe146f0
```

Review followed intent → architecture → implementation → polish, including an
independent read-only review of boundaries, bloat, coupling, stale docs and tests.
One documentation preservation defect was corrected: legacy-note copy instructions
now refuse existing destinations and symlinks. No speculative cleanup, extra
services/tables, compatibility aliases or domain mocks were introduced. Runtime
changes are the bridge/skill command contract, bind/ignore configuration, prompt
retirement and viewer evidence/list projection. Active README, architecture,
operations, workflows, skills/research references, inspection, testing, trading
policy and AGENTS were reconciled; original PRD is preserved verbatim. Historical
measurements remain unchanged with supersession pointers where needed.

All evidence is local, not remote CI. No Git remote operation or push occurred.
Synthetic software acceptance is complete; actual rollout is **not complete**:
the unsupported legacy operator ledger remains preserved, with handoff stopped
and no verified archive claimed. The two requested review guide files were not
supplied. Real brokerage HTML, FMP entitlements/responses, host-agent instruction
following and off-device encrypted backup remain human gates. No real/private
documents, trade, secret or provider call was used for acceptance. Stop here;
Phase 2 starts only after operator foundation acceptance.
