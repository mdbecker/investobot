Feature: Immutable isolated earnings persistence
  Scenario: Preview and idempotently accept source-backed earnings
    Given a fictional validated earnings package and a fresh ledger
    When earnings import is previewed
    Then no persistent bytes or financial state change
    When earnings are confirmed and equivalent reordered input is confirmed again
    Then one immutable source-backed run exists with trusted skill provenance
