# Fund look-through

Recursive exposure is a read-only calculation over canonical accepted positions and
pinned fund observations. Observation weights are fractions, not percentages. The
calculation preserves every account and fund contribution path, source dates and
unknown residual; a partially disclosed fund is never normalized to 100%.

The default decision freshness limit is 120 calendar days. Missing dates, stale
holdings, future observations/publications, cycles and recursion beyond eight fund
levels leave their full affected value unresolved. Currency differences require a
verified FX model and otherwise block aggregation. Cash remains visible.

Companies aggregate only through explicitly verified issuer identities. Names and
tickers alone cannot establish issuer equivalence. Missing issuer evidence remains
an unresolved issuer amount, separately from unknown constituent amounts.

`research_universe` selects verified operating companies by descending exposure,
then canonical issuer ID. The default minimum is 1% of the entire known household
value, including cash. It returns fewer than the requested count when fewer qualify
and reports unknown, stale, unresolved and filtered exposure separately. Adapters
must preserve these coverage fields when freezing a research manifest; research of
the selected companies does not establish whole-portfolio coverage.

The domain functions accept `state`, observations keyed by canonical security ID,
and an explicit reporting date. A fund observation contains `as_of`, `currency`,
`holdings` with `security_id` and fractional `weight`, plus supplied source metadata.
Operating-company rows require reviewed `issuer_id` and `issuer_verified=true`.
Provider ticker rows must be resolved before calculation. These functions do not
fetch data, create identities, write caches, or certify original source truth.
