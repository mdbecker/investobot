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
3. Set `FMP_API_KEY` in your shell environment before starting Docker Compose.
   Keep keys out of version control. This is a public market-data API key, never
   a brokerage credential.
4. Run the CLI in Docker. Missing keys, timeouts, rejected access and unexpected
   provider payloads produce external-data errors (exit code 2). Error messages
   do not echo request URLs or keys.

Official endpoint references checked during implementation:

- [ETF and fund holdings](https://site.financialmodelingprep.com/developer/docs/stable/holdings)
  maps to `/stable/etf/holdings?symbol=...`.
- [ETF and mutual fund information](https://site.financialmodelingprep.com/developer/docs/stable/information)
  maps to `/stable/etf/info?symbol=...`.
- [Dividend-adjusted history](https://site.financialmodelingprep.com/developer/docs/stable/historical-price-eod-dividend-adjusted)
  maps to `/stable/historical-price-eod/dividend-adjusted?symbol=...`.
- [Security profiles](https://site.financialmodelingprep.com/developer/docs/stable/profile-symbol)
  maps to `/stable/profile?symbol=...`, for supplied identifiers and classifications.

History only accepts explicitly adjusted close fields. It excludes unadjusted
prices rather than reporting their changes as total returns. Possible missing
weekday sessions produce warnings and an exact usable date range; holidays are
not inferred. Correlation uses returns between aligned dates, with at least
three prices and nonconstant returns. It reports the usable period.

## Offline demonstrations and tests

Pass an explicit fixture path to select synthetic data. The checked-in
`tests/fixtures/fmp-synthetic.json` contains invented funds AAA, BBB and PART,
with invented holdings, history and expenses. It is not recorded market data,
an investment suggestion or evidence of actual fund composition. Every result
states `source: SYNTHETIC_FMP_FIXTURE`. No key or network access is needed.

Python API: `MarketClient(ledger, api_key=None, fixture_path=None)` supplies
`holdings(ticker, refresh=False)`, `history(...)` and `metadata(...)`.
`security_metadata(...)` returns profile classifications without inventing missing fields.
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
seven days and return only classifications, not current quote fields. Synthetic and live data use
separate keys. Oldest constituent update bounds holdings as-of metadata;
historical as-of uses the latest observation. Retrieval freshness does not imply
the underlying fund disclosures are recent. No background refresh occurs.

OpenFIGI, Treasury and FRED are permitted future narrow sources in the PRD but
are not required or called by this initial structured-data implementation.
