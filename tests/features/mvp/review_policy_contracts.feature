Feature: Proposed taxable sales use approved evidence for the actual trade date
  Scenario Outline: Invalid annual evidence cannot authorize a taxable sale
    Given a reviewed fictional household with a confirmed September gain
    When the <path> proposal uses <evidence> tax evidence
    Then taxable sales are blocked by <code> while accepted facts remain intact

    Examples:
      | path      | evidence          | code                         |
      | rebalance | wrong-year        | TAX_BUDGET_YEAR_MISMATCH     |
      | harvest   | wrong-year        | TAX_BUDGET_YEAR_MISMATCH     |
      | rebalance | stale             | STALE_TAX_HISTORY_ATTESTATION |
      | harvest   | stale             | STALE_TAX_HISTORY_ATTESTATION |
      | rebalance | stale-without-sales | STALE_TAX_HISTORY_ATTESTATION |
      | harvest   | stale-without-sales | STALE_TAX_HISTORY_ATTESTATION |
      | rebalance | future            | FUTURE_TAX_HISTORY_ATTESTATION |
      | harvest   | future            | FUTURE_TAX_HISTORY_ATTESTATION |
      | rebalance | mixed-environment | MIXED_DATA_ENVIRONMENT       |
      | harvest   | mixed-environment | MIXED_DATA_ENVIRONMENT       |

  Scenario Outline: Current matching annual evidence retains confirmed positive tax cost
    Given a reviewed fictional household with a confirmed September gain
    When the <path> proposal uses matching tax evidence
    Then the matching evidence retains eight dollars of consumption and permits a sale

    Examples:
      | path      |
      | rebalance |
      | harvest   |
