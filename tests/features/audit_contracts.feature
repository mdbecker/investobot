Feature: Discover compact plan response contracts
  Scenario Outline: Plan tools describe their response detail
    When the agent describes the audit tool "<tool>"
    Then its response detail is "<detail>"

    Examples:
      | tool          | detail          |
      | plan.list     | compact_summary |
      | plan.compare  | compact_summary |
      | plan.show     | full_plan       |

  Scenario: Reconciliation describes suggested classification reviews
    When the agent describes the audit tool "portfolio.reconcile"
    Then its contract identifies explicit classification reviews
