Feature: One source-aware recursive household exposure
  Scenario: A sixty percent disclosure preserves the undisclosed remainder
    Given synthetic household exposure evidence for "observed partial"
    When household exposure is calculated without changing its evidence
    Then 600 dollars is attributed to the observed company and 400 dollars remains unknown

  Scenario: Verified issuer identity combines direct and nested fund paths
    Given synthetic household exposure evidence for "verified nested issuer"
    When household exposure is calculated without changing its evidence
    Then one verified issuer has 1000 dollars across two contribution paths

  Scenario: Identical unverified tickers do not establish issuer equivalence
    Given synthetic household exposure evidence for "equal source tickers"
    When household exposure is calculated without changing its evidence
    Then two separate observations retain 2000 dollars of unresolved issuer identity

  Scenario: Missing cash prevents a household denominator
    Given synthetic household exposure evidence for "missing cash"
    When household exposure is calculated without changing its evidence
    Then the known 1000 dollar subtotal has no household total or percentages

  Scenario Outline: Numeric amounts and source identity remain independent
    Given synthetic household exposure evidence for "<case>"
    When household exposure is calculated without changing its evidence
    Then exposure satisfies "<case>" coverage and identity rules

    Examples:
      | case                   |
      | stale holdings         |
      | later publication      |
      | absent holdings        |
      | invalid weights        |
      | missing mark           |
      | cycle                  |
      | depth limit            |
      | exact residues         |

  Scenario: Research selects only verified issuers while keeping unresolved coverage
    Given synthetic household exposure evidence for "research selection"
    When the verified issuer research universe is selected
    Then verified company selection preserves observed unresolved amounts

  Scenario Outline: Partial source evidence cannot become verified household coverage
    Given synthetic household exposure evidence for "<case>"
    When household exposure is calculated without changing its evidence
    Then source uncertainty is preserved for "<case>"

    Examples:
      | case                      |
      | accepted parser issue     |
      | source diagnostic         |
      | provisional issuer        |
      | conflicting issuer        |
      | later observed evidence   |
