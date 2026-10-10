Feature: Source-backed news input contract
  Scenario: Preserve facts and unknown dates
    Given a fictional issuer announcement and source-backed fact
    When the package is validated
    Then evidence and unknown catalyst dates remain explicit
    And interpretations remain separate from verified facts
  Scenario: Reject unsupported resolutions
    Given an event without cited outcome evidence
    When it is marked resolved or a question answered without support
    Then validation rejects the package atomically
  Scenario: Preserve disputed claims
    Given a disputed fictional claim
    When validated
    Then it remains disputed and cannot answer a question as a verified fact
