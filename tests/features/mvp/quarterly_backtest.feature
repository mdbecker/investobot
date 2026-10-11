Feature: Historical quarterly policy uses explicit sessions
  Scenario: Rebalance once after qualifying quarter-month drift
    Given two fictional dated total-return series cross a quarterly boundary
    When the quarterly historical policy is simulated
    Then only the first qualifying March session rebalances and facts remain unchanged
