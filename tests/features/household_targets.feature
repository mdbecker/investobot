Feature: Household targets are independent of accepted holdings
  Background:
    Given an accepted household holds two canonical securities and cash

  Scenario: Save a valid hypothetical target
    When a balanced target is saved
    Then its security weights and account constraints are retained
    And accepted portfolio state remains unchanged

  Scenario: Reject invalid household weights atomically
    When a target with incomplete weights is saved
    Then the target request fails without persistent changes

  Scenario: Multiple hypothetical targets coexist
    When two differently named targets are saved
    Then both draft targets remain available
    And accepted portfolio state remains unchanged

  Scenario: Editing preserves immutable target versions
    When a balanced target is saved
    And its allocation is edited
    Then the original allocation remains available as version one
    And the latest target is version two

  Scenario: Only one target may be active
    When two differently named targets are saved
    And each target is activated in sequence
    Then only the second target is active
    And accepted portfolio state remains unchanged

  Scenario: Target differences use canonical household weights
    When a balanced target is saved
    And its household allocation differences are requested
    Then current and target dollars and drift are exact
    And accepted portfolio state remains unchanged

  Scenario: Restricted account permissions remain explicit
    When a target restricts the retirement account to one permitted security
    Then the saved constraints preserve that restriction
    And missing account permissions remain unknown

  Scenario: Archiving preserves historical target inputs
    When a balanced target is saved
    And that target is archived
    Then its latest status is archived and historical allocation survives
    And accepted portfolio state remains unchanged

  Scenario: Unknown investment identifiers cannot become target securities
    When a target names an unregistered security
    Then the target request fails without persistent changes

  Scenario: Different household currencies cannot be summed for target drift
    When a balanced target is saved
    And the household has incompatible currencies
    And its household allocation differences are requested
    Then the difference request fails with inconsistent state
