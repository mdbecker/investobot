Feature: Discoverable investment research skills
  Scenario: Earnings and political research use portable agent skills
    Given Investobot's bundled research skills
    When they are installed for Codex
    Then both portable skills and their references are discoverable

  Scenario: Installing skills preserves user modifications
    Given a user-modified installed skill exists
    When installation is requested without overwrite permission
    Then all installed and unrelated files remain unchanged
