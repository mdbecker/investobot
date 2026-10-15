# Development

Follow [testing](testing.md) for locked offline Docker commands and
[workflows](workflows.md) for the authoritative operational walkthrough.
The [current contract](contract.md) defines product and financial invariants.

Keep main; commit observed red tests before new behavior and green checkpoints
once verified. No fetch, remote operation or push. Use separate module ownership
for explicitly requested parallel work; the coordinator owns shared integration.
Freeze writes before exact-tree acceptance. Install no project packages on the host.

Use existing public behavior tests for pure refactors. Do not add internal mocks,
read-count assertions, skips, compatibility engines, migrations or broad new
frameworks. Preserve Decimal residues, typed evidence gaps and immutable facts.
Review intent, architecture, implementation, then polish. Correctness precedes
performance. Run only the eight fixed paired workflows described in
[performance](performance.md); new fuzz campaigns require explicit human invocation.

No real samples or secrets are needed for offline development. Provisioning and
source permissions remain human responsibilities in [data sources](data-sources.md)
and [readiness](readiness.md). Synthetic fixtures simulate only external source
inputs; SQLite, transactions, CLI, recovery, Parquet and native extensions are real.
