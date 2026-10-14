Feature: Reproducible saved plans
  Saved financial assumptions and reports survive changes to the live ledger.

  Scenario: A saved plan remains readable after later snapshots
    Given a saved plan based on a dated synthetic portfolio
    When a later snapshot changes the live holdings
    Then the saved plan retains its original inputs and source snapshot identifiers
    And current inspection identifies the saved plan as stale

  Scenario: Historical Markdown export remains identical after ledger changes
    Given a saved plan based on a dated synthetic portfolio
    And its historical Markdown report has been exported
    When a later snapshot changes the live holdings
    Then exporting the persisted plan again produces identical bytes

  Scenario: Alternatives preserve independent assumptions after reopening the database
    Given a saved plan based on a dated synthetic portfolio
    When a second alternative uses a different explicit price assumption
    And the database is closed and reopened
    Then both plans retain their independent prices and original inputs
