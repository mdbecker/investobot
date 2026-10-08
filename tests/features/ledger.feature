Feature: Explicit local ledger state
  Scenario: Import is private and read only until explicitly applied
    Given a synthetic account page with positions and cash
    When I import the page
    Then the ledger remains empty
    When I explicitly apply the snapshot
    Then the summary contains the imported values
    And repeated reconciliation has no differences
    And the raw page is not persisted
  Scenario: Manual buys require confirmation and preserve activity history
    Given an applied synthetic account
    When I preview a manual buy
    Then cash is unchanged
    When I confirm the manual buy
    Then cash and quantity reflect the buy
  Scenario: A changed snapshot reports differences without inventing trades
    Given an applied synthetic account
    When I reconcile a reduced share quantity
    Then a quantity difference is reported
    And no sale is inferred
