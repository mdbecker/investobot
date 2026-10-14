Feature: One policy governed planner
  Scenario: Synthetic exploration buys with cash and writes nothing
    Given a complete synthetic account with 200 cash and an approved target
    When an unapproved synthetic contribution is previewed twice
    Then each preview buys one share for 100 with a fee of 5 and preserves a cash floor of 50
    And no plans or accepted financial facts are written

  Scenario: Approved policy produces a saved immutable hypothetical plan
    Given a complete synthetic account with 200 cash and an approved target
    When a contribution is proposed using a saved approved policy
    Then the saved plan contains complete executable details and accepted facts remain unchanged

  Scenario: Real scenarios require policy approval
    Given a complete real account with 200 cash and an approved target
    When an unapproved synthetic contribution is previewed twice
    Then the proposal is blocked for missing policy approval without writes

  Scenario: Unknown fees remain a review gate
    Given a complete synthetic account with 200 cash and an approved target
    And execution fees are unknown
    When an unapproved synthetic contribution is previewed twice
    Then the fee uncertainty prevents execution review approval

  Scenario: Stale price assumptions cannot fund a trade
    Given a complete synthetic account with 200 cash and an approved target
    And the sourced price is stale
    When an unapproved synthetic contribution is previewed twice
    Then no trade is proposed and stale prices are reported

  Scenario: Rebalance consumes fee adjusted positive tax dollars
    Given a complete taxable portfolio with two verified specific lots and a 34.6 tax allowance
    When the overweight stock is proposed for sale using an approved policy
    Then the sale gain is 115 and conservative tax consumption is 34.6
    And accepted lots and balances remain unchanged

  Scenario: Embedded targets cannot create accepted target versions
    Given a complete synthetic account with 200 cash and an approved target
    When the public proposal command receives an embedded unsaved target
    Then it rejects the target without creating a version or plan

  Scenario: Public preview accepts saved targets without writes
    Given a complete synthetic account with 200 cash and an approved target
    When the public preview command receives a saved target and synthetic assumptions
    Then the public preview reports executable details without saving

  Scenario: Harvest and rebalance agree on the same fee adjusted loss sale
    Given a complete taxable portfolio with two verified loss lots and a reviewed replacement
    When approved harvest and rebalance estimate the same loss sale
    Then both estimate a 35 loss and zero positive tax consumption while retaining wash review
