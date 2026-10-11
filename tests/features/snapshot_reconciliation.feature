Feature: Safe successive account snapshots
  Scenario Outline: Reconciliation reports valuation changes
    Given an accepted complete dated account snapshot
    When the next snapshot changes "<field>" to "<value>"
    Then reconciliation reports "<field>" as CHANGED_VALUE
    Examples:
      | field        | value |
      | price        | 110   |
      | market_value | 1100  |
      | cost_basis   | 850   |
  Scenario: Partial inventory preserves unobserved holdings and lots
    Given an accepted complete dated account snapshot
    When an incomplete snapshot omits a holding and all lots
    Then the unobserved holding and previous lots remain
  Scenario: Complete inventory removes absent holdings
    Given an accepted complete dated account snapshot
    When a complete snapshot omits a holding
    Then the absent holding and its lots are removed
  Scenario: Changed quantity without lots is unresolved
    Given an accepted complete dated account snapshot
    When an incomplete snapshot changes quantity without lots
    Then the updated position has unresolved lot state
  Scenario: Old snapshot cannot overwrite newer state
    Given an accepted complete dated account snapshot
    When an older snapshot is applied without override
    Then application conflicts and leaves the ledger unchanged
  Scenario: Old snapshot override requires justification
    Given an accepted complete dated account snapshot
    When an older snapshot is applied with a justified override
    Then the override justification is audited
  Scenario: Identical snapshot creates no second transition
    Given an accepted complete dated account snapshot
    When the identical snapshot is applied again
    Then there is still one snapshot transition
  Scenario: Contradictory identity application is atomic
    Given an accepted complete dated account snapshot
    When a snapshot bridges conflicting security identifiers
    Then application conflicts and leaves the ledger unchanged
  Scenario: Classification changes are reconciled
    Given an accepted complete dated account snapshot
    When the account classification changes
    Then reconciliation reports account classification changes
