Feature: Research completeness across frozen specialty tasks
  Research coverage describes the requested scope, not merely any accepted evidence.

  Scenario: One complete specialty cannot complete five required tasks
    Given a frozen synthetic issuer queue requiring five specialty skills
    And complete accepted news evidence for the selected issuer
    When the selected portfolio research plan is reported
    Then news coverage is complete while four specialties remain not researched
    And selected and whole portfolio research remain incomplete

  Scenario: Historical complete research does not cover a later requested window
    Given a frozen synthetic issuer queue requiring five specialty skills
    And complete accepted news evidence predating the requested window
    When the selected portfolio research plan is reported
    Then current news coverage is unavailable with explicit historical context

  Scenario: Selected issuer reports do not load unrelated accepted evidence
    Given a frozen synthetic issuer queue requiring five specialty skills
    And complete accepted news evidence for the selected issuer
    And corrupted accepted research for an unrelated issuer
    When the selected portfolio research plan is reported
    Then selected issuer source evidence is returned independently
