Feature: Conservative household tax and exposure accuracy
  Scenario Outline: Critical lot and source gaps prevent fabricated sale gains
    Given a dated taxable household with two complete lots
    And tax data has "<gap>"
    When the household sale is estimated
    Then the sale has insufficient data and null gains
    Examples:
      | gap                 |
      | unresolved lots     |
      | excess lot quantity |
      | missing date        |
      | unknown source date |
      | missing tax status  |

  Scenario: Specific mixed-term sales allocate exact fees across lots
    Given a dated taxable household with two complete lots
    When both specified lots are sold with six dollars of fees
    Then short term gain is ninety eight and long term loss is one hundred four
    And the estimate discloses fees and conservative tax assumptions

  Scenario: Incomplete household history is disclosed independently from known lot gains
    Given a dated taxable household with two complete lots
    And tax data has "incomplete history"
    When the household sale is estimated
    Then known gains remain available with incomplete household history

  Scenario: An IRA purchase with an explicit identifier bridge conflicts with a taxable loss
    Given a dated taxable household with two complete lots
    And an IRA purchase uses a bridged canonical security
    When the household sale is estimated
    Then the IRA appears in potential wash sale conflicts

  Scenario: Legacy valuation freshness is disclosed without inventing a source date
    Given a dated taxable household with two complete lots
    And tax data has "legacy source date"
    When the household sale is estimated
    Then legacy freshness is explicitly unknown

  Scenario: A dated older valuation discloses freshness limitations
    Given a dated taxable household with two complete lots
    And tax data has "older source date"
    When the household sale is estimated
    Then older source data is disclosed

  Scenario: Tax-free sales do not create taxable gains
    Given a dated taxable household with two complete lots
    And tax data has "tax free account"
    When the household sale is estimated
    Then taxable short and long term gains are zero

  Scenario: Historical risk aligns and sorts common dates with a cash assumption
    Given unsorted adjusted history and fifty percent household cash
    When hypothetical historical risk is computed
    Then maximum drawdown is five percent with zero cash return disclosed
