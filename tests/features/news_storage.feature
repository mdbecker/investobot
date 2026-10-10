Feature: Isolated immutable news research
  Scenario: Preview and explicitly accept a fictional event
    Given a fictional news package and fresh ledger
    When the package is previewed then explicitly accepted twice
    Then preview changes no bytes and one immutable run preserves financial state
