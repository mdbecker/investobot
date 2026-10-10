Feature: Source-backed fund share-class diligence
  Scenario: The agent skill explains a fund's source-backed review
    Given the bundled Investobot research skills
    When they are installed for Codex or Claude Code
    Then fund diligence guidance and its authoritative JSON contract are discoverable
    And existing customized skills remain untouched

  Scenario: Two mutual-fund classes are not the same fee disclosure
    Given the same SEC fund series has Class A and Class I shares
    And a fee table is reported only for Class A
    When Class I research is validated
    Then Class A fees cannot be reported as Class I fees

  Scenario: A similar name cannot identify the wrong fund series
    Given a registrant offers two different funds
    When one fund's holdings are attributed to the other series
    Then the unsupported research is rejected before acceptance

  Scenario: Expense ratios and sales loads remain different costs
    Given a mutual-fund class reports a 0.60% net expense ratio and a 3% front load
    When its research summary is requested
    Then the two fee types remain separately labeled and sourced
    And they are not added into a fabricated annual fee

  Scenario: A temporary fee waiver retains its expiry
    Given an ETF reports a 0.25% gross expense ratio and 0.15% net ratio with a dated waiver
    When its research is summarized
    Then both ratios and the waiver expiry remain visible

  Scenario: An incomplete portfolio is not shown as a full allocation
    Given an ETF publishes two top positions weighing 6% and 4%
    When its holdings are inspected
    Then reported weight totals 10%
    And the other 90% is not assigned to fabricated holdings
    And full-portfolio top-ten concentration remains unavailable

  Scenario: Unknown index rules remain unknown
    Given an index fund names its index but does not disclose reconstitution rules
    When its method is summarized
    Then the index remains identified with source evidence
    And the absent reconstitution method remains unknown

  Scenario: Turnover is not exchange trading volume
    Given a mutual fund reports 18% annual portfolio turnover
    When its diligence summary is requested
    Then 18% is shown as portfolio turnover with its fiscal period
    And not as ETF daily trading volume

  Scenario: ETF trading costs are not a mutual-fund NAV rule
    Given an ETF has a disclosed 0.08% median bid-ask spread
    And a mutual fund deals at end-of-day NAV with a redemption restriction
    When their respective research summaries are requested
    Then each retains its own trading or redemption characteristics
    And no shared liquidity score is invented

  Scenario: Tax distributions are observations not investor liabilities
    Given a fund reports a 0.40 USD-per-share capital gain distribution
    When its tax evidence is summarized
    Then the historical distribution and source date are shown
    And no investor tax bill or after-tax return is calculated

  Scenario: Absence of distributions does not establish tax efficiency
    Given a partial research run finds no distribution history
    When its summary is requested
    Then the distribution history is unavailable
    And the fund is not labeled tax-free or tax-efficient by default

  Scenario: Preview does not create a selected ledger
    Given a valid fictional ETF diligence package
    When it is validated and previewed
    Then no persistent research database is created

  Scenario: Accepting equivalent fund evidence is idempotent
    Given one accepted fictional fund research package
    When reordered but otherwise equivalent evidence is accepted again
    Then no duplicate historical run is created
    And a genuine correction creates a separate immutable run

  Scenario: A rejected citation cannot partially persist
    Given a fund package contains an invalid same-run source reference
    When acceptance is attempted
    Then no fund profile, holding, metric or finding is saved

  Scenario: Fund research cannot change portfolio investments
    Given accepted household positions and a saved plan
    When separate fund diligence is accepted
    Then positions, cached holdings and planning freshness are unchanged

  Scenario: Historical fund reports are read-only
    Given one accepted fictional fund research package
    When its historical details and reports are read
    Then the accepted ledger bytes remain unchanged
