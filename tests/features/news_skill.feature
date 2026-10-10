Feature: Portable source-backed company news skill
  Scenario: Discover and install news without altering existing research skills
    Given the existing political and earnings skill contents
    When news research skill discovery and project installation are requested
    Then news guidance and all existing bundles are available unchanged
