Feature: No-write household scenarios and historical risk
  Scenario: Taxable fund replacement changes concentration without touching state
    Given a household with a taxable loss fund and known cash
    When I simulate a sale and replacement purchase
    Then taxable losses and selected lots are reported
    And the Apple exposure decreases
    And the original ledger bytes remain unchanged
  Scenario Outline: Impossible trades are rejected
    Given a household with a taxable loss fund and known cash
    When I simulate an impossible "<action>"
    Then the simulation rejects inconsistent state
    Examples:
      | action |
      | BUY |
      | SELL |
      | MOVE_CASH |
  Scenario: Retirement rebalance has no realized taxable gain
    Given a household with a retirement fund and known cash
    When I simulate a sale and replacement purchase
    Then no taxable gain is reported
  Scenario: Cash transfers preserve household value
    Given a household with a taxable loss fund and known cash
    When I simulate a cash transfer to another account
    Then household value is unchanged and account cash changes
  Scenario: Historical risk reports exact usable dates and drawdown
    Given a household with a taxable loss fund and known cash
    When I compute historical portfolio risk
    Then the maximum drawdown includes the known cash weight
    And pairwise correlations and concentration are reported
