Feature: Deterministic earnings CLI
  Scenario: Validation and preview do not create a selected database
    Given a fictional earnings file and no selected database
    When earnings are validated previewed and listed
    Then stdout is JSON and no database file is created
  Scenario: Human acceptance retains independently comparable historical earnings
    Given a fictional earnings file and no selected database
    When two source-backed annual comparison periods are confirmed
    Then saved history summaries and compatible comparisons are discoverable
