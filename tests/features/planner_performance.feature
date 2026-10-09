Feature: Efficient deterministic trade planning
  Scenario: Retirement priority and taxable loss lots retain exact results
    Given a deterministic mixed household with gain and loss lots
    When its constrained replacement plan is generated
    Then the exact retirement-first trades and lot allocations are preserved
    And final cash, gains, tax and allocation preserve the recorded results
    And planning leaves accepted holdings and provider caches unchanged

  Scenario Outline: Inconsistent authoritative simulation cannot be persisted
    Given a deterministic mixed household with gain and loss lots
    And the authoritative simulation returns inconsistent <field>
    When its constrained replacement plan is requested
    Then inconsistent simulation fails without saving a plan
    And planning leaves accepted holdings and provider caches unchanged

    Examples:
      | field      |
      | cash       |
      | allocation |
