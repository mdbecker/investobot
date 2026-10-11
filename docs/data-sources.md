# Structured data and setup

FMP is the only commercial structured market-data provider. No brokerage login,
account aggregation, trades, news feed or second commercial vendor is used.
The ledger is authoritative for account balances and broker-supplied basis;
market data never modifies portfolio positions or tax lots.

## Live FMP setup

1. Create an account directly with [FMP](https://site.financialmodelingprep.com).
2. Check your plan's entitlement to holdings, fund metadata and dividend-adjusted
   history; endpoint access and available symbols vary by plan. The app does not
   subscribe or buy data for you.
3. Set `FMP_API_KEY` in your shell environment or ignored `.env` before starting
   Docker Compose. Keep keys out of version control and chat transcripts. This
   is a public market-data API key, never a brokerage credential. Recreate the
   running service after changing its environment.
4. Run the CLI in Docker. Missing keys, timeouts, rejected access and unexpected
   provider payloads produce external-data errors (exit code 2). Error messages
   do not echo request URLs or keys.

Official endpoint references for the implemented mappings:

- [ETF and fund holdings](https://site.financialmodelingprep.com/developer/docs/stable/holdings)
  maps to `/stable/etf/holdings?symbol=...`.
- [ETF and mutual fund information](https://site.financialmodelingprep.com/developer/docs/stable/information)
  maps to `/stable/etf/info?symbol=...`.
- [Dividend-adjusted history](https://site.financialmodelingprep.com/developer/docs/stable/historical-price-eod-dividend-adjusted)
  maps to `/stable/historical-price-eod/dividend-adjusted?symbol=...`.
- [Security profiles](https://site.financialmodelingprep.com/developer/docs/stable/profile-symbol)
  maps to `/stable/profile?symbol=...`, for supplied identifiers and classifications.
- [Public quotes](https://site.financialmodelingprep.com/education/index-articles/instant-stock-intelligence-a-comprehensive-guide-to-fmps-quote-api)
  maps to `/stable/quote?symbol=...`. Quotes are public observations, never updates
  to ledger prices, balances or lots.

History only accepts explicitly adjusted close fields. It excludes unadjusted
prices rather than reporting their changes as total returns. Possible missing
weekday sessions produce warnings and an exact usable date range; holidays are
not inferred. Correlation uses returns between aligned dates, with at least
three prices and nonconstant returns. It reports the usable period.

## Offline demonstrations and tests

Pass an explicit fixture path to select synthetic data. The checked-in
`tests/fixtures/fmp-synthetic.json` contains invented funds AAA, BBB and PART,
with invented holdings, history and expenses. It is not recorded market data,
an investment suggestion or evidence of actual fund composition. Provider
observations state `source: SYNTHETIC_FMP_FIXTURE`; analyses retain their source
provenance. No key or network access is needed.

Python API: `MarketClient(ledger, api_key=None, fixture_path=None)` supplies
`holdings(ticker, refresh=False)`, `history(...)` and `metadata(...)`.
`security_metadata(...)` returns profile classifications without inventing missing fields.
`quote(ticker, refresh=False)` returns a public price observation, with
`DATA_UNAVAILABLE` for missing prices and external-data errors for malformed values.
`compare(client, fund_a, fund_b, refresh=False)` supplies quantitative similarity.

Explicit ISIN/CUSIP/FIGI aliases occurring together bridge identity across rows.
A ticker-only observation joins a strong identity only if the ticker identifies
one such identity in the compared dataset. Conflicting strong identifiers are
not joined merely because a ticker matches. Names alone do not establish identity.

Holdings include all returned provider rows, with decimal weights in fractions
(60 percent becomes `"0.6"`). Missing or unsupported weights remain unresolved.
The app does not rescale incomplete portfolios to 100 percent. Coverage that
differs from 100 percent by more than 0.5 percentage points is flagged partial;
this heuristic does not certify completeness. Missing holdings return
`DATA_UNAVAILABLE`; comparison requires holdings for both funds. Similarity does
not determine whether securities are substantially identical for tax purposes.
Metadata expense ratios preserve the provider's percentage units (0.10 means
0.10 percent); missing values stay null.

## Cache and provenance

SQLite stores normalized public holdings and market responses, with `source`,
`retrieved_at` and `data_as_of` when supplied. Holdings, daily history and fund
metadata expire after 24 hours. `refresh=True` bypasses cache. Expired cache is
never silently returned after a provider error. Security profiles expire after
seven days and return only classifications, not current quote fields. Quotes
expire after 15 minutes; their as-of time is the provider's Unix timestamp
converted to UTC, when supplied. Quotes can be delayed or from a closed market,
even when newly retrieved. Synthetic and live data use
separate keys. Oldest constituent update bounds holdings as-of metadata;
historical as-of uses the latest observation. Retrieval freshness does not imply
the underlying fund disclosures are recent. No background refresh occurs.

OpenFIGI, Treasury and FRED are permitted future narrow sources in the PRD but
are not required or called by this initial structured-data implementation.

## Docker configuration and optional tax rates

The default Compose service passes `FMP_API_KEY` from the shell/ignored `.env`.
Run a clearly labelled offline command without an API key:

```sh
docker compose run --rm -T \
  -e INVEST_FIXTURES=/app/tests/fixtures/fmp-synthetic.json \
  app invest fund compare AAA BBB
```

If choosing local TOML configuration, copy
[the configuration example](config.example.toml) into ignored
`local-data/config.toml`. Never commit actual keys or financial assumptions. An
explicit one-off container sees that file with:

```sh
docker compose run --rm -T -e INVEST_CONFIG=/app/local-data/config.toml \
  app invest tax lots --as-of 2026-10-08
```

Optional `[tax]` entries are fractional rates represented as Decimal strings:
`ordinary_income_rate`, `long_term_capital_gains_rate`, optional `niit_rate` and
optional `state_capital_gains_rate`. Both ordinary-income and long-term rates are
required for tax-dollar estimates. Supply only human-confirmed assumptions,
following [tax limitations](tax-limitations.md); omitted rates remain unknown
rather than becoming guessed tax savings. Pass the same configuration to plans
being compared. For the running dashboard, set `INVEST_CONFIG` in a private
Compose override/environment configuration and recreate the container; a host
path is not automatically a container path.

## Outstanding manual integration checks

Generic HTML validation rejects ambiguous repeated cash labels and duplicate
recognized financial columns. Malformed cash stays unknown and blocks claiming
complete coverage. Complete tax-lot coverage requires parseable acquisition
dates and known basis for position rows. Without a reviewed broker lot ID or
immutable sourced acquisition reference, a generated lot remains unresolved
and unsaleable. A hash of mutable quantity/basis cannot establish lot identity.
Review matching manually for partial pages; do not replace confirmed inventory
with newly generated identifiers.

Offline tests use synthetic fixtures and mock provider boundaries. They do not
establish live endpoint entitlement, full fund coverage or actual institution
support. Human release checks remain:

1. **Real institution HTML:** provide representative anonymized holdings, lots,
   restricted retirement funds, mutual funds, bank/cash tables and partial pages
   for Vanguard, Fidelity NetBenefits and PNC. Remove private account identifiers
   and sensitive content; never commit raw private pages. Validate quantities,
   valuations, basis, dates, identifiers and completeness against known expected
   normalized facts. Update provisional parser aliases only after the actual
   shapes are covered by tests. Dynamic/non-table pages can remain unsupported.
2. **Live FMP:** the human supplies an FMP test API key locally and confirms
   entitlements. In Docker, inspect `market quote TICKER --refresh`,
   `fund holdings TICKER --refresh`, `market history TICKER --refresh` and
   `fund compare TICKER_A TICKER_B --refresh` for researched supported symbols.
   Compare observed formats, currency, weight coverage, date/provenance fields,
   adjusted-return assumptions, refresh/TTL behavior and error handling with
   official vendor data. Keep credentials/private diagnostics outside Git.
   Unexpected shapes need anonymized regression fixtures and fixes before
   claiming live compatibility.
3. **Source rights:** independently review original-source reuse permissions and
   local political-contribution rights policies. Agent assertions cannot authorize
   restricted named records or embedding broker/personal data.
4. **External agent skills:** exercise installed skills with the chosen agent,
   verify command discovery and explicit confirmations, and review cited sources.
   Offline scripted walkthroughs do not establish actual agent compliance.

Manual validation must not place trades, supply broker credentials or overwrite
canonical portfolio marks. Public quote refresh is cache-only. Automated tests
and CI remain offline and never require secrets. Synthetic household fixtures
are not automatically applied to a user's database. The source snapshot date is
independent of its import time; no fixture or successful refresh can certify a
real account's freshness or completeness.
