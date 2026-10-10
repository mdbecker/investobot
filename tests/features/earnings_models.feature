Feature: Accurate source-backed earnings research
  Scenario: Accept a reported quarterly revenue observation
    Given a synthetic source-backed earnings package
    When earnings research is validated
    Then its exact values and source periods are preserved

  Scenario: Prevent year-to-date cash-flow confusion
    Given a synthetic source-backed earnings package
    When a nine-month cash-flow fact is labeled as third-quarter only
    Then the unsupported quarterly representation is rejected
