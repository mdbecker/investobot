Feature: One source-aware recursive household exposure
  Scenario Outline: Numeric amounts and source identity remain independent
    Given synthetic household exposure evidence for "<case>"
    When household exposure is calculated without changing its evidence
    Then exposure satisfies "<case>" coverage and identity rules

    Examples:
      | case                   |
      | observed partial       |
      | verified nested issuer |
      | equal source tickers   |
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
