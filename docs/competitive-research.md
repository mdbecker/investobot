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
./scripts/invest research skills show investobot-competitive
./scripts/invest research skills install --agent codex --workspace /app
./scripts/invest schema
./scripts/invest tools describe research.competitive.import
```

Use `--agent claude-code` for project-local Claude Code installation. Installation
copies instructions only. Modified canonical files require explicit `--confirm`;
unrelated user files remain intact. Never put credentials in research JSON.

Ask your authorized external agent to use `investobot-competitive`, identifying
the legal subject, scope, geography and research date. Review its primary sources,
peer identities, segment overlaps, factual bases and separately stated inferences.
Save its single JSON object in ignored `local-data/competitive.json`, then:

```sh
./scripts/invest research competitive validate /app/local-data/competitive.json
./scripts/invest research competitive import /app/local-data/competitive.json
# After independent source review and explicit human approval:
./scripts/invest research competitive import /app/local-data/competitive.json --yes
./scripts/invest research competitive list --ticker TICKER
./scripts/invest research competitive show RUN_ID
./scripts/invest research competitive summary RUN_ID
./scripts/invest research competitive matrix RUN_ID --peer PEER_ID
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

Fresh checksum-identified SQLite schema 1 initializes through existing application
behavior. Use disposable synthetic ledgers for evaluation; see
[operations](operations.md).

Automated tests use fictional companies and offline sources. They do not establish
real-world source accuracy. The separate human gate requires a public subject,
two real competitors, verification of at least two overlaps and two findings,
several original reported metrics, and a deliberately incompatible pair. Local
Docker evidence is separate from GitHub Actions; no push means remote acceptance
remains unverified. The complete requirements are preserved in [PRD-v2.8.md](PRD-v2.8.md).
