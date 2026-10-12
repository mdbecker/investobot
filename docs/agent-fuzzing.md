# Local agent fuzzing

Exploratory campaigns run only when a human explicitly requests one. The harness
does not launch an AI, require credentials, contact providers or publish issues.
Ordinary CI runs deterministic harness tests and promoted fixed regression cases;
it never generates or schedules a campaign.

Native performance certification is a separate release gate. Local exploratory
timings do not certify the documented reference machine or absolute budgets.
Do not start a live agent campaign before the performance foundation and native
acceptance gates have been verified. The checked-in fictional contract campaign
is a deterministic harness fixture, not a fresh exploratory campaign.

## Copyable instruction for an existing local coding agent

> Run a fresh, bounded Investobot fuzz campaign only in disposable offline Docker.
> Inspect recent changes, `invest tools list/describe`, `benchmarks/cases.json`,
> `fuzz/scenario.py`, prior local reports and retained novelty history. Design at
> least 12 distinct schema-valid JSON cases across at least five P01–P15 families,
> including four multi-step state transitions and two performance/growth cases.
> Prioritize changed code and missing family coverage. Vary action ordering,
> cross-record relationships, invalid inputs, numeric boundaries, sizes and
> failure modes; new names or seeds alone are insufficient. Cover every P01–P15
> family within five recorded campaigns and explicitly report remaining gaps.
>
> Write data only: no generated Python, shell, SQL, URLs, paths or executable
> assertions. Select allowlisted operations, mutations and independent invariant
> IDs. Expected values are result classes, never invented financial arithmetic.
> Validate the JSON, then run the offline harness. Revise invalid or duplicate
> proposals until accepted: exact inputs must be new and at least 25% of shapes
> must be absent from the previous ten retained campaigns. Bootstrap explicitly
> only on the first run; obtain human acknowledgment before proceeding after
> later history loss. Do not reset history to pass novelty checks.
>
> Save exact cases and replay suspected failures twice from clean state. Minimize
> without losing dependencies or the observed signature. Distinguish confirmed
> bugs, confirmed slow paths, expected rejections, unresolved findings and
> environmental failures. Rank a concise report with source/input hashes,
> violated invariants, exact evidence and agent-free reproduction commands.
> Compare performance only on identical saved input and equivalent local limits,
> using the shared benchmark gates, seven observations and one fresh paired
> retry; a tie at 25% passes. A matched 1×/4× growth suspect is not automatically
> a confirmed regression. No private ledger, account HTML, live APIs or secrets.
>
> Ask for approval before modifying production code or publishing external
> issues. Prepare a concrete minimized Given/When/Then regression proposal first.
> After approval, observe and commit red before fixing production; then verify
> green replay, the complete correctness suite and affected fixed benchmarks.
> Promote genuinely new hot paths as immutable deterministic benchmark inputs,
> preserving their independent oracle checks. Never add a CI fuzz campaign.

## JSON and execution

Use the current allowlist in `fuzz/scenario.py`. The campaign envelope is
`{"schema_version":1,"campaign_id":"local-campaign","cases":[...]}`. A case
has this shape (one example does not satisfy campaign breadth or novelty):

```json
{
  "id": "loss-basis-read",
  "family": "P06",
  "seed": 314159,
  "fixture_profile": "tiny",
  "records": 8,
  "operations": [{"name": "tax", "params": {"kind": "lots"}}],
  "mutations": [],
  "invariants": ["basis_conservation", "immutable_reads"],
  "expected_result": "SUCCESS",
  "performance_dimension": null,
  "rationale": "Inspect exact sourced remaining basis without accepted writes."
}
```

Run the following entry points **inside the project's network-disabled Docker
runtime**, with only the repository and a separate disposable output/history
directory mounted. Do not mount the private application ledger. Paths below are
container paths chosen by the human, never fields in generated scenario JSON.

```sh
python scripts/fuzz.py validate /data/fuzz/campaign.json
python scripts/fuzz.py run /data/fuzz/campaign.json --output-dir /data/fuzz/run-001 --history /data/fuzz/history.json --bootstrap
python scripts/fuzz.py replay /data/fuzz/run-001/saved-case.json --output-dir /data/fuzz/replay
python scripts/fuzz.py history-export --history /data/fuzz/history.json --output /data/fuzz/portable-history.json
python scripts/fuzz.py history-import /data/fuzz/portable-history.json --history /data/fuzz/history.json
```

Omit `--bootstrap` after the first run. Default scenarios allow at most 12
operations, 25,000 records and 20 MiB input; explicit local `--large` remains
bounded and uses tighter resource guards. Single saved-case replay does not need
12 cases or an AI. Keep history in ignored application data and export a
sanitized copy before rebuilding the machine. Reports and promotion drafts stay
local; review exact installed command help before running history commands.

Triage never edits benchmark inventory or production. Promotion requires two
clean reproductions, a fixed input, observed red and green evidence for the same
regression test, and human review. Structural validation cannot verify external
source truth, rights or real institution adapter compatibility.

The current local Docker target is native M4/ARM64 with CPU execution. Vector
fixtures use precomputed synthetic 384-dimensional vectors; no GPU embedding
provider is invoked, and no Metal or GPU device access has been verified.
An explicit future GPU adapter setup needs separate authorization and measured
evidence. Native ARM functional tests do not replace paired medium/extended
performance acceptance or reviewed reference capture before a live campaign.
