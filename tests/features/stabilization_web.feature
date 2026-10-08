Feature: Safe account snapshot acceptance in the inspection interface
  Scenario: Reconciliation exposes preserved account metadata
    Given the inspection ledger has accepted dated retirement holdings
    When a changed snapshot with taxable metadata is reconciled through the interface
    Then reconciliation explains that account configuration is preserved

  Scenario: An undated update requires deliberate review
    Given the inspection ledger has accepted dated retirement holdings
    When a changed undated snapshot is reconciled through the interface
    Then the interface reports an unknown source date requiring an override
    And ordinary acceptance leaves the holdings unchanged
    When the update is accepted with an explained override
    Then the undated holdings are accepted without inventing a source date

  Scenario: The import controls require an explained freshness override
    Given a local inspection interface
    When the import interface is inspected
    Then acceptance depends on reconciliation and a required override explanation
