Feature: Conservative account imports
  Scenario: A table with lot data establishes exact basis
    Given a synthetic lot table
    When the lot table is parsed
    Then acquisition dates and basis are preserved
  Scenario: Invalid quantities are rejected before state mutation
    Given a normalized snapshot with a negative quantity
    When the snapshot is applied
    Then the application rejects it and leaves no accounts
  Scenario: Unknown asset type remains unsupported
    Given a synthetic derivative position table
    When the derivative table is parsed
    Then the asset is OTHER with a warning
  Scenario: Account application preserves recorded transaction history
    Given a normalized snapshot with a known account
    When I record a purchase and apply a later snapshot
    Then the activity history remains available
  Scenario: Lot quantities cannot exceed the imported position
    Given a normalized snapshot with excess lot quantities
    When the snapshot is applied
    Then the application rejects it and leaves no accounts
  Scenario: Unknown cash does not permit an inferred cash balance
    Given a page without a cash table
    When I apply that page and preview a buy
    Then the preview fails for unknown cash
