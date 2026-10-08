Feature: Local inspection and explicit portfolio acceptance
  Scenario: Inspect an empty ledger without fabricated balances
    Given a local inspection server with an empty ledger
    When I inspect the portfolio summary
    Then the summary reports zero and the page provides an import workflow

  Scenario: Preview, reconcile, and explicitly accept a page
    Given a local inspection server with an empty ledger
    When I preview a synthetic account page
    Then the normalized preview is available and the ledger is unchanged
    When I reconcile and explicitly apply the preview
    Then the portfolio summary reflects the accepted snapshot
    And the raw page has not been stored

  Scenario: Reject cross-origin mutations
    Given a local inspection server with an empty ledger
    When a foreign origin posts an account page
    Then the request is rejected without importing it

  Scenario: Reject oversized input
    Given a local inspection server with an empty ledger
    When an oversized body is submitted
    Then the request is rejected before parsing
