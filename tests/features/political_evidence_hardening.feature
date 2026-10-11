Feature: Political research evidence and identity hardening
  Scenario: Public record locators survive credential removal
    Given a public disclosure URL with a record locator and credential
    When the source URL is normalized
    Then its record locator is retained and credentials are absent
  Scenario: Research cannot attach to an unrelated security
    Given a registered fictional security
    When research supplies its ID with a contradictory ticker
    Then import fails without persisting research
  Scenario: Candidate summaries preserve verified recipient identities
    Given a fictional contribution to a verified candidate committee
    When the recipient summary is requested
    Then candidate and committee identities remain visible without donor affiliation
