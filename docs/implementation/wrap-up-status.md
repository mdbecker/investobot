# Finite MVP wrap-up

The [2026-10-12 addendum](../PRD-mvp-wrap-up-2026-10-12.md) controls the
remaining scope. Original PRDs remain historical specifications.

The [targeted final-review follow-up](review-follow-up-2026-10-12.md) supersedes
the tiny-fixture measurements below with representative inputs and seed-free
replay. The application reference is unchanged. The supplied review confirms
both remote workflows passed; repository required-check enforcement remains
human-owned.

- A: approved the limited reference change from `7cbf2bed13a0447865403e986662119571217bc6`
  to `d0940a12c44831095492efcd7091fb7b937ad6b3`. All fifteen native
  operations comprising the eight retained workflows passed their existing
  independent financial oracles in the reference image. Application source is
  unchanged since that reference; the same recipe/harness will measure both.
- B: simplified the runner to eight workflows and isolated hosted ARM CI;
  archived generated evidence. Retired cases/controllers/scaling/templates and
  duplicate unified runner are removed. Focused checks: 33 tests and Ruff pass.
- C: simplified manual adversarial skill and isolated replay/minimization/reports;
  removed quotas, novelty/history and benchmark promotion machinery. Eleven
  fixed replay/privacy/rejection/resource tests and Ruff pass. No AI campaign ran.
- D: reviewed import scoped reads/call-local indexes and retained them: no stale
  cache or ambiguous identity behavior found. Removed internal read-count checks,
  preserving financial outcomes: 24 focused import/lifecycle tests and Ruff pass.
  The referenced `code_review(8).md` / `code_smell_review(9).md` were not present
  in the repository or supplied attachments; review followed the addendum's
  stated intent/architecture/implementation/polish and smell categories.
- E: final committed ARM image passes correctness, lint, synthetic workflows,
  installed-wheel skills and all eight paired workflows. Finite wrap-up complete.

## Final acceptance and handoff

Tested code commit `34ca5bc7045bd020eb482da58c3e2713d020115d`, ARM64 image
`fedae15fab72`, offline Docker with no private ledger or credentials:

- `uv run --locked pytest -q`: **1,314 passed in 45.88 s**. Retired timing,
  quota and internal read-count contracts are removed; financial BDD remains.
- `uv run --locked ruff check --config pyproject.toml src tests benchmarks scripts fuzz`:
  all checks passed.
- `uv run --locked python scripts/demo_unified_mvp.py`: **34 actual CLI steps**,
  no external calls, exact lot conservation, immutable hypothetical facts,
  verified archive/artifact restoration and restored corpus retrieval. Financial
  fingerprints match: `e80cee513356e0fc5a528e90d6d10afd3fc19d73e82e2ecc027bde270c10463c`.
- Offline wheel build/install in the disposable container: all **13 bundled
  financial skills** discovered with their packaged instructions. The manual
  development fuzz skill lives separately at `fuzz/SKILL.md`.

Removed `benchmarks/paired.py`, `scaling.py`, `templates.py`, the duplicate
`scripts/benchmark_unified_mvp.py`, obsolete broad certification tests,
`fuzz/novelty.py` and generated benchmark reports. Consolidated runner/gates,
replay/minimization and current status docs. The existing plan-storage helper
remains for ordinary functional storage tests. No financial application source
or dependencies changed; existing import optimizations pass safety checks.

Commits remain local on `main`; no host installs, pushes, private-volume tests,
live campaigns or automated trading occurred. Documentation/capture metadata
recorded after acceptance do not alter the tested runtime or fixture recipe.

## Native paired results

Reference: `d0940a12c44831095492efcd7091fb7b937ad6b3`; candidate:
`34ca5bc7045bd020eb482da58c3e2713d020115d`, image `fedae15fab72`.
Both used the same harness, native ARM64 Docker Desktop engine, 2 CPUs,
4 GiB, network disabled, one warm-up and five samples per workflow.
The smallest raw sample was 367.396 ms. Fixture inputs, outputs and processed
counts matched; no confirmation was needed. The fixed 26% repeated-regression
contract returns FAIL, while an unconfirmed increase requests a complete repeat.

