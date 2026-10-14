Feature: Defensible household performance calendar dates
  Actual returns combine complete dated account evidence only when chronology permits it.

  Scenario: Minute separated valuations form complete household endpoints
    Given two complete synthetic accounts observed one minute apart on each endpoint
    When actual household performance is requested twice
    Then the household return is exactly ten percent on three thousand dollars
    And reporting preserves every accepted fact

  Scenario: Account reporting uses only its own dated valuations
    Given two complete synthetic accounts observed one minute apart on each endpoint
    When actual performance for account alpha is requested
    Then the account return is exactly ten percent
    And reporting preserves every accepted fact

  Scenario Outline: Same day evidence cannot invent a common flow boundary
    Given household observations with <evidence> around an external deposit
    When actual household performance is requested twice
    Then TWR is unavailable with <issue>
    And reporting preserves every accepted fact
    Examples:
      | evidence             | issue                           |
      | opposite timestamps  | AMBIGUOUS_FLOW_BOUNDARY          |
      | date only timestamps | AMBIGUOUS_FLOW_BOUNDARY          |
      | missing event time   | AMBIGUOUS_FLOW_BOUNDARY          |

  Scenario: Explicit common after flow observations support exact return
    Given household observations with common after timestamps around an external deposit
    When actual household performance is requested twice
    Then the household return excludes the one hundred dollar deposit
    And reporting preserves every accepted fact

  Scenario: Conflicting same day valuations require review
    Given two complete synthetic accounts with conflicting same date valuations
    When actual household performance is requested twice
    Then TWR is unavailable with AMBIGUOUS_VALUATION_CHECKPOINT
    And reporting preserves every accepted fact

  Scenario: Incomplete account coverage remains unavailable
    Given two synthetic accounts with unknown cash in one endpoint
    When actual household performance is requested twice
    Then TWR is unavailable with PARTIAL_VALUATION_CHECKPOINT
    And reporting preserves every accepted fact
