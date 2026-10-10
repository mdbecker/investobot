Feature: Immutable isolated political research
  Scenario: Preview and accept corporate research without portfolio changes
    Given a fictional corporate research package
    When research import is previewed
    Then no research is persisted
    When research import is confirmed twice
    Then one immutable run is saved without financial changes
  Scenario: Discover research commands and validation schema
    When political tool contracts are inspected
    Then import is explicitly scoped to research and has the authoritative schema
