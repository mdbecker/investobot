Feature: Reliable normalized HTML snapshots
  Scenario: Distinct lots aggregate their full known basis and identifiers
    Given two distinct lots of the same ETF
    When the account page is normalized
    Then position totals equal the sum of both lots
    And identifiers are preserved on positions and lots

  Scenario: Unknown lot basis remains unknown at the position level
    Given two lots with one missing basis
    When the account page is normalized
    Then aggregate basis remains unknown

  Scenario Outline: Contradictory source rows cannot be silently imported
    Given an account page with <problem>
    When the account page is normalized
    Then normalization fails with a source conflict
    Examples:
      | problem                        |
      | duplicate position rows        |
      | duplicate lot rows             |
      | conflicting security identities |
      | conflicting lot prices         |
      | mixed summary and lot rows     |

  Scenario: A generic import makes no completeness claims
    Given two distinct lots of the same ETF
    When the account page is normalized
    Then position and lot coverage are incomplete booleans
    And the source timestamp is unknown

  Scenario: Explicit completeness and source date are preserved
    Given two distinct lots of the same ETF
    When the complete account page is normalized with its source date
    Then position and lot coverage are complete booleans
    And the supplied source date is distinct from import time

  Scenario: An unsupported table cannot establish financial state
    Given an account page without a supported holdings table
    When the account page is normalized
    Then normalization fails without producing a snapshot
