Feature: Historical research continuity and disputed claims
  Scenario: An unresolved event survives an omitted run
    Given an older fictional event and a later omitted observation
    When effective context is requested
    Then the event and unanswered question retain their older provenance

  Scenario: Rediscovery is reobservation rather than novelty
    Given an older fictional event and a later omitted observation
    When the event returns in a third run with new verified evidence
    Then the delta shows reobservation with prior evidence and new facts

  Scenario: Explicit resolution stops active carry-forward
    Given a fictional event explicitly resolved before a later omitted run
    When effective context is requested
    Then the resolved event remains historical rather than active

  Scenario: Newly disputed allegations remain separate from verified updates
    Given two fictional runs with a newly disputed allegation
    When the selected runs are compared
    Then the disputed addition has citations and no verified fact update

  Scenario: Verification withdrawal remains visible and uncertain
    Given two fictional runs withdrawing a fact verification
    When the selected runs are compared
    Then the claim is explicitly disputed rather than disproven
