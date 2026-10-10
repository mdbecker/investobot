Feature: Verified local ledger recovery
  Scenario: B01 Online backup preserves complete committed state
    Given a disposable accepted recovery ledger
    When an online recovery archive is created
    Then the archive verifies and restores the complete accepted state

  Scenario: B02 Tampered artifacts cannot be restored
    Given a recovery archive with a tampered referenced artifact
    When recovery verification is requested
    Then the artifact is identified and replacement is refused

  Scenario: B03 Development schemas are preserved byte for byte
    Given a development schema nine ledger
    When new-design database status is requested
    Then the unsupported schema is reported without changing any bytes

  Scenario: B04 Restore preview preserves the current ledger
    Given a disposable accepted recovery ledger
    When recovery preview and confirmed replacement are requested separately
    Then preview preserves the ledger and confirmation restores the archived state

  Scenario: B05 Corrupt SQLite cannot receive an OK verification
    Given a damaged SQLite ledger
    When database verification is requested
    Then verification reports a specific non-success integrity result

  Scenario: Recovery refuses traversal members
    Given a recovery archive containing a traversal member
    When recovery verification is requested
    Then unsafe members block verification without writing outside staging

  Scenario: First install exposes normalized durable storage
    Given an empty new-design ledger path
    When new-design database status is requested
    Then schema one has relational balances and durable writer settings

  Scenario: Missing verified backup blocks destructive future migration
    Given an empty new-design ledger path
    When a destructive future migration is requested without a verified backup
    Then migration is blocked without changing the accepted database
