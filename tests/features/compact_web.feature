Feature: Compact inspection planning responses
  Scenario: Generating a plan exposes the shared compact summary
    Given a synthetic inspection planning portfolio
    When a plan is generated through the inspection boundary
    Then generation returns only the shared compact plan summary

  Scenario: Listing and comparing retain compact financial summaries
    Given a synthetic inspection planning portfolio
    When two alternatives are generated and inspected
    Then inspection lists and compares the shared compact summaries

  Scenario: Explicit inspection retrieval preserves complete saved details
    Given a synthetic inspection planning portfolio
    When a plan is generated through the inspection boundary
    Then explicit inspection retrieval preserves full details and reports
