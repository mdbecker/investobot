Feature: Imported cash and lots remain trustworthy
  Scenario: Repeated cash balance tables cannot double available cash
    Given a page repeating the same cash row in two tables
    When I normalize the hardened import
    Then the contradictory source is rejected

  Scenario Outline: Complete coverage cannot hide omitted financial data
    Given a complete page containing <problem>
    When I normalize the hardened import
    Then the contradictory source is rejected
    Examples:
      | problem                 |
      | malformed cash value    |
      | invalid acquisition date |
      | missing lot basis       |
      | missing acquisition date |

  Scenario: Ambiguous duplicated columns cannot replace a reported value
    Given a page with two market value columns
    When I normalize the hardened import
    Then the contradictory source is rejected

  Scenario: A valuation refresh preserves the same known tax lot identity
    Given a known lot imported at two valuations
    When I compare the normalized lot identities
    Then the lot identity is unchanged
