Feature: A local dashboard supports human-reviewed planning
  Scenario: The dashboard has five clear primary destinations
    When the investor opens the local dashboard
    Then navigation offers Overview Targets Plans Prompt Library and Import & Reconcile
    And the dashboard provides editable targets and manual-review plan controls

  Scenario: Import coverage and confirmed activity remain explicit
    When the investor opens the local dashboard
    Then snapshot completeness is unchecked by default
    And the activity example requires a stable activity ID
    And unsupported transfers are identified for manual review

  Scenario: Targets and overview share accepted financial calculations
    Given an accepted synthetic retirement household
    When a target is saved and explicitly activated through the dashboard API
    Then overview shows the active target and exact accepted value and target drift
    And the saved target can be edited and its historical version inspected
    And accepted holdings are unchanged

  Scenario: Saved plans are inspectable comparable and downloadable
    Given an accepted synthetic retirement household
    When two alternative plans are generated through the dashboard API
    Then the plan views expose manual trades tax values drift and common assumptions
    And the downloaded report matches the persisted plan
    And accepted holdings are unchanged

  Scenario: Changed source state makes a displayed plan visibly stale
    Given an accepted synthetic retirement household
    When two alternative plans are generated through the dashboard API
    And confirmed interest changes the source portfolio
    Then the dashboard API displays stale plan status
    And the dashboard includes a visible stale status treatment
