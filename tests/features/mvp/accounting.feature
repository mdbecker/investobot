Feature: Authoritative accounting, actual performance and conservative tax review
  All data are invented, USD, source-dated and stored in disposable SQLite ledgers.

  Scenario: B06 Reject a contradictory position value atomically
    Given accounting case B06 has ten shares priced at 100 but reported value 100
    When its candidate observation is reconciled and accepted
    Then INCONSISTENT_POSITION_VALUE blocks acceptance without changing facts

  Scenario: B07 Preserve confirmed purchases after an older observation
    Given accounting case B07 has an October 9 snapshot and October 10 purchase
    When another October 9 observation arrives on October 11
    Then the purchase survives and the observation is evidence only

  Scenario: B08 Block ambiguous date-only event ordering
    Given accounting case B08 has a trade and same-day date-only observation
    When its candidate observation is reconciled and accepted
    Then AMBIGUOUS_SOURCE_ORDER blocks acceptance without changing facts

  Scenario: B09 Retain omitted inventory and unknown cash
    Given accounting case B09 has two holdings and no accepted cash coverage
    When a partial page omitting the second holding is accepted
    Then both holdings survive and cash remains typed unknown

  Scenario: B10 Preserve broker lot identity and adjusted remaining basis
    Given accounting case B10 has a broker lot after an earlier partial sale
    When a second statement reports four remaining shares and adjusted basis 360
    Then the same broker lot has four shares and remaining adjusted basis 360

  Scenario: B11 Confirmed activity retries are idempotent and conflicts atomic
    Given accounting case B11 has a confirmed ten-dollar deposit
    When identical and conflicting retries use its activity ID
    Then the identical retry is a typed no-op and conflicting retry changes no facts

  Scenario: B12 A purchase does not invent a valuation mark
    Given accounting case B12 has a new purchased security without an accepted mark
    When household summary is requested
    Then its valuation is incomplete with null value and MISSING_VALUATION_MARK

  Scenario: B13 Corporate actions and reinvestment have distinct economic meanings
    Given accounting case B13 has complete reinvestment split and return-of-capital evidence
    When those three events are confirmed
    Then quantity basis and cash preserve event meanings without external deposits

  Scenario: B14 Strong identity conflicts cannot merge common ticker aliases
    Given accounting case B14 has conflicting strong identities for ticker SAME
    When its candidate observation is reconciled and accepted
    Then SECURITY_IDENTITY_CONFLICT blocks acceptance without changing facts

  Scenario: B15 Summary tables are not extra holdings
    Given accounting case B15 has a position table and an ambiguous summary total table
    When the fictional HTML is parsed
    Then only the actual holding is proposed and ambiguous summary is typed review required

  Scenario: B20 Exact flow-boundary TWR is 21 percent
    Given accounting case B20 has values 1000 then 1100 before a 100 deposit then 1200 then 1320
    When actual performance is requested for the fixed observation interval
    Then actual time weighted return is exactly 0.21

  Scenario: B21 XIRR uses actual days and is money weighted
    Given accounting case B21 has 1000 invested for 365 days and closing value 1100
    When actual performance is requested for the fixed observation interval
    Then XIRR satisfies the 365.25-day equation and is labeled money weighted

  Scenario: B22 Paired household transfers are not investor contributions
    Given accounting case B22 has a verified paired 200 interaccount transfer
    When actual performance is requested for the fixed observation interval
    Then household external contributions are zero

  Scenario: B23 Reinvestment is not an investor deposit
    Given accounting case B23 has a 50 internally reinvested dividend
    When actual performance is requested for the fixed observation interval
    Then household external contributions are zero and return includes the dividend once

  Scenario: B24 Missing deposit-boundary valuation makes TWR unavailable
    Given accounting case B24 has a deposit without a boundary valuation
    When actual performance is requested for the fixed observation interval
    Then TWR is unavailable with the precise missing boundary date

  Scenario: B25 Current-weight historical risk is hypothetical
    Given accounting case B25 has current weights and fictional daily price history
    When the current-weight historical risk report is requested
    Then the report explicitly identifies hypothetical current allocation and excludes realized CAGR

  Scenario: B26 Confirmed gains consume annual positive-tax headroom
    Given accounting case B26 has a 500 annual allowance and 200 confirmed positive tax cost
    When a proposed additional 400 tax cost is assessed
    Then remaining headroom is 300 and the sale is blocked by annual tax budget

  Scenario: B27 Saved proposals do not consume annual allowance
    Given accounting case B27 has two unexecuted sale proposals and a 500 annual allowance
    When yearly tax budget is requested
    Then the remaining headroom is 500 and proposed consumption is zero

  Scenario: B28 Household IRA acquisitions trigger loss-sale review
    Given accounting case B28 has a loss sale and an IRA purchase twenty days earlier
    When household harvest review is requested
    Then the IRA conflict is cited and no guaranteed tax savings are reported

  Scenario: B29 Missing outside-account history cannot establish legal safety
    Given accounting case B29 has unknown spouse history and an unverified replacement
    When household harvest review is requested
    Then legal review remains required and no replacement is certified wash-sale safe

  Scenario: B30 Specific-lot sale conserves remaining adjusted basis
    Given accounting case B30 has four remaining shares with adjusted remaining basis 360
    When one share is sold from that explicit broker lot
    Then remaining quantity is three and remaining adjusted basis is 270

  Scenario: AC01 Source displayed precision determines rounding tolerance
    Given extended accounting case AC01 has a rounded position discrepancy within its displayed precision
    When its new accounting boundary is exercised
    Then its rounding discrepancy and tolerance are explicitly reported without rewriting evidence

  Scenario: AC02 Unknown displayed price precision blocks acceptance
    Given extended accounting case AC02 has an otherwise consistent position with unknown displayed precision
    When its new accounting boundary is exercised
    Then UNKNOWN_PRICE_PRECISION blocks observation acceptance

  Scenario: AC03 Invalid source timestamps are rejected before persistence
    Given extended accounting case AC03 has an invalid source timestamp
    When its new accounting boundary is exercised
    Then the source timestamp is rejected by the strict observation model

  Scenario: AC04 Unknown observation fields do not disappear silently
    Given extended accounting case AC04 has an unknown observation field
    When its new accounting boundary is exercised
    Then the unknown field is rejected by the strict observation model

  Scenario: AC05 Domain provenance does not borrow freshness from another balance
    Given extended accounting case AC05 has fresh positions old lots and unknown cash provenance
    When its new accounting boundary is exercised
    Then positions lots and cash retain distinct source dates and coverage

  Scenario: AC06 Unvalidated institution adapters require human review
    Given extended accounting case AC06 has invented Vanguard HTML without reviewed institution fixtures
    When its new accounting boundary is exercised
    Then the adapter is provisional and human review is required

  Scenario: AC07 Parser preserves cell provenance without storing raw pages
    Given extended accounting case AC07 has an invented page containing a private irrelevant text marker
    When its new accounting boundary is exercised
    Then financial cells have provenance and the private page text is absent from SQLite

  Scenario: AC08 Mutable rows cannot become automatically saleable tax lots
    Given extended accounting case AC08 has a lot row without a broker ID or reviewed acquisition reference
    When its new accounting boundary is exercised
    Then the unmatched lot is unresolved and cannot support a specific lot sale

  Scenario: AC09 Later full snapshots cannot silently overwrite event discrepancies
    Given extended accounting case AC09 has a confirmed purchase followed by a contradictory full checkpoint
    When its new accounting boundary is exercised
    Then CONFIRMED_EVENT_DISCREPANCY prevents replacing balances

  Scenario: AC10 Preflight is typed and read only
    Given extended accounting case AC10 has a known holding but unknown account cash coverage
    When its new accounting boundary is exercised
    Then preflight returns UNKNOWN_CASH_COVERAGE and a next human action without mutation

  Scenario: AC11 Final specific lot sale removes exact adjusted basis residue
    Given extended accounting case AC11 has three shares and one cent remaining adjusted basis
    When its new accounting boundary is exercised
    Then final lot quantity and adjusted basis are exactly zero

  Scenario: AP01 Partial valuation invalidates its actual return interval
    Given extended accounting case AP01 has a partial terminal valuation
    When its new accounting boundary is exercised
    Then actual returns are unavailable with PARTIAL_VALUATION_CHECKPOINT

  Scenario: AP02 Missing cash flow coverage cannot fabricate actual returns
    Given extended accounting case AP02 has unknown cash flow history coverage
    When its new accounting boundary is exercised
    Then actual returns are unavailable with INCOMPLETE_CASH_FLOW_HISTORY

  Scenario: AP03 Multiple XIRR roots are unavailable rather than a selected favorable root
    Given extended accounting case AP03 has investor cash flows with two positive XIRR roots
    When its new accounting boundary is exercised
    Then XIRR is null and MULTIPLE_XIRR_ROOTS is reported

  Scenario: AP04 XIRR without a cash flow sign change is unavailable
    Given extended accounting case AP04 has cash flows without a valid XIRR root
    When its new accounting boundary is exercised
    Then XIRR is null and NO_XIRR_ROOT is reported

  Scenario: AP05 Actual CAGR uses supported duration and linked TWR
    Given extended accounting case AP05 has a supported 365-day ten percent linked return
    When its new accounting boundary is exercised
    Then actual CAGR follows the declared 365.25-day annualization equation

  Scenario: AP06 Total actual loss annualizes to minus one
    Given extended accounting case AP06 has a complete positive-duration total loss
    When its new accounting boundary is exercised
    Then actual TWR and CAGR are both exactly minus one

  Scenario: AT01 Two monthly confirmed sales share one annual allowance
    Given extended accounting case AT01 has two confirmed monthly taxable gain sales
    When its new accounting boundary is exercised
    Then annual consumption sums both sales and the remaining allowance is 460

  Scenario: AT02 Realized losses cannot replenish conservative tax allowance
    Given extended accounting case AT02 has a confirmed gain sale followed by a larger loss sale
    When its new accounting boundary is exercised
    Then positive tax consumption remains 20 and signed net gain remains negative

  Scenario: AT03 Positive short and long term gains use separate marginal rates
    Given extended accounting case AT03 has one short term and one long term confirmed gain
    When its new accounting boundary is exercised
    Then annual positive tax consumption is 60 with separate term rates

  Scenario: AT04 Unknown marginal rates block gain realization without blocking cash purchases
    Given extended accounting case AT04 has an unknown long term marginal rate
    When its new accounting boundary is exercised
    Then UNKNOWN_TAX_RATE blocks the gain sale but does not block a cash only proposal

  Scenario: AT05 Non USD tax units cannot enter household allowance math
    Given extended accounting case AT05 has a EUR tax policy without an FX model
    When its new accounting boundary is exercised
    Then UNSUPPORTED_TAX_CURRENCY blocks tax budget calculation

  Scenario: AT06 Exactly thirty days before a loss sale remains in the wash window
    Given extended accounting case AT06 has an IRA acquisition exactly thirty days before the loss sale
    When its new accounting boundary is exercised
    Then the boundary acquisition is included as a household conflict

  Scenario: AT07 Thirty one days before is outside the inspected window
    Given extended accounting case AT07 has an IRA acquisition thirty one days before the loss sale
    When its new accounting boundary is exercised
    Then the old acquisition is excluded without certifying legal safety
