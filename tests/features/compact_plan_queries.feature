Feature: Schema 1 saved alternatives retain compact immutable results
  Scenario: Common queries return compact ordered summaries
    Given a fresh schema 1 household with two saved alternatives
    When saved alternatives are listed and compared
    Then compact ordered summaries preserve saved metrics without changing accepted facts

  Scenario: Full retrieval reads only the selected immutable plan
    Given a fresh schema 1 household with two saved alternatives
    When the first saved plan is retrieved after current cash changes
    Then its full details and source state remain unchanged

  Scenario: Planning ignores unrelated historical payloads
    Given a fresh schema 1 household with two saved alternatives
    When an older large observation is added
    Then the planning fingerprint stays unchanged and current evidence stays compact
    And financial decimal spelling is normalized while identifiers and provenance matter

  Scenario: Concurrent saves share an atomic baseline
    Given a fresh schema 1 household with two saved alternatives
    When independent connections concurrently save two more alternatives
    Then all alternatives reference one complete baseline
