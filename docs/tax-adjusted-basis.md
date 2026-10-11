# Remaining adjusted tax basis

Public `tax lots`, `tax analyze` and harvest candidates use accepted
`remaining_adjusted_basis` for the remaining lot quantity. Original acquisition
basis is optional and does not override adjusted basis. For example, ten shares
with original basis 1000 and documented remaining basis 800 have current basis
800; a two-share sale removes 160 before applying its allocated fee.

Legacy lots with only original basis retain proportional accounting. A candidate
explicitly marked `REVIEW_REQUIRED` for unknown basis semantics cannot use that
fallback. Missing or negative adjusted basis, unavailable acquisition dates or
contradictory lot quantities keep definitive taxable estimates unavailable.

Read-only calculations preserve supplied decimal precision and remove the entire
remaining basis on a final-lot sale. Partial estimates allocate remaining basis
by the selected quantity; confirmed accounting persists the exact removed basis
and remaining residue. Fees reduce proceeds separately from gross prices. Tax
rates and household wash-sale evidence remain independent requirements; this
basis calculation cannot establish legal treatment or guaranteed savings.
