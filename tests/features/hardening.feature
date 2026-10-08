Feature: Exact identity and explicit uncertainty
  Scenario: Security aliases preserve UUID when a ticker changes
    Given a snapshot with a CUSIP identified stock
    When I apply the same CUSIP under a new ticker
    Then the security UUID remains the same
    And its CUSIP is stored
  Scenario: A known manual purchase updates total position basis
    Given a snapshot with a CUSIP identified stock
    When I record a confirmed purchase
    Then the summary includes the new known basis
  Scenario: Unknown cash is disclosed in the summary
    Given a snapshot without known cash
    When I request a summary
    Then a missing cash warning is visible
  Scenario: Security history includes reproducible return statistics
    Given a synthetic market history source
    When I request security history from the CLI
    Then return volatility drawdown and rolling series are supplied
