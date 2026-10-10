Feature: Strict verified political research inputs
  Scenario: A name-only attribution cannot become verified evidence
    Given a fictional political research package
    When only the public role biography supports its contribution
    Then political validation rejects the package

  Scenario: A declared permission cannot override the reviewed policy
    Given a fictional political research package
    When contribution permission is checked without a reviewed policy
    Then political validation rejects the package
