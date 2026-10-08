Feature: Structured discovery and portfolio similarity
  Scenario: Equity filters select matching provider candidates
    Given synthetic discovery data
    When I screen technology equities above a market capitalization threshold
    Then only the matching equity is returned with provenance
  Scenario: Fund criteria use structured metadata
    Given synthetic discovery data
    When I search ETFs by expense ratio AUM and issuer
    Then only the qualifying synthetic fund is returned
  Scenario: Unsupported filters are rejected
    Given synthetic discovery data
    When I request a profitability filter unavailable in the provider adapter
    Then the unsupported filter is an input error
  Scenario: Replacement ranking excludes the original and preserves raw metrics
    Given synthetic discovery data
    When I rank ORIGINAL SAME DIFFERENT and UNKNOWN against ORIGINAL
    Then SAME ranks above the high correlation low overlap fund
    And the original fund is excluded
    And unknown metrics remain unavailable
    And the exact tax similarity disclaimer is present
  Scenario: Discovery fails conservatively when FMP is unavailable
    Given a discovery client whose external provider fails
    When I request an equity screen
    Then discovery reports an external data error
  Scenario: Invalid filter values are rejected before external access
    Given synthetic discovery data
    When I screen with a negative price bound
    Then the invalid filter is an input error
