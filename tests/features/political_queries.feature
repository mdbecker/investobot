Feature: Deterministic political research inspection
  Scenario: Summarize counted donations and linked refunds without inferred affiliations
    Given fictional immutable political research with a donation refund and memo
    When the research summary is requested
    Then the PAC totals net the linked refund and preserve transaction evidence
    And no donor political affiliation is inferred

  Scenario: Inspect an accepted package without changing its evidence
    Given fictional immutable political research with a donation refund and memo
    When the full research package is requested
    Then the accepted package is reproduced with its import provenance

  Scenario: List research without loading evidence payloads
    Given fictional immutable political research with a donation refund and memo
    When matching research runs are listed
    Then only compact matching run metadata is read
