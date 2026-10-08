# Household target portfolios

Targets describe desired household security allocations independently of accepted
holdings. Saving, editing, activating and archiving targets never places trades
or changes actual positions, cash or lots. `target diff` reports allocation drift;
it does not generate trade instructions.

Discover commands with `invest tools describe target.save`. All examples below
run with `docker compose run --rm app invest ...`. Save JSON outside version
control if it contains private account information.

```json
{
  "name": "Balanced candidate",
  "description": "An allocation to compare with other candidates",
  "target_allocations": {
    "CANONICAL_EQUITY_SECURITY_ID": "0.60",
    "CANONICAL_BOND_FUND_SECURITY_ID": "0.35",
    "CASH": "0.05"
  },
  "planning_constraints": {
    "eligible_accounts": ["ira", "taxable"],
    "permitted_securities": {
      "ira": ["CANONICAL_EQUITY_SECURITY_ID", "CANONICAL_BOND_FUND_SECURITY_ID"],
      "taxable": ["CANONICAL_EQUITY_SECURITY_ID", "CANONICAL_BOND_FUND_SECURITY_ID"]
    },
    "cash_minimums": {"ira": "0", "taxable": "500"},
    "short_term_gain_budget": "0",
    "long_term_gain_budget": "5000",
    "target_tolerance": "0.01"
  }
}
```

Replace placeholders with registered canonical security IDs from the portfolio's
accepted positions or registered security catalogue. Ticker strings alone are
not target identities. `CASH` is reserved for household cash. Allocations are
fractional Decimal weights between zero and one; they must total one within the
explicit tolerance `0.000001`. Class labels such as "growth" cannot replace
actual investable securities. Different household currencies cannot be summed
for target differences without a supported FX model.

Use `target save FILE`, `target list`, and `target show TARGET_ID`. To edit, provide
the existing `id` in a complete new JSON payload and save again. Every edit creates
a new immutable version; `target show TARGET_ID --version 1` retrieves historical
inputs. Saving without an ID creates another candidate. An unknown supplied ID
is rejected rather than silently creating a target.

New targets default to `DRAFT`. `target activate TARGET_ID` explicitly selects
one active target and returns the prior active target to draft. A supplied
`status: "ACTIVE"` explicitly activates the saved version in the same atomic
operation. `target archive TARGET_ID` changes current status without deleting
historical inputs or saved plans. Activation/archiving do not rewrite historical
version rows; current status is overlaid when displaying the latest version.

`target diff TARGET_ID` aggregates accepted position values by canonical security
ID and includes cash. Dollar and weight differences are target minus current:
a positive difference means the target wants more of the security. It uses
accepted valuation marks, not fetched quotes. Unknown cash warnings remain
visible; a zero household value cannot establish meaningful current weights.

Account eligibility must be explicit. Empty eligibility permits no planning.
An omitted account's permitted-securities list means unknown eligibility, not
unrestricted access. A permitted list may be empty to prohibit purchases.
Unregistered accounts, investments and excluded position IDs are rejected.
`excluded_positions` uses accepted position IDs (`account_id:security_id`);
`trade_increments` maps account IDs to canonical security IDs and positive share
increments. Known cash is required when specifying an account cash minimum.

Constraints also include separate ST/LT gain budgets, target tolerance and
`price_max_age_days` (default one). An omitted tax budget is distinct from zero.
Restricted retirement plans must name only permitted investments. Do not infer
fractional trading availability: the planner uses whole-share defaults for stocks
and ETFs unless an increment is explicitly configured. See persisted plans and
reports for infeasible constraints, remaining drift and required human review.
