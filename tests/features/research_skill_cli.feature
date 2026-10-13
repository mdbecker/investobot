Feature: Research skills are discoverable instructions
  Scenario: Skill tools report explicit project-local mutation scope
    When research skill tools are discovered
    Then installation is scoped to project skill files and discovery is read only
