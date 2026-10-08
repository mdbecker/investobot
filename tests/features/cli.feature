Feature: One machine-readable investment executable
  Scenario: Invalid snapshot input has documented error semantics
    When I invoke apply with an invalid snapshot
    Then the command exits one with JSON on stderr
  Scenario: Missing external credentials fail conservatively
    When I request fund holdings without credentials
    Then the command exits two with JSON on stderr
  Scenario: Tax analysis is available as JSON
    Given an empty local ledger
    When I request tax lots
    Then the command emits valid JSON on stdout
  Scenario: Malformed command syntax uses input error JSON
    When I invoke an unknown subcommand
    Then the command exits one with JSON on stderr
