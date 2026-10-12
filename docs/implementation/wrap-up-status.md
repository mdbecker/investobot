# Finite MVP wrap-up

The [2026-10-12 addendum](../PRD-mvp-wrap-up-2026-10-12.md) controls the
remaining scope. Original PRDs remain historical specifications.

- A: approved the limited reference change from `7cbf2bed13a0447865403e986662119571217bc6`
  to `d0940a12c44831095492efcd7091fb7b937ad6b3`. All fifteen native
  operations comprising the eight retained workflows passed their existing
  independent financial oracles in the reference image. Application source is
  unchanged since that reference; the same recipe/harness will measure both.
- B: simplify the runner and safely isolated CI; archive generated evidence.
- C: simplify explicitly requested adversarial replay and bug reporting.
- D: focused safety review and concise documentation.
- E: final Docker correctness, lint, skill, synthetic demo and eight-case pair.

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
