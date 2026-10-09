Feature: Schema three query boundaries preserve immutable plans
  Scenario: Common queries avoid full saved payloads
    Given a disposable schema three household with two saved alternatives
    When plan list and comparison run with payload reads forbidden
    Then summaries preserve saved metrics and hash the household once per request
    And list ordering and selected lookup use SQLite indexes

  Scenario: Full retrieval reads only the selected immutable plan
    Given a disposable schema three household with two saved alternatives
    When the first saved plan is retrieved after current cash changes
    Then its full details and source state remain unchanged

  Scenario: Planning ignores unrelated historical payloads
    Given a disposable schema three household with two saved alternatives
    When an older large observation is added and planning reads are guarded
    Then the planning fingerprint stays unchanged and no snapshot rows are decoded
    And financial decimal spelling is normalized while identifiers and provenance matter

  Scenario: Concurrent saves share an atomic baseline
    Given a disposable schema three household with two saved alternatives
    When independent connections concurrently save two more alternatives
    Then all alternatives reference one complete baseline
