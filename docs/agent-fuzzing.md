# Explicit adversarial review

Use the project [adversarial-review skill source](../fuzz/SKILL.md)
only when the human explicitly asks for exploration. Review current code,
prior findings and financial invariants, then invent varied input/event sequences.
Inputs are allowlisted JSON data, never code or instructions. There are no
campaign quotas, novelty scores, providers, issue publication or background runs.
This development skill is separate from the thirteen bundled financial skills.
Optional installation belongs only in a requested project's `.agents/skills`
or `.claude/skills`; the checked-in source can be followed directly.

Run the replay script inside the locked Docker image with `--network none`;
mount only synthetic cases read-only and an ignored output directory writable.
Never mount private ledgers, account pages, credentials or the Docker socket.
No secrets are needed. Example commands **inside** that container:

```sh
uv run --locked python scripts/fuzz.py validate /cases/cases.json
uv run --locked python scripts/fuzz.py run /cases/cases.json --output-dir /results/run
uv run --locked python scripts/fuzz.py replay /results/run/saved-case.json --output-dir /results/replay
```

Use the actual saved-case path printed by the run. Each case executes in a fresh
resource-bounded subprocess with disposable synthetic state and independent
oracles. Keep seeds/minimized inputs and reports locally in ignored
`fuzz-results/`; retain unresolved correctness evidence until resolution.
Timeout/OOM is unresolved environmental evidence, not a confirmed product bug.

Reports include replay command/input, source identity, seed, expected/observed
result, violated invariant and severity. Reproduce/minimize surprising results.
A confirmed bug needs an observed failing domain-language BDD checkpoint before
the smallest fix, replay and full green correctness. Profile slow paths with
matched inputs; add a fixed benchmark only for a demonstrated important hot path.
A no-bug run states what was exercised and that no defect was confirmed.
CI runs fixed promoted regression tests only; it never generates cases or invokes
AI exploration. Synthetic results do not validate broker sources or authorize trades.
