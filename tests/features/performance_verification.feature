Feature: Measured shared-baseline planning workload
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
