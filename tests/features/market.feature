Feature: Complete available structured fund data
  Scenario: Available holdings retain provenance and normalize identifiers
    Given synthetic provider responses
    When I retrieve AAA holdings
    Then all available holdings have normalized identities and weights
    And the response states source and observation dates
  Scenario: Partial holdings remain partial
    Given synthetic provider responses
    When I retrieve PART holdings
    Then partial coverage is explicitly warned
  Scenario: Stale holdings are refreshed
    Given synthetic provider responses
    And expired cached holdings
    When I retrieve AAA holdings
    Then refreshed holdings replace the expired cache
  Scenario: Provider failure never silently returns stale data
    Given expired holdings and an unavailable provider
    When I retrieve holdings from the unavailable provider
    Then external unavailability is reported
  Scenario: Fund comparison calculates overlap active share and correlation
    Given synthetic provider responses
    When I compare AAA and BBB
    Then overlap and active share reflect normalized weights
    And historical return correlation and expense ratios are supplied
  Scenario: Missing holdings are unavailable
    Given synthetic provider responses
    When I retrieve MISSING holdings
    Then missing holdings have unavailable status
  Scenario: Historical gaps identify the usable period
    Given synthetic provider responses
    When I retrieve AAA history
    Then adjusted history identifies its usable period and gap warnings
  Scenario: Strong security aliases bridge different provider identities
    Given synthetic provider responses
    When I compare CUSIPA and CUSIPB
    Then ISIN and CUSIP aliases identify the same shared security
  Scenario: Security metadata retains its own freshness policy
    Given synthetic provider responses
    When I retrieve security metadata for AAPL
    Then the profile supplies classifications with a seven day cache policy
  Scenario: Public quotes retain provenance without changing ledger prices
    Given synthetic provider responses
    When I retrieve an AAPL quote
    Then the quote has a fifteen minute cache and source timestamps
    And the public quote leaves portfolio state unchanged
  Scenario: Quotes older than fifteen minutes are refreshed
    Given synthetic provider responses
    And a sixteen minute old AAPL quote
    When I retrieve an AAPL quote
    Then the expired quote price is replaced
