# Known-bond analysis

`invest bond analyze` evaluates supplied fixed-rate terms using QuantLib.
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
QuantLib uses floating-point numerical solving; displayed metrics are decimal
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

Optional `call_schedule` is a list of `{"date":"2028-01-15","price":"100"}`
redemption scenarios. The minimum of maturity yield and all supplied valid call
yields is returned as yield to worst. Calls on regular coupon dates preserve
the supplied original coupon schedule. Off-coupon calls require additional
stub/accrued-redemption terms and produce a warning with no yield to worst,
rather than a guessed cash flow. Absent call schedules produce an explicit
warning; they are not interpreted as proof that a bond is non-callable.
An explicitly empty schedule permits maturity-only yield to worst, with the
same warning that schedule completeness must be verified by the user.
