Feature: Reproducible human-reviewed plan reports
  Scenario: Markdown exports preserve all persisted planning inputs and calculations
    Given an immutable synthetic trade plan with unresolved tax information
    When its Markdown report is exported
    Then the report contains account trades lots allocations cash assumptions and warnings
    And export confirmation hashes exactly the saved report bytes
    And the original plan remains unchanged

  Scenario: JSON exports roundtrip the complete persisted plan
    Given an immutable synthetic trade plan with unresolved tax information
    When its JSON report is exported
    Then the report JSON exactly equals the persisted plan
    And export confirmation hashes exactly the saved report bytes

  Scenario: Unsupported formats fail without creating a report
    Given an immutable synthetic trade plan with unresolved tax information
    When a PDF report is requested
    Then the report request fails as invalid input without a file

  Scenario: Unknown financial values remain explicitly unknown
    Given an immutable synthetic trade plan with unresolved tax information
    When its Markdown report is rendered
    Then unknown tax effects are disclosed without guessed savings
