Feature: Measured shared-baseline planning workload
  Scenario: The unchanged synthetic workload reports efficient storage and access
    Given the disposable benchmark contains the required synthetic household
    When its twenty alternative plans are measured
    Then the measurement reports one baseline and separate stored JSON sizes
    And plan storage growth is below forty four MiB with compact responses
    And planning persistence and query verification measurements are available
    And two selected historical reports survive a confirmed cash change

  Scenario: Listing reads only its summary metadata
    Given a small saved synthetic alternative
    When SQLite disallows comparison-only assumption hash reads
    Then listing the alternative still succeeds

  Scenario: Audit-only metadata does not invalidate financial planning inputs
    Given a small saved synthetic alternative
    When only account and security audit histories are appended
    Then its planning fingerprint and saved status remain current

  Scenario: Planning fingerprints retain every financial decimal digit
    Given financial states containing large exact decimal cash balances
    Then distinct final cents have distinct fingerprints and trailing zeros do not
