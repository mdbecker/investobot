# Verification

All execution, dependency resolution, tests and lint run in disposable Docker
containers. Install nothing on the host. Use the locked image and offline commands
in the [quickstart](../README.md); never mount a private ledger for acceptance.
Set `INVEST_PROMPTS=/data/prompts`. Ruff requires `--config pyproject.toml`.

New or changed behavior gets public-interface tests first, observed intended
failures and a test-only conventional commit before implementation. Record a
green conventional commit after the complete integrated suite passes. No skips,
expected failures or artificial internal mocks establish acceptance. Only
external network boundaries may be faked; databases, transactions, CLI, native
extensions, Parquet and recovery are real.

Fictional fixtures include source precision, provenance, coherent quantities,
prices, cash and verified lot identities. Tests cover both successful workflows
and missing-data/privacy/atomicity gates. Scripted skill drivers exercise actual
CLI sequences; real external-agent behavior remains a human smoke test.

Final verification uses an image built from the exact committed Git tree, locked
offline full tests and lint, installed-wheel CLI/skill checks, recovery and the
synthetic demonstration. Mounted-source results and local measurements are
explicitly distinct from exact-commit or remote CI evidence. See
[status](implementation/unified-mvp-status.md) and [benchmarks](benchmarks-unified-mvp.md).
