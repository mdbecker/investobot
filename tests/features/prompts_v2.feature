Feature: Local reusable prompt library
  Scenario: Bundled research prompts cover the requested workflows
    When I list the local prompt library
    Then all nine investment workflow prompts are available
    And reading the library creates no user directory

  Scenario: Copying a prompt preserves its full plain Markdown
    When I read the concentration prompt
    Then its complete text contains portfolio analysis and human control instructions

  Scenario: Users create edit and delete their own prompt
    When I save and edit a personal prompt
    Then its latest full text is available
    When I delete the personal prompt
    Then it is no longer available

  Scenario: User overrides preserve recoverable bundled defaults
    When I override and then remove the concentration prompt
    Then the original bundled text is restored
    And deleting the bundled original is rejected

  Scenario Outline: Unsafe prompt identifiers are rejected
    When I save a prompt named "<slug>"
    Then a prompt input error prevents the write
    Examples:
      | slug                    |
      | ../private              |
      | /tmp/private            |
      | nested/private          |
      | unsafe.md               |
      | UPPERCASE               |

  Scenario: A symlink cannot expose or overwrite an outside file
    Given a prompt file symlink to an outside document
    When I try to read edit and delete the symlink prompt
    Then every operation is rejected and the outside file is unchanged

  Scenario: A symlink directory cannot redirect prompt storage
    Given the configured prompt directory is a symlink
    When I save a personal prompt
    Then a prompt input error prevents the write

  Scenario: Oversized prompts are rejected before writing
    When I save a prompt larger than 64 KiB
    Then a prompt input error prevents the write

  Scenario: The configured environment selects local storage
    Given the prompt directory is configured by environment
    When I save a personal prompt
    Then it is stored in that configured directory
