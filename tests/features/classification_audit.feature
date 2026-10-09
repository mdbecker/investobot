Feature: Audited canonical security classifications
  Scenario: Imported suggestions cannot correct an existing unknown security
    Given an unknown security is held in two synthetic accounts
    When a changed snapshot suggests ETF for that security
    Then reconciliation identifies the canonical security and explicit correction workflow
    And reconciliation leaves accepted state unchanged
    When those holdings are accepted
    Then quantities cash basis and lots update while both classifications stay OTHER
    And no classification correction is audited

  Scenario: Direct snapshot acceptance cannot bypass classification confirmation
    Given an unknown security is held in two synthetic accounts
    When a changed snapshot suggests ETF for that security
    And those holdings are accepted
    Then quantities cash basis and lots update while both classifications stay OTHER
    And no classification correction is audited

  Scenario: Unknown incoming classifications preserve confirmed metadata
    Given an unknown security is held in two synthetic accounts
    And its ETF classification is explicitly confirmed
    When a changed snapshot omits the classification
    And those holdings are accepted
    Then canonical and current classifications remain ETF

  Scenario: Known classification contradictions reject the whole snapshot
    Given an unknown security is held in two synthetic accounts
    And its ETF classification is explicitly confirmed
    When a multiple-security snapshot contradicts the confirmed type
    Then no positions cash account metadata securities or snapshots change

  Scenario Outline: Strong identity contradictions reject the whole snapshot
    Given an unknown security is held in two synthetic accounts
    When a multiple-security snapshot conflicts in <identity>
    Then no positions cash account metadata securities or snapshots change
    Examples:
      | identity |
      | cusip |
      | isin |
      | figi |

  Scenario: Initial known classifications require no correction
    Given a household without securities
    When a new ETF snapshot is reconciled and accepted
    Then its initial classification is ETF without review or correction history

  Scenario: Explicit corrections are previewed audited and idempotent
    Given an unknown security is held in two synthetic accounts
    And a plan and historical snapshots are saved
    When ETF classification is previewed and confirmed twice with provenance
    Then preview changes nothing and confirmation updates both accounts once
    And exact financial amounts lots and historical snapshots are preserved
    And the classification history records verified provenance and the saved plan is stale

  Scenario: Classification provenance cannot be invented or omitted
    Given an unknown security is held in two synthetic accounts
    When classification is confirmed without a source
    Then classification fails without changing accepted state
