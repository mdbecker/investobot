# Competitive position and peer research

V2.8 adds evidence about one operating company and one to eight peers. An external
agent researches; Investobot validates and preserves the evidence; a human checks
original sources and decides whether to accept it. Commercial competition does
not establish investment suitability. There are no rankings, trade suggestions,
valuation forecasts, portfolio changes or automatic research jobs.

## Setup and review

No new API account, credential or host installation is needed. Build the Docker
runtime and discover the authoritative contract and portable instructions:

```sh
docker compose build
docker compose run --rm -T app invest research skills show investobot-competitive
docker compose run --rm -T app invest research skills install --agent codex --workspace /app
docker compose run --rm -T app invest schema
docker compose run --rm -T app invest tools describe research.competitive.import
```

Use `--agent claude-code` for project-local Claude Code installation. Installation
copies instructions only. Modified canonical files require explicit `--confirm`;
unrelated user files remain intact. Never put credentials in research JSON.

Ask your authorized external agent to use `investobot-competitive`, identifying
the legal subject, scope, geography and research date. Review its primary sources,
peer identities, segment overlaps, factual bases and separately stated inferences.
Save its single JSON object in ignored `local-data/competitive.json`, then:

```sh
docker compose run --rm -T app invest research competitive validate /app/local-data/competitive.json
docker compose run --rm -T app invest research competitive import /app/local-data/competitive.json
# After independent source review and explicit human approval:
docker compose run --rm -T app invest research competitive import /app/local-data/competitive.json --yes
docker compose run --rm -T app invest research competitive list --ticker TICKER
docker compose run --rm -T app invest research competitive show RUN_ID
docker compose run --rm -T app invest research competitive summary RUN_ID
docker compose run --rm -T app invest research competitive matrix RUN_ID --peer PEER_ID
```

Validation and preview do not create a selected database. Confirmation writes
research only, atomically. Reordered equivalent content and redundant financial
trailing zeros are unchanged; corrections create another immutable run. List is
compact, show returns the complete accepted package, and summary/matrix project
stored evidence. Earlier research and financial state remain separate.

## Reading a matrix

Rows retain exact reported values and citations, including missing sides as null.
A numeric comparison requires the same metric definition, accounting basis,
unit, exact dates, period type and scope. Segment observations additionally need
the same explicit overlap and its corresponding company-specific segment names.
Different currencies, fiscal calendars, FCF definitions, adjusted measures or
unconnected segments remain `NOT_COMPARABLE`; there is no FX or quarterization.

For a unique match, absolute difference is subject minus peer. Percentage
difference uses the peer as denominator and is null if that denominator is zero
or negative. Inexact division carries a rounding warning. Consolidated comparisons
do not demonstrate strength in an overlapping market. Missing private-company
numbers are unknown, never zero. A citation's presence cannot prove its truth.

## Database and release boundaries

Schema 7 initializes fresh ledgers only and rejects schema 6 and earlier without
migration or deletion. Keep existing private ledgers backed up and unchanged;
use a separate disposable database to evaluate V2.8. See
[deliberate reset instructions](development.md#deliberate-schema-reset) only if
you explicitly choose to discard a selected disposable ledger; preserve prompts.

Automated tests use fictional companies and offline sources. They do not establish
real-world source accuracy. The separate human gate requires a public subject,
two real competitors, verification of at least two overlaps and two findings,
several original reported metrics, and a deliberately incompatible pair. Local
Docker evidence is separate from GitHub Actions; no push means remote acceptance
remains unverified. The complete requirements are preserved in [PRD-v2.8.md](PRD-v2.8.md).
