Feature: Deterministic known-bond analysis
  Scenario: Analyze a fixed-rate bond using disclosed conventions
    Given a synthetic fixed-rate bond with known terms
    When I analyze the bond
    Then yield accrued interest dirty price duration and convexity are calculable
    And calculation conventions are disclosed

  Scenario: Reject unsupported supplied call terms
    Given a synthetic fixed-rate bond with known terms
    And a supplied call date and redemption price
    When I analyze the bond
    Then callable bond measures are unavailable

  Scenario: Preserve unknown bond terms
    Given a bond without a known coupon or price
    When I analyze the bond
    Then bond analysis reports insufficient data without guessed metrics

  Scenario: Reject invalid bond terms
    Given a bond with an invalid payment frequency
    When I analyze the bond
    Then invalid bond input is rejected

  Scenario: Do not calculate an irregular coupon stub without complete conventions
    Given a synthetic fixed-rate bond with known terms
    And an issue date that creates an irregular coupon stub
    When I analyze the bond
    Then bond analysis reports insufficient data without guessed metrics
