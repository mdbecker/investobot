# Conservative comparison rules

Metrics are reported observations only. Preserve source values and original
periods. Allowed monetary measures include revenue, gross profit, operating/net
income, operating cash flow, capital expenditures and disclosed free cash flow.
Do not construct undisclosed free cash flow or infer equivalent definitions.
`CUSTOMER_COUNT` uses `count`; monetary measures need supported currencies.
`OTHER` needs a specific source-backed definition. Never guess GAAP, IFRS,
non-GAAP, currency, segment equivalence or missing numerical values.

Direct comparison needs matching metric code, definition, unit, accounting
basis, period type, actual start/end dates and scope. Duration observations need
both dates; instant observations have no start. Historical metric dates and their
source publication cannot exceed the researched date. Different fiscal calendars,
currencies, adjusted bases and quarterly/year-to-date measures remain distinct.
There is no FX, inflation, quarterization or market-share model.

Consolidated metrics have no segment or overlap. Segment comparisons require
both observations to reference the same explicit overlap and correspond to its
subject and peer segments. Segment names can differ; similar labels do not prove
business equivalence. A consolidated revenue comparison alone says nothing about
competitive strength within the overlapping market.

Pairs must be unique on both sides. Ambiguous, incompatible or absent pairs
remain `NOT_COMPARABLE`, retaining available original observations and reasons.
Private-company missing revenue is unavailable, never zero.

Investobot computes subject-minus-peer absolute differences for compatible pairs.
Peer-relative percentage differences use a positive peer denominator only;
zero/negative baselines produce null percentages and warnings. Decimal subtraction
preserves precision; division discloses inexact rounding. Do not supply
agent-computed comparative percentages or financial forecasts as reported facts.

The matrix is descriptive. Qualitative interpretations never become computed
facts, investment suitability, scores, rankings, target weights or trade actions.
Citation presence cannot prove truth or actual comparability: inspect original
disclosures and preserve uncertainty.
