Feature: Household look through without fabricated exposure
  Scenario: Direct holdings and multiple funds combine across accounts
    Given direct Apple shares and two synthetic funds in different accounts
    When I compute household exposure
    Then Apple direct and indirect value are combined
    And known sector values are aggregated
  Scenario: Partial fund data leaves an explicit unknown remainder
    Given a fund with twenty percent available holdings and household cash
    When I compute household exposure
    Then eighty percent of the fund remains unknown
    And cash remains visible
  Scenario: Missing holdings and unsupported assets remain unknown
    Given a fund without holdings and an unsupported position
    When I compute household exposure
    Then all invested value is unknown
  Scenario: Excess provider weights never inflate household assets
    Given a fund with provider weights exceeding one hundred percent
    When I compute household exposure
    Then the inconsistent fund remains unknown
