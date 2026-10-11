# Actual portfolio performance

Actual performance uses explicit complete dated valuation checkpoints and an
attested external cash-flow history. Missing evidence returns typed unavailable
outcomes rather than zero returns. This calculation never treats current weights
or hypothetical backtests as historical account performance.

TWR links complete intervals around each external flow. A boundary mark must
explicitly say `BEFORE_FLOW` or `AFTER_FLOW`; the paired balance follows from that
mark and the exact cash flow. Two supplied marks must agree with the cash movement.
Missing or ambiguous boundary ordering blocks TWR; no interpolation is performed.
CAGR annualizes supported linked TWR using actual calendar days and 365.25 days per
year. A supported complete total loss produces -100%.

XIRR uses investor signs: deposits negative, withdrawals positive and terminal
value positive. The equation uses actual day differences divided by 365.25. Root
isolation uses disclosed floating-point arithmetic over log rates [-700,700].
Missing or multiple roots leave the rate null. Explicit `investor_cash_flows` may
supply already reviewed investor-sign flows. They are separate from portfolio-sign
external cash movements.

Paired household transfers cancel only with explicit links, distinct accounts,
matching dates and exact opposite amounts. Account-level transfers remain external.
Retained dividends, interest, purchases, sales, fees and reinvestment are not
external contributions. Their effects must already be represented in complete
checkpoint valuations; they are never added twice. Default results are net of fees.
A gross-fee report requires separately sourced adjusted valuation evidence.

The pure `calculate(payload)` function accepts reporting dates, scope, provenance,
checkpoints, cash flows and explicit coverage. Ledger extraction and CLI routing
supply these facts; the function neither discovers completeness nor changes the
ledger, valuations, caches or saved plans.
