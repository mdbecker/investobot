Feature: Explicit corrections preserve trustworthy portfolio state
  Scenario: A verified ETF classification replaces an unknown type
    Given an unknown security in two dated accounts with saved plans
    When an ETF classification is confirmed
    Then canonical and current classifications agree without changing inventory
    And classification provenance is audited and plans become stale
  Scenario: Preview and repeated corrections do not create mutations
    Given an unknown security in two dated accounts with saved plans
    When classification is previewed then confirmed twice
    Then preview is read only and the repeat is unchanged
  Scenario Outline: Invalid classification is rejected atomically
    Given an unknown security in two dated accounts with saved plans
    When classification is requested with "<type>" and "<source>"
    Then the correction is rejected atomically
    Examples:
      | type | source |
      | ETF |         |
      | CRYPTO | issuer |
  Scenario: Known classifications cannot be replaced
    Given an unknown security in two dated accounts with saved plans
    When a verified ETF is classified as STOCK
    Then the correction is rejected atomically
  Scenario: Incomplete imports retain verified security classification
    Given an unknown security in two dated accounts with saved plans
    When a verified ETF receives an incomplete classification snapshot
    Then every current position remains an ETF
  Scenario: Contradictory known import classification is atomic
    Given an unknown security in two dated accounts with saved plans
    When a verified ETF receives a STOCK snapshot
    Then the correction is rejected atomically
  Scenario: Routine snapshots preserve authoritative account configuration
    Given an unknown security in two dated accounts with saved plans
    When a snapshot changes every account metadata field and valuation
    Then reconciliation explains metadata discrepancies and preserves configuration
  Scenario: Confirmed account correction is audited and stales plans
    Given an unknown security in two dated accounts with saved plans
    When account tax treatment is previewed then confirmed twice
    Then account preview is read only and confirmation is audited once
    And saved plans are stale
  Scenario Outline: Invalid account updates roll back atomically
    Given an unknown security in two dated accounts with saved plans
    When an invalid account update "<case>" is confirmed
    Then the correction is rejected atomically
    Examples:
      | case |
      | unknown |
      | identity |
      | unsupported |
      | currency |
      | missing reason |
      | missing source |
      | invalid boolean |
      | invalid tax |
  Scenario: Empty new accounts permit explicit currency changes
    Given an empty account with no cash observation
    When its currency is explicitly changed
    Then its new currency is audited
  Scenario: Undated updates cannot supersede dated holdings silently
    Given an unknown security in two dated accounts with saved plans
    When an undated changed snapshot is reconciled and ordinarily applied
    Then unknown freshness requires override and leaves state unchanged
  Scenario: Reviewed undated updates preserve unknown dates
    Given an unknown security in two dated accounts with saved plans
    When an undated changed snapshot is applied with justification
    Then the unknown date override is audited and plans are stale
  Scenario Outline: Snapshot freshness policy is explicit
    Given a "<prior>" accepted source date
    When a snapshot with "<incoming>" source date is reconciled
    Then its date status is "<status>" and override is "<required>"
    Examples:
      | prior | incoming | status | required |
      | none | unknown | NO_PRIOR_DATED_STATE | false |
      | unknown | unknown | NO_PRIOR_DATED_STATE | false |
      | 2026-10-08 | 2026-10-08 | KNOWN_CURRENT | false |
      | 2026-10-08 | 2026-10-09 | KNOWN_CURRENT | false |
      | 2026-10-08 | 2026-10-07 | OLDER_THAN_ACCEPTED | true |
      | 2026-10-08 | unknown | UNKNOWN_SOURCE_DATE | true |
  Scenario: Previously applied snapshots remain no-ops
    Given an unknown security in two dated accounts with saved plans
    When the same snapshot is applied again
    Then no snapshot transition is duplicated
  Scenario: Overrides require reasons
    Given an unknown security in two dated accounts with saved plans
    When an undated changed snapshot is applied without justification
    Then the correction is rejected atomically
  Scenario: Older snapshot overrides have a distinct audit category
    Given an unknown security in two dated accounts with saved plans
    When an older snapshot is applied with justification
    Then an older source override is audited
  Scenario: CLI exposes explicit corrections and machine readable contracts
    Given an unknown security in two dated accounts with saved plans
    When corrections are previewed and confirmed through the CLI
    Then CLI corrections and discovery contracts are consistent
  Scenario: Legacy records remain readable with empty audit defaults
    Given legacy account and security records without audit fields
    When the ledger is reopened
    Then legacy records expose safe empty audit histories
  Scenario: Classification requires an existing canonical security
    Given an unknown security in two dated accounts with saved plans
    When a nonexistent security is classified
    Then the correction is rejected atomically
  Scenario: Registration cannot bypass classification confirmation
    Given an unknown security in two dated accounts with saved plans
    When registration attempts to replace OTHER with ETF
    Then the correction is rejected atomically
  Scenario: Strong identity conflicts cannot be merged after classification
    Given an unknown security in two dated accounts with saved plans
    When a verified ETF receives conflicting strong identities
    Then the correction is rejected atomically
  Scenario: Removing dated observation provenance requires review even with equal values
    Given an unknown security in two dated accounts with saved plans
    When an otherwise unchanged snapshot loses its source date
    Then unknown freshness requires override and leaves state unchanged
