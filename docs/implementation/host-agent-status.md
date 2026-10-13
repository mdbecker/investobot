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
