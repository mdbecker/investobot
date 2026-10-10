# Unified MVP rebuild evidence

Specification: [preserved October 10 PRD](../PRD-unified-mvp-2026-10-10.md).
This is an implementation record, not a claim that the rebuild is delivered.
Historical PRDs retain their original contents.

## Baseline

- Branch: `main`; source commit `5120897e9e5a314ad50fb242ad1496d976549a92`.
- Offline Docker image: `investobot-unified-baseline`.
- `uv run --locked pytest -q`: **862 passed**, 33.66 seconds.
- `uv run --locked ruff check --config pyproject.toml src tests`: passed.
- Containers have no network and no private ledger volume. No host packages installed.

## Global red phase

New acceptance files live under `tests/features/mvp/`, grouped by user domain.
Each step uses fixed fictional inputs and disposable SQLite files; only external
network boundaries may be faked. Independent agents own accounting, decision,
and research workflow scenarios; the coordinator owns recovery and datasets.
No production implementation starts until the complete scenario inventory is
observed with valid requirement failures and committed as a test-only checkpoint.
A baseline regression may pass already; it must remain an explicit regression.

The minimum B01–B66 inventory is being reviewed for fixture correctness and
additional work-package requirements. Recovery/data diagnostics currently include
missing `db` commands, missing pinned analytical readers, untyped provider gaps,
public native bind acceptance and absent portable portfolio skills. These are
expected unmet behaviors, not release failures being hidden with skips.

## Remaining delivery gates

WP01–WP12 implementation, integrated full-suite green, locked offline fresh-image
verification, recovery roundtrip, synthetic CLI demonstration, performance
measurements and current operations docs are outstanding. No new-design ledger
is claimed available yet. No existing ledger has been reset or migrated.

Vanguard, Fidelity NetBenefits and PNC require reviewed redacted original HTML;
synthetic pages cannot establish institution support. FMP entitlement/endpoints
require the user's manually reviewed live-provider gate. Real-company source
truth, permissions and actual LLM skill-following remain separate human gates.
No GitHub Actions result is claimed; this session never pushes.
