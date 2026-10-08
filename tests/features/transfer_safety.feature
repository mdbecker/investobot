Feature: Hypothetical transfers respect account tax boundaries
  Scenario: Cash cannot freely move into a retirement account
    Given loaded taxable and tax free accounts with cash
    When a cross tax treatment cash movement is simulated
    Then the simulation requires manual review without changing actual state
