# Input and output contracts

`invest tools list`, `invest tools describe COMMAND` and `invest schema` expose
registered flags, strict JSON schemas and actual persistent mutation scopes.
Successful results are JSON stdout. Errors are JSON stderr: code 1 invalid input,
2 unavailable external data, 3 inconsistent/blocked state, 4 internal error.
Incomplete analyses return structured outcomes with explicit typed issues.

Financial amounts use exact decimal strings. Identifiers retain literal source
identity, including leading zeros. Source timestamps and import timestamps are
different facts. Positions, lots and cash carry independent coverage/freshness;
unknown cash is never zero. Displayed source precision is required for validating
quantity/price/value rounding. Raw broker HTML is never persisted.

Confirmations are explicit and idempotent. Reusing a confirmed ID with different
facts fails atomically. Later observations cannot erase confirmed events; partial
observations cannot delete unseen inventory. Trading policies and targets are
separate immutable versions. A saved plan pins baseline, prices, policy, dataset
and algorithm; later actual changes make it stale without rewriting history.

Research uses strict specialty packages or the shared immutable envelope, with
trusted skill identity, source locators, environment and permissions. Structural
validation does not prove source truth or rights. Search retains hashes, citation
dates and offsets; vectors require explicit compatible model/dimension metadata.
See [research](portfolio-research.md), [search](search.md) and [trading policy](trading-policy.md).
