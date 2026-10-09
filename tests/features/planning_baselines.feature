Feature: Shared immutable planning baselines
  Scenario: Planning reads only accepted current inputs
    Given a disposable household with large historical observations
    When its planning state is read
    Then only compact latest observation provenance is included

  Scenario: Alternative plans share immutable storage atomically
    Given a disposable household with large historical observations
    When two alternatives are saved from identical planning inputs
    Then one baseline and two snapshot-free details records exist
    And a failed third insertion leaves no orphan baseline

  Scenario: Old schemas require deliberate reset
    Given an incompatible version two database
    When it is opened
    Then reset instructions are reported without destroying data
