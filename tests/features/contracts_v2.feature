Feature: Agent command discovery
  Scenario: An agent discovers portfolio tools and explicit mutation scopes
    When the agent lists the tool catalogue
    Then the catalogue identifies financial mutations and cache writes

  Scenario: An agent retrieves the hypothetical simulation contract
    When the agent describes portfolio.simulate
    Then the contract describes inputs outputs and a read-only example

  Scenario: Snapshot validation schemas remain authoritative
    When the agent requests the complete discovery schema
    Then snapshot commands expose the validated snapshot schema
    And discovery documents structured error semantics

  Scenario: Commands registered later appear in discovery
    Given an application with a newly registered target command
    When the agent lists that application's tool catalogue
    Then the target command is discovered without another schema registry

  Scenario: Unknown commands are rejected as invalid input
    When the agent describes an unknown tool
    Then the request fails with input error code one
