# Historical hypothetical backtests

`run` freezes a portfolio allocation, requested dates, policy, source manifest,
algorithm version and financial starting inputs in an immutable saved experiment.
`compare` reads those saved results only. It refuses comparisons with different
periods, sessions, source hashes, universes, contribution schedules or model
assumptions. Missing observations never shorten a candidate's requested window.

Today's portfolio is labeled `HYPOTHETICAL_CURRENT_ALLOCATION`: it imagines deploying
today's weights at the historical start and is not actual account performance.
Target allocations are also hypothetical. Cash earns zero by default. The model
uses dividend-reinvested total-return indexes, no external contributions unless
explicitly supplied, zero default modeled fees/slippage and no modeled taxes.
Explicit contributions are allocated using the same frozen weights. Per-trade fees
reduce available hypothetical capital and remain part of the return calculation.
Optional `QUARTERLY` rebalancing checks the first eligible session above the pinned
drift threshold in March, June, September and December, at most once per month.
Fees apply to each changed security; taxes remain outside this hypothetical model.
This optional historical strategy never imposes a live trading schedule.

Inputs require positive dated `total_return_index` observations. Unadjusted prices
and an unexplained adjusted-close field are insufficient. Explicit manifest
`sessions` establish the calendar against which missing observations are rejected.
Without that calendar, coverage is disclosed as provider-observed sessions only;
this cannot establish that an entire exchange history is complete. No arbitrary
forward fill or extrapolation is performed. Constituent data is not substituted
for historical security return evidence. No survivorship-free claim is made.

Total return and balances use Decimal. Annualized return and sample daily
volatility use disclosed floating-point statistics; volatility assumes 252 sessions
per year. Drawdown is calculated on linked growth after excluding explicit external
contributions. Results include tracking dates, turnover, assumptions and final
allocation. Pretax hypothetical outcomes are not actual tax savings.

The functions do not refresh quotes, change accepted holdings, spend planning tax
budgets or write market caches. Saving a calculation writes only `backtest_runs`.
Provider entitlement, original-source verification and real-data completeness
remain human review gates.

The dashboard lists saved runs, reads their immutable results and compares selected
runs through GET requests. Incompatible assumptions remain `INCOMPARABLE` with
reasons; viewing never runs a new simulation or saves another result.
