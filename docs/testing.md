# Verification

All execution, dependency resolution, tests and lint run in disposable Docker
containers. Install nothing on the host. Use the locked image and offline commands
in the [quickstart](../README.md); never mount a private ledger for acceptance.
Ruff requires `--config pyproject.toml`.

New behavior and confirmed bugs get public-interface tests first, observed intended
failures and a test-only conventional commit before implementation. Record a
green conventional commit after verification passes. Pure refactors use existing
green behavior tests; do not manufacture red failures or test internal read counts.
No skips,
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

## Current offline commands

```sh
docker build -t investobot-test .
docker run --rm --network none investobot-test uv run --locked pytest -q
docker run --rm --network none investobot-test uv run --locked ruff check --config pyproject.toml src tests benchmarks scripts fuzz
docker run --rm --network none investobot-test uv run --locked python scripts/demo_unified_mvp.py
```

Never bind the operator's `local-data/state` for acceptance. Host bridge/Compose
lifecycle validation uses a disposable checkout and synthetic data; financial
pytest fixtures use temporary real SQLite. The shell forwarding test substitutes
only the external Docker executable boundary, and is complemented by real
Compose discovery/stdin/install/persistence checks. Performance retains exactly
eight paired representative workflows and its confirmed >25% guard, as described
in [performance](performance.md). Retain raw local evidence outside Git for 90
days and unresolved failures through resolution. No remote CI result is implied.
