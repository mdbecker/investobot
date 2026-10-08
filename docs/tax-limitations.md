# Tax analysis boundaries

This software is analytical tooling, not tax preparation. It never places trades or adjusts imported broker basis. Broker-provided basis remains authoritative; missing basis or lot detail produces `INSUFFICIENT_DATA` rather than a guessed value.

Monetary calculations use Decimal. A lot's stored cost basis applies to its original quantity; remaining and proposed-sale basis are proportional to that original quantity. Long-term classification requires a sale later than the acquisition's one-year anniversary. Exact sale fees, capital-loss deduction limits, carryforwards, bracket changes and filing-specific rules are outside these estimates.

Supported selection methods are FIFO, LIFO, HIFO, explicit ordered SPECIFIC lot IDs and MIN_TAX. MIN_TAX requires ordinary-income and long-term capital-gains rates; it sorts available lots by estimated current tax effect per share. Optional NIIT and state rates add to each term's rate. Negative estimated tax effect represents the rate-based effect of a loss, not guaranteed usable tax savings. Absent rates yield gains/losses without invented tax-dollar estimates.

Wash-sale checks examine known same-security BUY activity and dated lots across all loaded household accounts, including Traditional and Roth IRAs, within the inclusive 30 days before and after a proposed loss sale. Results identify potential conflicts, insufficient history, or no known conflict. They do not determine whether different securities are legally substantially identical, infer complete histories from account snapshots, allocate disallowed losses, or alter basis. Future household activity and unknown outside accounts or spouse activity can change actual tax treatment. `history_complete` is an explicit assertion about loaded activity, not a guarantee that future transactions will not occur.

Harvesting candidates are taxable lots with known basis, known current price and an unrealized loss. Candidates are analytical facts, not trade recommendations. Valuations use ledger snapshots and disclose their dates; the tax module does not retrieve current market prices.
