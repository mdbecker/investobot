# Trading policies and conservative proposals

Targets describe desired household weights. Separately approved immutable trading
policies describe eligible account/security buy, sell and hold permissions,
execution increments, cash floors, minimum notionals, source environment, tax
allowance and trading calendar. Approval previews write nothing; explicit policy
confirmation saves a version. A conflicting repeat ID fails rather than replacing
an approved policy. Production proposals resolve a saved policy ID.

Use `invest policy approve --file reviewed-policy.json` to preview, then repeat
with `--confirm` after human review. `invest policy list` returns compact saved
versions; `invest policy show POLICY_ID` retrieves the exact approved payload.
Run these commands through the Docker CLI described in the quickstart.
The JSON requires `version`, `source`, `data_environment` and `permissions`.
Each canonical account/security permission requires independent JSON booleans
`can_buy`, `can_sell`, `can_hold` and an exact positive string `share_increment`.
Financial amounts use decimal strings, never floating-point JSON numbers.
Unknown accounts/securities are rejected; approval cannot create identities.

Direct dictionary policies are supported only for synthetic domain previews and
are clearly marked for review. They never become evidence of human approval.
Permissions require JSON booleans. Missing cash, execution precision, position
freshness or provenance blocks a calculable proposal. Unknown actual fees remain
unknown: a zero hypothetical fee assumption requires manual review.

Contribution-only mode proposes purchases against confirmed same-account cash and
underweights. It never sells or transfers cash to fund purchases. Rebalancing
checks remaining drift after cash-first purchases and permits sales only during
March, June, September or December above the approved five-percentage-point
threshold. A separately confirmed policy can save a reasoned exception window.
Confirmed purchases/sales consume monthly cadence; unconfirmed saved plans do not.

Buy and sell permissions are independent. Explicit share increments, cash floors,
minimum notionals and excluded positions remain binding. Automatic proposals
support stocks, ETFs and mutual funds; individual bonds require explicit scenarios.
The deterministic process uses stable canonical account/security/lot ordering,
prioritizes cash-funded purchases and does not claim global optimization.

Taxable sales require reconciled verified whole-position lots and known acquisition
basis. HIFO chooses highest known adjusted basis per remaining share, with stable
lot-ID ties. Positive estimated term-specific tax cost consumes remaining annual
USD allowance derived from confirmed sales. Losses do not replenish that allowance;
saved proposals do not consume it. Unknown coverage blocks taxable sales while safe
cash-only proposals can remain available for human review.

Every saved plan pins its actual baseline, target/policy version, explicit scenario
prices, assumptions, ordered actions, exact lot selections and canonical simulation.
Hypothetical prices revalue only a disposable scenario baseline; accepted quantities
and marks remain unchanged. The authoritative simulator checks cash and household
value before persistence. Plan list/show calculate current staleness separately;
historical actions and reports remain immutable. No proposal places a trade.
