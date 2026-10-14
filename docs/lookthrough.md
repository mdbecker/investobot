# Fund look-through

`lookthrough.exposure` is the single recursive numeric engine shared by household,
research, simulation and viewer reads. [Operational walkthrough](workflows.md)
contains the authoritative commands. Reports preserve source dates, currency,
account/fund paths, cycles/depth limits, known amounts and undisclosed residuals.

Observed constituents need not be registered securities. Their weights remain
visible, with source identity and original paths. Equal tickers or names do not
prove issuer equivalence; only canonical/verified identity allows aggregation.
`unresolved_identity_value` describes represented amounts lacking that identity;
`unknown_exposure_value` describes unrepresented weight. Neither is redistributed.
Weights above one block the observation. Stale or unavailable evidence stays typed.

Omitted cutoff means current UTC reporting date. Pinned immutable observations take
precedence; eligible persisted provider caches support labeled provisional current
exploration only. Explicit historical dates never consume current caches or later
published evidence. Provider retrieval is a separate operation.

Missing valuation/cash gives `total_value: null`, `known_value_subtotal`, and null
coverage ratios. Numeric coverage and evidence quality remain separate.
Research selects only verified issuer rows and retains unresolved/filtered coverage.
No automatic constituent registration, provider call, cache write or source certification.
