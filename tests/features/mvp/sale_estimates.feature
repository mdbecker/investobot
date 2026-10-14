Feature: Fee aware specific lot sale estimates
  Scenario: Fees reduce both term gains and conservative positive tax cost
    Given two specific lots with remaining adjusted bases 240 and 140
    When five shares are estimated at 100 with a sale fee of 5
    Then the long term gain is 57 and short term gain is 58
    And the positive estimated tax cost is 34.6 without changing financial facts

  Scenario: Losses cannot replenish positive gain allowance
    Given two specific lots including a long term loss
    When five shares are estimated at 100 with a sale fee of 5
    Then the positive estimated tax cost is 23.2 despite the loss

  Scenario: Final fee residue is retained exactly
    Given three one share specific lots
    When three shares are estimated with a fee of 1
    Then the allocated fees total exactly 1

  Scenario: Unknown adjusted basis blocks an estimate
    Given two specific lots with remaining adjusted bases 240 and 140
    And the second lot has unknown basis
    When five shares are estimated at 100 with a sale fee of 5
    Then the sale reports insufficient data without invented gains
