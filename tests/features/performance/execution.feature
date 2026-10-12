Feature: Disposable, paired performance execution
  Scenario: A timed mutation starts from the same fixed facts
    Given a fixed synthetic measurement request
    When two fresh observations execute the same mutation
    Then their input and substantive output proofs match
  Scenario: Docker and offline constraints are required
    Given the release resource contract
    When a measurement is requested outside the safe runtime
    Then it rejects the request before opening a selected ledger
  Scenario: Paired revisions rotate in identical order
    Given reference, base and candidate revisions
    When the statistical observation schedule is generated
    Then each revision receives seven observations in rotated order
  Scenario: A runner error remains a failed observation
    Given a child that times out or is killed
    When the parent captures the measurement
    Then the report retains the failure and cannot certify it
