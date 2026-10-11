# Known-bond analysis

`invest bond analyze` evaluates supplied plain fixed-rate terms using SciPy.
It does not discover bonds, retrieve prices, or place orders.
Pass JSON with `face_value`, `coupon` (annual decimal fraction), `issue_date`,
`maturity`, `settlement_date` (all ISO dates), `frequency` (1, 2, 4, or 12),
and `clean_price` (per 100 face value). Unknown required terms yield
`INSUFFICIENT_DATA` without invented metrics. Invalid values are input errors.

Example terms:

```json
{"face_value":"1000","coupon":"0.05","issue_date":"2021-01-15","maturity":"2031-01-15","settlement_date":"2026-10-08","frequency":2,"clean_price":"98","day_count":"ACTUAL_ACTUAL_BOND"}
```

The result contains yield to maturity, accrued interest for the supplied face
value, dirty price per 100, dirty value, modified duration, and convexity.
SciPy solves the discounted regular cash-flow price equation for the nominal
compounded annual yield. Duration and convexity use its analytical first and
second price derivatives. These calculations use floating-point numerical solving;
displayed metrics are decimal
strings with 12 significant digits, rather than exact ledger monetary arithmetic.

Conventions are disclosed in every calculated result: NullCalendar,
unadjusted business dates, a backward regular schedule from maturity to issue,
zero settlement lag because settlement is supplied, compounded annual yields,
and principal redemption at 100. Default day count is Actual/Actual (Bond),
with a warning when omitted. Supported explicit alternatives are
`THIRTY_360_BOND_BASIS` and `ACTUAL_365_FIXED`.
Verify these conventions against the actual security. This MVP does not support
floating coupons, irregular schedules, ex-coupon terms, inflation adjustments,
or instrument-specific Treasury/bank holiday calendars.

Explicit `instrument_type` values `CALLABLE`, `CONVERTIBLE` and `STRUCTURED`
return `UNAVAILABLE` with typed issues and no metrics. Nonempty `call_schedule`,
conversion terms or structured-payoff terms also return that outcome when the
type label is omitted. Embedded optionality cannot become a plain bond by leaving
out its label. Yield to worst is not calculated. An absent/empty call schedule
does not establish that original instrument terms were independently verified.
