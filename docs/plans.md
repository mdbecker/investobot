# Human-reviewed plans and reports

Follow [the operational walkthrough](workflows.md) for explicit target, policy,
preview, proposal and export steps. `planning.propose` is the only action generator.
Synthetic unapproved preview saves nothing; approved proposals save hypothetical
plans using previously saved targets and immutable policy IDs. No accepted balances,
marks or lots change. Contributions-only never sells; rebalance uses account cash
first on any valid date. Permissions, fees, increments, floors and freshness apply.

Specific-lot sale estimates share one Decimal calculation with conditional harvest:
remaining adjusted basis, quantity-allocated fees with exact final residue, term
gains and conservative positive estimated tax cost. Losses do not replenish annual
allowance. Confirmed executed facts use their immutable recorded allocations.
No guaranteed tax savings or wash-sale legality is claimed.

Propose/show return full action detail. List/compare use compact saved summaries,
show current staleness separately, disclose incompatible assumptions and never rank
investment quality. Backtest comparison creates no target or transition plan.

Report exports contain saved account actions, units, prices, fees, selected lot IDs,
source/policy/manifest references and limitations. JSON roundtrips full immutable
content; Markdown is intended for human review. Exports are reproducible and do not
recompute with new prices. Review current staleness before manually executing trades.
