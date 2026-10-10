# ETF and mutual-fund due diligence

Fund diligence preserves manually researched primary disclosures for one SEC
fund series and exactly one share class. It records fees, methodology, a dated
holdings snapshot, turnover, product-specific liquidity and historical per-share
distributions. It does not recommend investments, estimate investor taxes or
update household holdings, prices, plans or provider caches.

## Setup and research

No fund API account, token, brokerage credentials or new runtime dependency is
required. Use the existing Docker runtime for all Investobot execution. Your
external Codex or Claude Code agent uses its own browser to review original
public disclosures. Install bundled instructions explicitly into the chosen
project with `research skills install`; this copies files only into `.agents/skills`
or `.claude/skills`. Modified canonical files require review and `--confirm`;
unrelated user files survive.

For example, after the project's locked Docker image is built, these commands
use a disposable schema-10 research database under ignored `local-data` and do
not mount the private Docker ledger volume:

```sh
mkdir -p local-data
docker run --rm --network none -v "$PWD:/app" -e INVEST_DB=/app/local-data/fund-research.db -e INVEST_PROMPTS=/data/prompts investobot-v3-test invest research skills list
docker run --rm --network none -v "$PWD:/app" -e INVEST_DB=/app/local-data/fund-research.db -e INVEST_PROMPTS=/data/prompts investobot-v3-test invest research skills install --agent codex --workspace /app
```

Replace `codex` with `claude-code` for Claude Code. Replace the image name with
your locally built locked project image where appropriate. Invoke
`investobot-fund-diligence` in that external agent and identify the desired series
and share class. Its [source procedure](../skills/investobot-fund-diligence/references/research-method.md)
requires original SEC registrant CIK, series ID and class ID; names/tickers alone
cannot identify a fund. Inspect the actual filing, not merely a search result.

The exact contract is available through `invest schema` and
`invest tools describe research.funds.import`. Save one strict JSON object under
`local-data/fund-diligence.json`; the agent must leave missing values unknown and
separate reported facts from interpretation. Source locators identify concise
sections/tables without retaining full pages. All initial fixtures are fictional
and offline; they establish software behavior, not real fund accuracy.

## Preview, approve and inspect

Use the same disposable-container arguments above with these command suffixes:

```sh
invest research funds validate local-data/fund-diligence.json
invest research funds import local-data/fund-diligence.json
```

Validation and import preview never create the selected database. Review fund
identity, source dates and class-specific evidence in the original documents,
then explicitly approve acceptance:

```sh
invest research funds import local-data/fund-diligence.json --yes
invest research funds list --ticker TICKER
invest research funds show RUN_ID
invest research funds summary RUN_ID
invest research funds holdings RUN_ID
```

Only confirmed import writes research. Equivalent reordered input is an
UNCHANGED no-op; corrections append a new immutable run. `show` exposes the full
accepted package and trusted bundle identity. Other commands read compact
metadata or relational evidence and preserve actual observation dates and links.

Expense ratios and loads remain separate, waiver expiry is retained and ETF
trading metrics remain separate from mutual-fund NAV/redemption terms. Missing
distribution history does not establish tax efficiency. Partial holdings stay
partial: two 6%/4% holdings total 10%, with no invented 90% allocation. Largest-ten
observed concentration needs at least ten rows and is labeled according to
snapshot coverage. Provider-based `invest fund holdings`, `compare` and
`replacements` continue their separate workflows.

## Database compatibility and human acceptance

Fresh ledgers use schema 10. Older nonempty ledgers, including schema 9, are
rejected without migration or deletion. Preserve private ledgers and their
backups; choose a new research database rather than resetting private data.
If deliberately restarting a disposable test database, stop its users and remove
only its selected database plus the corresponding `-wal`/`-shm` files. Preserve
prompt overrides and unrelated data. No automatic reset is provided.

Before claiming real-source acceptance, a human must review one real ETF and
one real mutual-fund share class. For each, verify original SEC identity and
at least one original source for fees, holdings, methodology, turnover, liquidity
and distributions where available; document absent disclosures. Check source
origin, dates, exact class attribution, complete-versus-partial holdings and usage
rights. Structural validation and fictional tests do not satisfy this gate.
Record the review separately without rewriting accepted history. Remote GitHub
CI is also a separate gate; local offline Docker results cannot establish it.
