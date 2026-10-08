# Structured discovery

These tools return candidates and repeatable similarity metrics. They do not
recommend investments or determine wash-sale legality. Use browser research for
qualitative assessment and missing information. A person executes any trades.

## Equity screen

Pass a JSON filter object using supported FMP parameter names:

```json
{"sector":"Technology","marketCapMoreThan":"10000000000","priceLowerThan":"500","limit":100}
```

The adapter uses FMP's [company screener](https://site.financialmodelingprep.com/developer/docs/stable/search-company-screener).
Supported exact text criteria: `sector`, `industry`, `country`, `exchange`.
Supported numeric bounds: `marketCap`, `price`, `beta`, `volume`, `avgVolume` and
`dividend`, each suffixed `MoreThan` or `LowerThan`. Bounds are strict, finite,
nonnegative, with lower bound below upper bound. `dividend` refers to the
provider's annual dividend amount, not dividend yield. `isActivelyTrading` is a
JSON boolean. Equities exclude ETFs and mutual funds. Valuation, profitability,
growth and dividend-yield filters are deliberately unavailable in this adapter
until reliable provider field support is established. Unsupported filters fail
with input exit code 1; they are never silently ignored.

`limit` is an integer from 1 to 1000, default 1000. Reaching the candidate limit
sets `partial: true` and warns; it does not claim an exhaustive market universe.
No background jobs, recommendations or other commercial vendors are involved.

## Fund search

Example filter object:

```json
{"fund_type":"ETF","expense_ratio_max":"0.10","aum_min":"1000000000","issuer":"Example issuer","limit":100}
```

`fund_type` accepts `ETF` (default) or `MUTUAL_FUND`. The adapter first obtains
the FMP candidate universe, then checks supplied fund metadata. Expense ratio
is in provider percentage units: `0.10` means 0.10 percent. AUM is a provider
amount, with no invented currency conversion. Issuer is an exact text match
ignoring case. Missing required metadata excludes the candidate and produces a
warning. API entitlements and fund coverage can limit results. Category, style
and benchmark filters are unavailable; missing fields are never inferred.

Fund filtering may request metadata for every returned candidate. Use a modest
limit to respect provider quotas. Metadata uses the normal 24-hour SQLite
cache; screening itself is a fresh request. Each result includes provenance.
Warnings make incomplete coverage explicit.

## Replacement similarity

Supply an original fund and an explicit candidate symbol list. Duplicates and
the original fund are removed. The tool returns overlap, active share,
historical return correlation, expense ratio difference in percentage points,
fund type and benchmark when supplied. Raw metrics and source provenance remain
available alongside the score. Missing holdings produce `DATA_UNAVAILABLE` and
null metrics rather than guessed exposures.

The transparent score is:

```text
0.7 × holdings overlap + 0.3 × max(0, historical return correlation)
```

Scores range from 0 to 1 for complete, valid holdings. Missing correlation or
partial holdings leave the score null. A high correlation with zero holdings
overlap receives only the correlation portion. Expense, benchmark and fund type
remain separate raw metrics; unknown metadata is never imputed. Candidates
sort by score descending, with unscored candidates last. This is an analytical
portfolio-similarity score, not a prediction or legal test. Every ranking includes:

> This score does not determine whether securities are substantially identical for tax purposes.

Python API: `screen(client, filters)`, `search(client, filters)` and
`replacements(client, original, candidates)` in `invest.discovery`. The client
is `MarketClient`; use `FMP_API_KEY` for live data or an explicit synthetic
fixture path for offline demonstrations. `tests/fixtures/discovery-synthetic.json`
contains entirely invented securities and does not require internet or credentials.
