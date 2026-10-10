Feature: Saved earnings facts and conservative comparisons
  Scenario: Summaries keep accounting bases separate
    Given saved fictional quarterly earnings with GAAP and adjusted metrics
    When the saved earnings summary is requested
    Then exact values bases and source references remain separate
    And unavailable growth is null with a warning

  Scenario: Compatible year-over-year quarters compare exactly
    Given two comparable fictional second-quarter earnings runs
    When saved earnings runs are compared
    Then absolute and percentage changes use the saved exact values

  Scenario: Compact listing never reads evidence packages
    Given saved fictional quarterly earnings with GAAP and adjusted metrics
    When earnings runs matching the ticker are listed
    Then only matching compact metadata is returned without package reads

  Scenario: Historical evidence retains skill and import provenance
    Given saved fictional quarterly earnings with GAAP and adjusted metrics
    When the historical earnings package is shown
    Then its original facts and recorded skill identity are reproduced
