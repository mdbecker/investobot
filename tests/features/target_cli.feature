Feature: Persistent targets are available to the external agent
  Scenario: Target commands support stdin and preserve actual holdings
    Given a synthetic accepted investment and a target input
    When the agent saves lists activates and compares the target through the CLI
    Then all outputs are JSON and actual holdings remain unchanged
  Scenario: Research candidates can be registered without inventing holdings
    When the agent registers a verified synthetic investment
    Then its canonical ID is available with no positions or activities
  Scenario: Version one ledgers require deliberate reset
    Given a version one database with historical portfolio data
    When the updated ledger opens the database
    Then incompatible schema is rejected and historical data remains untouched
