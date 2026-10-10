# Fees, turnover and tax observations

Extract class-specific gross and net annual expense ratios, 12b-1 fees, front or
deferred loads and redemption fees separately. `0.25` with `PCT` means 0.25%.
Do not add gross and net ratios, loads or spreads into an invented annual cost.
Prospectus hypothetical cost examples are not expense ratios. Missing disclosures
remain absent; zero needs explicit cited support. Preserve waiver expiration
when disclosed; otherwise say expiration could not be verified. Future waiver
expiry is a contract term, not a future observed measurement.

Record portfolio turnover with its actual fiscal reporting period and source.
It is neither exchange volume nor an inferred flow from holdings changes.
Assets retain their reported class/series scope; do not sum incompatible scopes.

Distributions are historical `USD_PER_SHARE` facts. Preserve ordinary income,
short/long capital gain and return of capital separately. Set `period_end` to the
reported payable/ex date and identify which date it is in notes. Keep record,
ex and payable dates in source context when disclosed. Do not combine unrelated
events or infer distributions from NAV changes. An empty history means unavailable,
not tax-free. In-kind redemption is a possibility only when fund documents support
it; it does not guarantee capital gain avoidance.

Do not compute personal tax bills, after-tax returns, basis, predicted distributions
or a universal tax-efficiency score. Lower costs or historical distributions cannot
establish suitability or wash-sale safety.

Primary background references, checked October 10, 2026:

- [SEC fee bulletin](https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-bulletins/mutual-fund-and-etf-fees-and-expenses-investor-bulletin)
  explains distinct operating and shareholder costs and share-class differences.
- [SEC distribution bulletin](https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-bulletins/fund-distributions-investor-bulletin)
  describes distribution categories. Use actual fund records for numerical facts.
