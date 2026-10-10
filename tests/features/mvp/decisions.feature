Feature: Conservative planning and reproducible exposure and hypothetical history
  Scenario Outline: Contribution-first plan safeguards
    Given a fictional SQLite household for decision <case>
    When the pinned decision is evaluated
    Then decision <case> satisfies its financial acceptance contract
    Examples:
      | case |
      | B17 |
      | B31 |
      | B32 |
      | B33 |
      | B34 |
      | B35 |
      | B36 |
      | B37 |
      | B38 |
      | B31_UNKNOWN_FEE |
      | B31_UNCONFIRMED_CASH |
      | B31_UNKNOWN_POLICY |

  Scenario Outline: Recursive exposure preserves unknown coverage
    Given a fictional SQLite household for decision <case>
    When the pinned decision is evaluated
    Then decision <case> satisfies its financial acceptance contract
    Examples:
      | case |
      | B39 |
      | B40 |
      | B41 |
      | B42 |
      | B43 |
      | B44 |

  Scenario Outline: Historical strategy comparisons do not imply actual performance
    Given a fictional SQLite household for decision <case>
    When the pinned decision is evaluated
    Then decision <case> satisfies its financial acceptance contract
    Examples:
      | case |
      | B45 |
      | B46 |
      | B47 |
      | B48 |

  Scenario Outline: Full planning exposure and historical safeguards
    Given a fictional SQLite household for decision <case>
    When the extended pinned decision is evaluated
    Then extended decision <case> preserves its declared constraint
    Examples:
      | case |
      | P_CONFIRMED_CADENCE |
      | P_UNCONFIRMED_CADENCE |
      | P_CASH_FLOOR |
      | P_MINIMUM_NOTIONAL |
      | P_INDIVIDUAL_BOND |
      | P_LOSS_BUDGET |
      | L_DEPTH_BOUND |
      | L_UNKNOWN_ISSUER |
      | L_MINIMUM_TIES |
      | L_PUBLICATION_CUTOFF |
      | H_SESSION_GAP |
      | H_FEE_MISMATCH |
      | H_CASH_SCHEDULE_MISMATCH |
      | H_PINNED_READ |
