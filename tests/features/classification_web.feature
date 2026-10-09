Feature: Classification suggestions in local inspection
  Scenario: Reconciliation exposes reviewed classification guidance
    Given an inspection ledger holds an OTHER classified security
    When an ETF observation is reconciled through the local API
    Then the API identifies the canonical security and suggested ETF classification
    And the API explains the explicit classification correction
    And the inspection interface displays structured classification guidance

  Scenario: Accepted observations do not bypass classification review
    Given an inspection ledger holds an OTHER classified security
    When the ETF observation is explicitly accepted through the local API
    Then accepted holdings retain the canonical OTHER classification
