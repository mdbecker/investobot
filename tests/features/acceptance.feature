Feature: PRD acceptance workflows against synthetic household data
  Scenario: An agent composes exposure tax comparisons replacements and alternatives
    Given the representative anonymized household fixture
    When an agent checks concentration and a loss sale
    Then direct and indirect exposure and IRA conflicts are reported
    When an agent compares replacement funds and alternatives
    Then raw similarity metrics and no-write scenario results are available
  Scenario: A post-trade snapshot is explicitly reconciled and accepted
    Given the representative anonymized household fixture
    When a later normalized snapshot reduces a position
    Then the discrepancy is reported without a transaction
    When I explicitly accept the later snapshot
    Then the ledger and normalized audit trail reflect the snapshot
  Scenario: Known bond terms yield deterministic fixed-income metrics
    Given known synthetic fixed-rate bond terms
    When the agent analyzes those terms
    Then yield accrual duration and convexity are available
