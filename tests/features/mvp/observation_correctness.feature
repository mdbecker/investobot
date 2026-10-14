Feature: Canonical observation and valuation safety
  Scenario: An execution price does not invent a valuation mark
    Given accepted fictional holdings and cash
    When a purchase of two unmarked shares is confirmed
    Then summary reports partial valuation with the known subtotal

  Scenario: A verified identifier survives a ticker change
    Given accepted fictional holdings and cash
    When the later complete snapshot changes the ticker with the same ISIN
    Then reconciliation shows metadata instead of liquidation and acceptance retains identity

  Scenario: Provisional parser issues survive acceptance review
    Given accepted fictional holdings and cash
    When a partial snapshot has provisional and unverified lot issues
    Then every typed issue survives and eligible evidence remains explicitly partial

  Scenario: Missing inventory and cash are not zero
    Given accepted fictional holdings and cash
    When a partial snapshot omits positions lots and cash
    Then accepted inventory cash and lots remain and repeat is idempotent

  Scenario: Conflicting identity blocks atomically
    Given accepted fictional holdings and cash
    When a snapshot conflicts with the held strong identity
    Then acceptance is blocked without mutation

  Scenario: Incompatible printed precision blocks acceptance
    Given accepted fictional holdings and cash
    When source values exceed their printed precision tolerance
    Then acceptance is blocked without mutation
