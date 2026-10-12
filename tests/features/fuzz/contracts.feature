Feature: Explicit offline exploration has deterministic independent guards
  Scenario Outline: A fixed harness example obeys its exploratory safety contract
    Given a fixed synthetic example of <contract>
    When the deterministic harness contract is evaluated
    Then the required independent result is observable

    Examples:
      | contract |
      | AFZ-01 |
      | AFZ-02 |
      | AFZ-03 |
      | AFZ-04 |
      | AFZ-05 |
      | AFZ-06 |
      | AFZ-07 |
      | AFZ-08 |
      | AFZ-09 |
      | AFZ-10 |
      | AFZ-11 |
      | AFZ-12 |
      | AFZ-13 |
      | AFZ-14 |
      | AFZ-15 |
      | AFZ-16 |
      | AFZ-17 |
      | AFZ-18 |
