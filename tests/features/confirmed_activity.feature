Feature: Confirmed activity preserves financial truth
  Scenario: Explicit partial sale consumes exactly the executed lot
    Given a dated taxable position with two lots
    When a partial sale selects the newer lot
    Then only the newer lot decreases and remaining valuation uses the accepted market price
  Scenario: Unknown executed lot selection remains unresolved
    Given a dated taxable position with two lots
    When a confirmed sale has no lot allocations
    Then shares and cash update but lots remain unresolved
  Scenario: Repeated activity ID is idempotent
    Given a dated taxable position with two lots
    When the same confirmed purchase is recorded twice
    Then only one purchase changes shares and cash
  Scenario: Conflicting activity ID is rejected atomically
    Given a dated taxable position with two lots
    When an existing activity ID is reused with different content
    Then the activity conflict leaves state unchanged
  Scenario: Buy execution price is distinct from market valuation
    Given a dated taxable position with two lots
    When a purchase with fees executes above market price
    Then basis includes fees and market valuation preserves the accepted price
  Scenario: Confirmed activities require a stable identifier
    Given a dated taxable position with two lots
    When a purchase is confirmed without an activity ID
    Then the activity conflict leaves state unchanged
  Scenario: Incorrect lot allocations fail atomically
    Given a dated taxable position with two lots
    When sale allocations do not equal sold shares
    Then the activity conflict leaves state unchanged
  Scenario: Cross account transfers require classification
    Given a dated taxable position with two lots
    When an unclassified security transfer is confirmed
    Then the activity conflict leaves state unchanged
