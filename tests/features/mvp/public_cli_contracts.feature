Feature: Explicit public workflows
  Scenario: Dataset evidence needs explicit publication
    Given a fictional accepted household and dataset manifest
    When the manifest is submitted without confirmation
    Then it is validated without persistent writes
    When the manifest is explicitly confirmed twice
    Then exactly one immutable manifest is published

  Scenario: Removed generation has no compatibility path
    Given a fictional accepted household and dataset manifest
    When public planning commands are discovered
    Then preview is read only and generate is absent

  Scenario: Inline targets cannot secretly be saved
    Given a fictional accepted household and dataset manifest
    When an approved proposal is requested with an embedded target
    Then it is rejected without target or plan writes

  Scenario: Current exposure is an offline persisted read
    Given a fictional accepted household and dataset manifest
    When current exposure is requested
    Then the shared response reports date and numeric coverage without mutation

  Scenario: Monthly timing is an agent preference
    When routine investing guidance is read
    Then it prefers monthly sessions and contributions without hard date gates

  Scenario: Comparing experiments never creates investment targets
    Given a fictional accepted household and dataset manifest
    When historical candidates are compared with a configured approved policy
    Then immutable runs are identified but targets and transition plans are not created
