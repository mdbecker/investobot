Feature: Account aware manual trade plans
  Scenario: Retirement reallocation reaches target without taxable realization
    Given an eligible synthetic retirement portfolio
    When a full replacement plan is generated
    Then it sells and buys in the IRA with zero taxable gain and no actual mutation
  Scenario: Taxable sale proposes specific lots
    Given an eligible synthetic taxable portfolio
    When a full replacement plan is generated
    Then taxable sales identify exact lots and long term gains
  Scenario: Gain budget limits the sale
    Given an eligible synthetic taxable portfolio
    And the long term gain budget is two hundred
    When a full replacement plan is generated
    Then sales respect the budget and disclose remaining drift
  Scenario: Unavailable retirement investments cannot be bought
    Given an eligible synthetic retirement portfolio
    And the replacement investment is not permitted
    When a full replacement plan is generated
    Then the restricted replacement is not purchased and the plan needs review
  Scenario: Excluded holdings cannot fund a purchase
    Given an eligible synthetic retirement portfolio
    And the only holding is excluded from trading
    When a full replacement plan is generated
    Then no unfunded purchases are proposed
  Scenario: Missing basis cannot produce ready taxable plans
    Given an eligible synthetic taxable portfolio
    And the lot basis is unresolved
    When a full replacement plan is generated
    Then no taxable sale is proposed and missing basis requires review
  Scenario: Unknown eligibility is not unrestricted
    Given an eligible synthetic retirement portfolio
    And account trading eligibility is unknown
    When a full replacement plan is generated
    Then no trades are proposed and eligibility requires review
  Scenario: Stale price assumptions cannot produce ready plans
    Given an eligible synthetic retirement portfolio
    And the replacement price is stale
    When a full replacement plan is generated
    Then no stale price purchase is proposed
  Scenario: Bond positions do not receive automatic trades
    Given an eligible synthetic retirement portfolio
    And the replacement security is an individual bond
    When a full replacement plan is generated
    Then no automatic bond purchase is proposed
  Scenario: Fractional fund increments are explicit
    Given an eligible synthetic retirement portfolio
    And a mutual fund permits hundredth unit trades with a cash target
    When a full replacement plan is generated
    Then the mutual fund purchase uses the explicit fractional increment
  Scenario: Source changes mark plans stale without rewriting saved inputs
    Given an eligible synthetic retirement portfolio
    When a full replacement plan is generated
    And confirmed account activity changes the source state
    Then the saved plan is stale and its original inputs remain immutable
  Scenario: Alternative targets compare against the same baseline
    Given an eligible synthetic retirement portfolio
    When two alternatives are planned against the same portfolio
    Then comparison reports turnover tax drift and a common baseline
  Scenario: Multiple accounts coordinate with retirement sales first
    Given eligible taxable and retirement accounts
    When a full replacement plan is generated
    Then retirement sales precede taxable sales and cash remains in each account
  Scenario: Mixed currencies reject planning atomically
    Given an eligible synthetic retirement portfolio
    And an account uses another currency
    When a full replacement plan is requested
    Then planning rejects mixed currencies without saving a plan
  Scenario: Agent CLI saves compares and exports persisted plans
    Given an eligible synthetic retirement portfolio
    When the agent generates compares and exports plans through the CLI
    Then all plan commands return JSON and the report matches the persisted plan
