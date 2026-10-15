Feature: Compact plan results for coding agents
  Scenario: Listing alternatives returns bounded saved financial summaries
    Given twenty saved alternatives with large synthetic histories
    When the agent lists alternatives
    Then twenty compact summaries preserve saved financial metrics
    And the response is smaller than 128 KiB without detailed financial state
    And alternatives are ordered by newest creation time and stable ID

  Scenario: Comparing alternatives returns bounded saved summaries
    Given twenty saved alternatives with large synthetic histories
    When the agent compares alternatives
    Then twenty compact summaries preserve saved financial metrics
    And the response is smaller than 128 KiB without detailed financial state
    And compatible alternatives disclose matching assumptions without ranking

  Scenario Outline: Incompatible assumptions are explicitly disclosed
    Given twenty saved alternatives with large synthetic histories
    And one alternative has different <assumption>
    When the agent compares alternatives
    Then comparison identifies incompatible <assumption>
    Examples:
      | assumption |
      | prices |
      | tax rates |
      | analysis date |
      | source snapshot |

  Scenario: Full retrieval and reports preserve historical details
    Given a target is ready for synthetic retirement planning
    And its complete plan and historical reports are saved
    When accepted cash changes and summaries are inspected
    Then listed status is stale while generated status is preserved
    And full retrieval retains original assumptions and proposed trades
    And historical report bytes remain identical

  Scenario: Unknown optional summary metrics remain explicit
    Given a saved synthetic plan without optional financial fields
    When the agent lists alternatives
    Then unknown summary values are null and warnings are empty

  Scenario: No saved plans returns an empty list
    Given an empty household
    When the agent lists alternatives
    Then the plans array is empty

  Scenario: Invalid comparison identifiers produce an input error
    Given twenty saved alternatives with large synthetic histories
    When the agent compares a missing identifier
    Then comparison fails with input exit code
