# Host-agent and persistence handoff — 2026-10-12

Supported product: an independently supplied **host AI agent** reads host-accessible
skills and invokes deterministic Docker CLI commands through `./scripts/invest`.
Git-ignored `local-data/state:/data` holds authoritative SQLite, sidecars,
immutable artifacts, receipts and backups. The human dashboard is read-only.
Canonical `skills/` are tracked and packaged for installation; complete `.agents/`
and `.claude/` directories belong to the host agent and stay outside Docker images.
Git ignores only generated Investobot bundles, so unrelated skills can be tracked.

The owner confirms all prior application contents are disposable development
state and authorizes fresh host-backed storage. **No migration, compatibility
handoff or operator decision is required.** Existing application behavior initializes
fresh state; viewing an absent ledger never creates it. No data copy, schema change
or volume deletion is part of this cleanup. Ordinary backup/restore and financial
safety remain unchanged. Historical PRDs retain their original requirements;
this approval supersedes their setup/preservation requirements.

## Original implementation evidence

Baseline `17d6668`, clean `main`: all A–D changed scenarios were authored before
production edits. Docker baseline **30 failed, 28 passed**, committed `ca391e0`.
Intended failures covered missing bridge/host command ownership, storage/ignores,
retired prompt commands, bond guidance, hidden fund-source issues and full
backtest-list payloads. Existing skill-install, SQLite recovery and viewer safety
controls passed. Green implementation `33b3822`: **91 focused tests passed**.

Nine prompt defaults were audited against thirteen existing skills. Unique bond
terms/call provisions/complex-instrument limitations and alternative-comparison
metrics were folded into screening/strategy. Duplicate or obsolete guidance was
removed with PromptLibrary, nine defaults, four CLI commands/descriptors, prompt
docs and obsolete CRUD tests. No new skill registry, service or database schema.

Exact runtime/config/test/skill tree `0ab2714`, native ARM64 image `493e7cdb501f`:
**1,363 passed in 50.57 seconds**, offline locked Docker; Ruff and JavaScript syntax
passed. Byte verification matched **322 committed files**. Docker wheel installation
verified all **13 skills** and absence of the retired prompt package. The existing
**34-step actual CLI demo** verified financial recovery and corpus retrieval;
accepted/restored fingerprint:
`35797d61e6c31bc3ca1638399ae1917dc45fb197ad76ac2add0fcb859109e25b`.

Real Compose checks in an isolated fictional checkout passed bridge discovery,
stdin/JSON/error handling, both host skill installs, edited-resource protection,
README preview/authorization/acceptance, absent/present GET, POST 405, and database
byte preservation. Accepted inventory, fingerprint, saved plan and artifact survived
container removal, Compose down/up and image rebuild. Ordinary online backup,
preview, restore and invalid-archive failure safety passed. Host ownership was
readable by the invoking macOS user, with 0700 private directories/0600 archives.
Git excluded private data and generated bundles while allowing unrelated skills.

Exactly **eight representative paired workflows passed** against pinned
`d0940a12c44831095492efcd7091fb7b937ad6b3`: same native ARM64 engine, 2 CPUs/4 GiB,
network none, one warm-up and five shared-batch samples. Minimum raw sample
**378.072 ms**, maximum median increase **9.92%**, no invalid/short samples or
confirmation pair required. Reference/candidate source and locks were byte-verified;
input/output hashes matched with the previously reviewed calendar projection.
No benchmark reference, recipe or allowance changed. These measurements describe
that runtime; the cleanup changes no financial implementation.

Review followed intent → architecture → implementation → polish and independent
boundary/docs review. The referenced `code_review(8).md` and
`code_smell_review(9).md` were not supplied; this remains a review-source limitation.

## Final approved cleanup

Privacy red checkpoint `4ce30d8`: **1 failed, 7 passed** in offline Docker, before
configuration edits. The focused regression requires complete host-agent directory
exclusions, without re-inclusion rules. Normal Docker CI seeds both configuration
and unrelated-skill files, builds the image and directly verifies neither host-agent
directory was copied. Narrow Git rules are unchanged.

Active setup docs and AGENTS now describe fresh host-backed state without obsolete
handoff instructions. Storage scenarios retain ordinary accepted-state/saved-plan/
artifact recovery, integrity and failed-restore safety; their former transfer-specific
names and paths are removed. No test exists solely to enforce a volume handoff.
Final cleanup CI results are recorded below after verification.

Raw original evidence: ignored `benchmark-results/host-agent-2026-10-12/`.
Cleanup evidence: ignored `benchmark-results/host-agent-cleanup-2026-10-12/`.
Retain local logs for 90 days and unresolved failures through resolution. They are
local evidence, not remote CI results. No host package installation, Git push,
trade or real-provider call is part of acceptance. Real brokerage HTML/FMP contracts,
source rights, host-agent instruction following and encrypted off-device backup
remain the documented human gates. Stop after this finite cleanup; Phase 2 starts
only after foundation acceptance.
