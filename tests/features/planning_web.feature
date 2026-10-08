Feature: Local dashboard uses authoritative domain calculations
  Scenario: Overview displays accepted state and active target differences
    Given a local server with a dated synthetic retirement portfolio
    When a target is saved and activated through the local API
    Then overview values and target differences match the CLI domain
  Scenario: Saved plans show trades taxes stale status and reports
    Given a local server with a dated synthetic retirement portfolio
    When a plan is generated through the local API
    Then saved trades and tax values match the CLI domain
    And a report can be downloaded without changing actual state
    When confirmed activity changes the portfolio
    Then the API visibly identifies the plan as stale
  Scenario: Prompt copy and user edits preserve bundled defaults
    Given a local server with a dated synthetic retirement portfolio
    When a user reads creates and edits a prompt through the API
    Then the full prompt text is returned and bundled defaults remain recoverable
  Scenario: Prompt paths and agent execution requests are rejected
    Given a local server with a dated synthetic retirement portfolio
    When invalid prompt paths and execution requests are posted
    Then no prompt or actual state changes occur
  Scenario: Planning mutations retain same origin protection
    Given a local server with a dated synthetic retirement portfolio
    When a target save comes from another origin
    Then the write is rejected
