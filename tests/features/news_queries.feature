Feature: Conservative news changes and compact prior context
  Scenario: A second article corroborates an existing story
    Given immutable fictional runs sharing a stable event key and verified facts
    When another source is added and a headline is renamed
    Then the change is new evidence only and retains exact source links
