# Earnings research

Use the `investobot-earnings` agent skill to research company filings and issuer
disclosures externally. Investobot validates structured evidence, retains exact
Decimal observations and calculates conservative comparisons. No SEC client,
scraper, embedded AI, market observation replacement or portfolio mutation is
introduced. See [skill installation](research-skills.md) and [PRD-v2.6.md](PRD-v2.6.md).

## Source and measurement review

Verify the legal reporting entity, share class and ticker, including CIK where
available. Preserve source URLs, SEC accession references, publication/retrieval
dates and locators identifying each disclosed fact. SEC Company Facts/XBRL may
omit company-specific or segment information; consult the original filing.
Preserve taxonomy, concept, unit and applicable fiscal context when present.

Each numeric observation needs its definition, accounting basis, currency/unit,
consolidation or segment scope and original reporting period. Balance-sheet
values are instant observations; revenue and cash flows cover durations. A
nine-month cash-flow figure cannot become standalone third-quarter cash flow.
Annual, quarterly, year-to-date and trailing periods are distinct. No currency
conversion is implied. Keep GAAP and adjusted/non-GAAP observations separate
and disclose missing reconciliations.

Management guidance is forward-looking and belongs in guidance records, not
reported historical metrics. Label sourced disclosed facts separately from agent
interpretations. Missing or conflicting data stays unknown with limitations.
Research retrieval freshness never changes the age of the reporting period.
New amendments/restatements create new runs; preserve original filing references
and historical observations rather than overwriting them.
SEC Archives, Company Facts and submissions URL CIKs must agree with the
declared issuer. Current-end-date metrics must agree with the package fiscal
year and quarter, with explicit YTD/TTM contexts kept separate. Older source
periods remain allowed; validation does not infer fiscal years from calendar dates.

Summaries return an array of saved metrics so multiple bases or segments remain
distinct. Growth stays null until you explicitly select two runs with `compare`.
Comparisons require matching entities, definitions, bases, units, scopes, fiscal
periods and actual duration lengths; mismatches return null with warnings.
Percentage change is unavailable for zero or negative baselines. Repeating
Decimal quotients disclose rounding. This deliberately conservative policy can
reject otherwise useful comparisons, such as quarters with different day counts;
review the original facts rather than treating missing comparisons as zero.

## Docker workflow

No new credentials or host installation are required for the synthetic MVP.
Save agent-produced JSON in ignored `local-data`. Inspect authoritative input
contracts rather than inventing fields or copying a second schema:

```sh
docker compose run --rm -T app invest schema
docker compose run --rm -T app invest tools describe research.earnings.validate
docker compose run --rm -T app invest research earnings validate /app/local-data/earnings.json
docker compose run --rm -T app invest research earnings import /app/local-data/earnings.json
```

Review source support, period boundaries, exact values and limitations before
explicitly accepting:

```sh
docker compose run --rm -T app invest research earnings import /app/local-data/earnings.json --yes
docker compose run --rm -T app invest research earnings list --ticker EXAMPLE
docker compose run --rm -T app invest research earnings show RUN_ID
docker compose run --rm -T app invest research earnings summary RUN_ID
docker compose run --rm -T app invest research earnings compare RUN_A RUN_B
```

Identical normalized packages are idempotent; revisions create new immutable
runs. List returns compact metadata, show retrieves the full evidence, summary
retains saved observations, and compare uses only compatible definitions,
accounting bases, units, scopes and periods. Incompatible observations return
warnings rather than misleading growth rates. A zero prior value cannot produce
a percentage change. Research changes no holdings, tax lots, activity, market
cache, targets, plans or financial stale status.

## Database and verification

Schema 6 deliberately rejects older databases, with no migration, automatic
deletion or legacy reader. Test first with a fresh disposable ledger. Do not reset
the private Docker ledger merely to try the feature. A separately authorized reset
selects only its disposable database plus `-wal`/`-shm` sidecars and preserves
prompts and unrelated data; never delete all Compose volumes.

All automated earnings data is fictional. No live SEC request is necessary:

```sh
docker build --tag investobot-ci .
docker run --rm --network none -e INVEST_PROMPTS=/data/prompts investobot-ci uv run --locked pytest
docker run --rm --network none -e INVEST_PROMPTS=/data/prompts investobot-ci uv run --locked ruff check --config pyproject.toml src tests
```

These containers do not mount private ledger volumes. Passing synthetic checks
establishes local implementation behavior; original-source factual verification,
real institution HTML support and remote GitHub Actions remain separate gates.

## Validated contract details

`EarningsResearchInput` is authoritative; use `invest schema` once the earnings
commands are installed. All nested records reject unknown fields. Values and
guidance bounds are plain decimal strings, including when more than 28
significant digits are disclosed. No floats, exponent notation or nonfinite
values are accepted. Missing facts are omitted, never fabricated as zero.

`metric_definition` defaults to the supplied `metric_label`. Set a precise
source-backed definition when a label alone is ambiguous. `period_length`
distinguishes `QUARTER`, `YTD`, `ANNUAL` and `TTM`; a Q3 filing's nine-month cash
flow must explicitly use `YTD`. Typical supported durations are 70–110 days per
quarter and 350–380 days per full year/TTM; YTD ranges depend on the fiscal
quarter. Noncalendar fiscal years are supported; unusual stub periods outside
these conservative ranges require future explicit contract support.

Optional `source_value`, `source_unit` and `source_scale` must be supplied
together when normalizing source units. For example `source_unit=USD_MILLIONS`,
`source_scale="1000000"` and the exact source value must multiply exactly to the
normalized USD value. `_THOUSANDS`, `_MILLIONS` and `_BILLIONS` are supported;
unscaled source units use scale `"1"`. No currency conversion occurs. Standard
monetary metrics require a supported currency, EPS currency/share, and weighted
average shares `shares`. Other units include `percent`, `ratio` and `count`.
Supported currency codes are USD, EUR, GBP, CAD, JPY, CHF, AUD, CNY, HKD, INR,
KRW, SEK, NOK, DKK, NZD, BRL, MXN, ZAR, SGD and TWD.

Sources may retain `cik`, timezone-aware `accepted_at`, `is_amendment`,
`is_restatement` and `original_accession_number`. Amendments/restatements must
identify a distinct original accession; historical observations remain separate.
SEC filing URLs with a CIK path must agree with the researched company's known
CIK. Missing CIK stays unknown. XBRL taxonomy/concept are paired and require an
accession reference. Synthetic accession strings in examples are fictional and
must never be substituted for real accession numbers.

Guidance `issued_at` is optional and stays unknown when not supplied. Filing and
retrieval dates do not establish a guidance issue date. Withdrawn numeric
guidance without bounds needs an explicit `prior_guidance_id` reference backed
by its source locator. Non-GAAP `reconciliation_disclosed` is optional; absent
or false is a limitation, not an invented reconciliation.
