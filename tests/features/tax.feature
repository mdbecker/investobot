Feature: Deterministic tax analysis of known household state
  Scenario Outline: Sale methods select known lots and classify gain
    Given a taxable portfolio with an old high basis lot and a recent low basis lot
    When a sale is analyzed using "<method>"
    Then the selected first lot is "<lot>" and the gain is "<gain>"
    Examples:
      | method   | lot | gain |
      | FIFO     | old | -100 |
      | LIFO     | new | 200  |
      | HIFO     | old | -100 |
      | SPECIFIC | new | 200  |
      | MIN_TAX  | old | -100 |

  Scenario: Mixed sale separates short and long term gains
    Given a taxable portfolio with an old high basis lot and a recent low basis lot
    When fifteen shares are sold at one hundred dollars
    Then long term loss is one hundred and short term gain is one hundred

  Scenario Outline: Household acquisition conflicts are conservative
    Given a taxable portfolio with an old high basis lot and a recent low basis lot
    And household purchase history is "<history>"
    When a loss sale is analyzed
    Then wash sale status is "<status>"
    Examples:
      | history       | status            |
      | taxable       | POTENTIAL_CONFLICT|
      | IRA           | POTENTIAL_CONFLICT|
      | future        | POTENTIAL_CONFLICT|
      | complete      | NO_KNOWN_CONFLICT |
      | incomplete    | INSUFFICIENT_DATA |

  Scenario: Missing lot basis never becomes a guessed gain
    Given a taxable portfolio with an old high basis lot and a recent low basis lot
    And the available lot basis is missing
    When a loss sale is analyzed
    Then tax analysis reports insufficient data

  Scenario: Missing lot detail never becomes guessed FIFO basis
    Given a taxable portfolio with an old high basis lot and a recent low basis lot
    And the lot detail is missing
    When a loss sale is analyzed
    Then tax analysis reports insufficient data

  Scenario Outline: Optional rates control tax estimates
    Given a taxable portfolio with an old high basis lot and a recent low basis lot
    When the sale is analyzed with "<rates>" tax rates
    Then the tax estimate is "<estimate>"
    Examples:
      | rates      | estimate |
      | absent     | none     |
      | configured | -20      |

  Scenario: Remaining lot basis and harvesting candidates are calculated without mutation
    Given a taxable portfolio with an old high basis lot and a recent low basis lot
    When lots and harvesting candidates are inspected
    Then the old lot has one hundred dollars of unrealized loss and is a harvesting candidate

  Scenario: Selling beyond the known position is rejected
    Given a taxable portfolio with an old high basis lot and a recent low basis lot
    When thirty shares are proposed for sale
    Then the sale is rejected as inconsistent state

  Scenario: A one year anniversary remains short term
    Given a taxable portfolio with an old high basis lot and a recent low basis lot
    When the old lot is inspected on its acquisition anniversary
    Then its holding period is short term
