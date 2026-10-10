Feature: Explicit incremental news research
  Scenario: Three fictional runs reveal evidence changes without affecting a plan
    Given a selected missing ledger and fictional news input
    When news is validated previewed and its baseline requested
    Then no database is created
    When three fictional observations are explicitly accepted
    Then the history exposes added facts postponed catalysts and changed research assessments
