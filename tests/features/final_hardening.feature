Feature: Financial and runtime release safeguards
  Scenario: Partial valuation refresh retains previously known aggregate basis
    Given a fully known dated synthetic taxable account
    When a partial valuation refresh has no basis or lot table
    Then known basis and lot history remain available
  Scenario: Contradictory aggregate basis cannot be accepted
    Given a fully known dated synthetic taxable account
    When a complete snapshot contradicts its own lot basis
    Then input is rejected atomically
  Scenario: Completeness must be a JSON boolean
    Given a fully known dated synthetic taxable account
    When normalized completeness is supplied as a string
    Then input is rejected atomically
  Scenario: Same-account ticker conflicts require identity review
    Given a fully known dated synthetic taxable account
    When the same account supplies conflicting strong identity for a ticker
    Then input is rejected atomically
  Scenario: Bad activity numbers have input error semantics
    Given a fully known dated synthetic taxable account
    When an invalid numeric activity is previewed through the CLI
    Then the CLI returns input error JSON on stderr
  Scenario: Impossible fee accounting is rejected
    Given a fully known dated synthetic taxable account
    When a confirmed sale fee exceeds its gross proceeds
    Then input is rejected atomically
  Scenario: Missing activity fields have input error semantics
    Given a fully known dated synthetic taxable account
    When a malformed activity is previewed through the CLI
    Then the CLI returns input error JSON on stderr
  Scenario: Unknown price input shape cannot silently use defaults
    Given a fully known dated synthetic taxable account
    When planning receives a list instead of price observations
    Then invalid price input is rejected without persisting a plan
  Scenario: Fresh quotes do not certify stale position quantities
    Given a fully known dated synthetic taxable account
    When a plan uses fresh prices against old source quantities
    Then the plan requires review of source freshness
  Scenario: IRA planning needs no fictional taxable lot inventory
    Given a dated retirement account without tax lots
    When an otherwise eligible replacement target is planned
    Then the plan is ready for human review with zero taxable gain
  Scenario: Native inspection defaults to loopback
    When the native inspection server is created with default host
    Then its listener uses loopback
  Scenario: Docker prompt files use persistent local storage
    Given the Docker application environment
    Then configured prompt storage uses the persistent data volume
  Scenario: Prompt CRUD is fully accessible through the CLI
    When the agent saves reads and deletes a plain Markdown prompt
    Then every prompt output is JSON and the copied text matches exactly
  Scenario: Three portfolio alternatives preserve a shared baseline
    Given a fully known dated synthetic taxable account
    When an agent creates three targets and plans and exports their reports
    Then their comparison uses the same source state and old reports remain reproducible
