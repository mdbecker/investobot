Feature: Corrected insider ownership disclosures
  Scenario: An amended holding replaces the originally reported balance
    Given a Form 4 discloses 125 directly held common shares on May 2
    And its cited Form 4 amendment corrects the same holding to 120 shares on May 2
    When the insider ownership report is requested
    Then both original and amended observations remain inspectable
    And only 120 shares appear as the effective latest reported balance

  Scenario: Contradictory same-day holdings remain unresolved
    Given two sourced unlinked ownership observations for the same holding and date
    And their reported quantities disagree
    When the insider ownership report is requested
    Then neither amount is selected as a uniquely current balance
    And both filings appear as conflicting latest observations

  Scenario: Unsupported amendment cannot quietly replace ownership
    Given an amended balance without a verifiable original-row link
    When the insider ownership report is requested
    Then the amended balance is marked unresolved
    And the original balance remains the effective latest observation

  Scenario: A filing correction changes a transaction date and code
    Given an original exercise and documented purchase correction
    When insider activity is summarized
    Then the original exercise is superseded
    And the corrected purchase is counted once under May 3
    And its purchase venue remains unknown

  Scenario: Unsupported code correction cannot be counted twice
    Given a proposed code correction without amendment evidence
    When the unresolved activity is accepted
    Then the unsupported correction remains excluded
    And the original transaction remains effective

  Scenario: An amended row cannot correct an unrelated insider trade
    Given a correction attributed to an unrelated reporting owner
    When correction validation is attempted
    Then the correction is rejected without creating storage

  Scenario: Discover fresh correction contracts and skill identity
    Given a source-backed correction package
    When correction commands and schemas are inspected
    Then input version 1.1 and trusted skill version 1.1.0 are exposed
    And accepted research uses fresh schema 9
