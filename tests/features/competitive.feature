Feature: Evidence-preserving competitive research
  Scenario: An agent can discover the competitive research method
    Given Investobot has bundled research skills
    When a user installs them for Codex or Claude Code
    Then competitive research is discoverable with its method and JSON contract
    And existing installed skills and user modifications are preserved

  Scenario: Accept a documented business overlap
    Given a valid fictional peer-research package
    When their competitive research is validated
    Then the corresponding business segments and common market are recognized

  Scenario: Reject unsupported competitor claims
    Given a peer is named without evidence of overlapping markets
    When its research package is rejected
    Then no database is created

  Scenario: Reject an unrelated registered security
    Given Fictional B is linked to Fictional C's registered security ID
    When its conflicting identity is validated
    Then the conflicting identity is rejected without writes

  Scenario: Preserve an unsupported qualitative conclusion as uncertainty
    Given a product claim is sourced but competitive superiority is unproven
    When a comparative finding is saved
    Then its factual basis and possible implication remain distinguishable
    And its uncertainty remains visible

  Scenario: Compare like-for-like reported revenue
    Given a valid fictional peer-research package
    When their peer matrix is requested
    Then the subject-minus-peer difference is 20 million USD
    And the peer-relative difference is 20 percent
    And both observations retain their original source references

  Scenario: Do not compare incompatible reports
    Given a subject and peer report different currencies bases and periods
    When their peer matrix is requested
    Then both reported values remain visible without numeric differences

  Scenario: Segment comparisons require an explicit market overlap
    Given similar-sounding segment revenues have no explicit overlap association
    When their peer matrix is requested
    Then both reported values remain visible without numeric differences

  Scenario: Missing private-company numbers are unknown
    Given a documented private competitor has no published revenue
    When their peer matrix is requested
    Then private revenue remains unavailable rather than zero

  Scenario: Preview before accepting company research
    Given a valid fictional peer-research package
    When its import is previewed
    Then no database is created
    And the preview declares research-only mutation

  Scenario: Accepted research is immutable and repeatable
    Given an accepted fictional peer-research package
    When the same facts are imported with reordered sources and metrics
    Then no duplicate run is created
    And a corrected package creates a separate historical run

  Scenario: Rejected evidence cannot partially persist
    Given accepted research and a new package referencing its absent source
    When the new import is rejected
    Then no partial company metric or finding is saved

  Scenario: Research does not become an investment recommendation
    Given a valid fictional peer-research package
    When the peer summary is requested
    Then the advantage is shown with assumptions and evidence
    And no score target allocation or trade recommendation is produced