| Workflow | Reference median ms | Candidate median ms | Ratio |
|---|---:|---:|---:|
| TWR/XIRR and linked flows | 1.2253 | 1.2213 | 0.9967 |
| Tax lots / annual budget | 0.6885 | 0.6948 | 1.0091 |
| Contribution / saved plans | 9.6998 | 9.8488 | 1.0154 |
| Household TLH | 0.1363 | 0.1343 | 0.9852 |
| Recursive look-through | 4.4611 | 4.3571 | 0.9767 |
| Ten-year backtest | 87.2724 | 84.2883 | 0.9658 |
| Historical analytical join | 71.8603 | 74.2901 | 1.0338 |
| Text/vector corpus retrieval | 2.7292 | 2.6967 | 0.9881 |

Medians are normalized by shared batch counts; preparation/reset/oracle work is
outside the financial operation boundary. Raw reports, including earlier invalid
short samples and superseded incomplete fingerprints, are retained in ignored
`benchmark-results/2026-10-12`. A 600 ms batching target replaces 300 ms cold
warm-up calibration; the strict 200 ms floor and 25% guard are unchanged.
SHA-256 reference / candidate / comparison reports:

```text
264d3d54f692e7e7c45b42fc6dc6571ac74aa1e2c577bc1ff6cf69b6b66dc820
486f8188aed04c97c5aaa710cfbc6a54d35a3d3eb0dd948dd965b8017c1bcca6
c1f2dd66ab6002250e8d9ebd2149aaf45e9fb404becb6ae3767441195c7c875e
```

Remote CI execution and required-check enforcement remain UNVERIFIED. No push
or repository settings change was performed.

## Historical rebaseline evidence

The old 4,000-position import took 460.992 seconds; `77a8515` took 23.241
seconds on identical synthetic inputs with matching financial outputs.
Final `d0940a1` matched-size medians were 0.470/1.885 seconds for
1,000/4,000 positions. These retired diagnostics justify the administrative
reset; they do not certify retained workloads or real brokerage parsing.
The matched medium fixture hash was
`2da741ff25b5a2fff769c88419bba58d5a51d787addf7c3f1eac66dcd4dc71f3`.
The retained recipe SHA-256 is
`7141a3f57f267e92f17fc3c22ff1c3390d466b6837a5c84cb733b659a0c313ac`.
Original evidence remains in Git history and a local ignored archive; no
history rewrite or further import optimization is authorized.

The stress input/output hashes were respectively
`e00241390564030e0fdcfbc2c35bd99a79de6aa272baf39e34df374b160cd184` /
`81bf88821cba296c1e1c08653a8a1ea4b7441d59a6df19a603ea17fde56037ce`.
The 25-file archive is `local-data/performance-archive/2026-10-12`, with
SHA256 manifest hash
`7d304c5721f420c6c53f237004a7f4d5f67529f44325ff9f8fbd5010cade2bf7`.
Retain local diagnostic archives for 90 days; retain evidence of open
correctness issues until resolution. CI artifacts expire after 30 days.
Git history preserves prior committed evidence indefinitely. New raw results
belong in ignored `benchmark-results/` or `fuzz-results/`, never the build context.

## Human prerequisites

Vanguard, Fidelity NetBenefits and PNC profiles remain PROVISIONAL until
reviewed sanitized real HTML is supplied. FMP live entitlement remains
UNVERIFIED. Real financial readiness requires the nine sourced workflows or
typed blockers, human policy/lot/wash-sale review and complete dated evidence.
Synthetic demonstrations do not establish real-source accuracy. No broker
credentials or trade execution belong in this application.
