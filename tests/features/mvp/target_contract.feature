Feature: Targets describe allocations while approved policies authorize trades
  Scenario Outline: A target cannot silently accept an inactive execution rule
    Given a synthetic account with 200 cash and a registered investment
    When a target is saved with legacy execution field "<field>"
    Then the target is rejected without writing a target version

    Examples:
      | field                |
      | permitted_securities |
      | cash_minimums        |
      | trade_increments     |
      | price_max_age_days   |

  Scenario Outline: Target weights never confer permission to buy
    Given a synthetic account with 200 cash and a registered investment
    When a contribution is proposed with "<permission>" policy permission
    Then no purchase is proposed and accepted facts remain unchanged

    Examples:
      | permission |
      | missing    |
      | denied     |

  Scenario: An approved policy cash floor controls purchases
    Given a synthetic account with 200 cash and a registered investment
    When a contribution is proposed with "allowed" policy permission
    Then one share costs 100 and the remaining 100 preserves the policy cash floor

  Scenario: The onboarding target example follows the supported schema
    When the target documentation JSON is validated
    Then it contains only supported target fields
