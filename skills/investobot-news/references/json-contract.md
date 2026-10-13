# Authoritative contract and acceptance

Use `./scripts/invest schema` to inspect `NewsResearchInput` and
`./scripts/invest tools describe research.news.validate` / `research.news.import` for current
inputs and mutation scopes. These generated contracts are authoritative; do not
maintain a separate schema in skill text or add unsupported fields.

The package uses schema version `1.0` and research type
`NEWS_CATALYSTS_THESIS_CHANGES`. It contains company, scope, sources, theses, events,
catalysts and limitations. Discover required fields, strict types, enums and links
from the CLI. Investobot pins trusted bundled skill metadata independently; do not
supply skill-version assertions. Use fictional evidence only for offline testing.

```sh
./scripts/invest research news context --ticker EXAMPLE
./scripts/invest research news validate /app/local-data/news.json
./scripts/invest research news import /app/local-data/news.json
# Only after explicit human approval of the reviewed preview:
./scripts/invest research news import /app/local-data/news.json --yes
./scripts/invest research news list --ticker EXAMPLE
./scripts/invest research news show RUN_ID
./scripts/invest research news summary RUN_ID
./scripts/invest research news changes --ticker EXAMPLE
./scripts/invest research news compare RUN_OLD RUN_NEW
```

Validation, preview and inspection are read-only. Confirmation stores research
only; repeated identical normalized packages are no-ops. No command establishes
legal source permission or factual truth. Human review must inspect original
citations, identity, date certainty, duplicate keys and disputed evidence before
acceptance. Neither `--yes` nor a valid schema proves a source supports a claim.
