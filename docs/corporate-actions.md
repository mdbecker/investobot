# Reviewed corporate actions

Confirm an activity only after reviewing its original notice, account, security,
date and amounts. Activity IDs are idempotent; conflicting repeats fail atomically.

`DIVIDEND_REINVESTMENT` requires gross amount, acquired quantity, gross price and
fee. Gross amount must equal quantity times price. Reinvestment creates an
acquisition with basis including the fee; cash changes only by the fee. It is
not an external deposit. Derived acquisition references preserve confirmed
activity provenance but do not invent verified broker lot IDs or sale permission.

`STOCK_SPLIT` requires an explicit positive ratio. It scales original and remaining
lot quantities while retaining IDs, acquisition dates and basis. Prior total
valuation and its source timestamp remain unchanged. The adjusted unit price is
retained only when exactly representable as a decimal; a split is not a new quote.

`RETURN_OF_CAPITAL` needs complete remaining lot coverage and known adjusted basis.
It reduces each active lot's basis in proportion to remaining shares, assigns
the exact final residue, and increases cash by the reviewed distribution. Original
acquisition basis remains historical evidence. Unknown basis or a distribution
exceeding any lot's basis blocks acceptance for manual treatment; Investobot does
not invent a taxable gain or negative basis.

All related accepted changes share a transaction. These operations do not establish
complete household transaction history or certify any tax result.
