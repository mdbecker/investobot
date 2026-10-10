Feature: Immutable dated public evidence
  Scenario: B16 Missing dividend adjustment is unavailable
    Given a fictional history response containing only unadjusted close
    When total return history is requested
    Then adjusted return is unavailable with a typed missing-field issue

  Scenario: B18 Historical holdings select an eligible vintage
    Given two synthetic fund holdings vintages
    When the September holdings snapshot is requested
    Then only the September eligible vintage is returned

  Scenario: B19 Pinned analytical reads are reproducible and read only
    Given a frozen synthetic analytical dataset
    When the pinned analytical dataset is read twice
    Then the results and fingerprints agree without changing the ledger

  Scenario: B65 Native inspection refuses public exposure
    Given a disposable inspection path
    When native inspection attempts to bind externally
    Then the bind is refused and Compose publishes only loopback

  Scenario: B66 Fresh quickstart discovers all portable workflows
    Given an offline fresh checkout
    When installed workflow discovery is requested
    Then seven portfolio workflows and safe backup instructions are discoverable

  Scenario: Offline analytics loads pinned analytical extensions without downloads
    Given an offline fresh checkout
    When analytical runtime capabilities are requested
    Then DuckDB and sqlite vec report pinned offline availability

  Scenario: Manifest verification detects damaged immutable evidence
    Given a frozen synthetic analytical dataset
    When a referenced artifact changes after its manifest is frozen
    Then the pinned analytical read is blocked by the exact artifact hash mismatch

  Scenario: Published source dates cannot be replaced by retrieval freshness
    Given a fictional undated quote response
    When its quote is retrieved
    Then retrieval time does not make the source quote current
