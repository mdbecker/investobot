Feature: Research skills are discoverable instructions
  Scenario: Skill tools report explicit project-local mutation scope
    When research skill tools are discovered
    Then installation is scoped to project skill files and discovery is read only
  Scenario: Political prompt migration preserves user overrides
    Given a user override of the legacy political prompt
    When bundled prompts are inspected
    Then the political prompt is no longer bundled and the user override survives
