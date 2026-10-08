Feature: Tax prerequisites respect account treatment and missing historical fields
  Scenario: A lot without an acquisition date key yields insufficient data safely
    Given a taxable holding whose lot has no acquisition date field
    When five shares are analyzed for a loss sale
    Then tax analysis reports insufficient data without inventing gains
    And missing purchase dates are disclosed in wash-sale warnings

  Scenario: Tax-free account sales do not require taxable lot inventory
    Given an IRA holding without lots and incomplete household history
    When five shares are analyzed for a loss sale
    Then the sale is non-taxable with lot inventory not required
    And no bogus unresolved-basis warning is reported
    And actual source freshness and household history limitations remain disclosed
