Feature: An agent discovers and safely imports through the CLI
  Scenario: Tools list is available as JSON
    When the agent invokes tools list
    Then the JSON catalogue includes portfolio.simulate
  Scenario: Tools describe is available as JSON
    When the agent describes portfolio.simulate through the CLI
    Then the JSON contract identifies simulation as read only
  Scenario: Explicit complete import preserves source date
    Given a synthetic saved holdings page
    When the agent imports with a known date and confirmed complete coverage
    Then the normalized snapshot confirms source date and both completeness fields
