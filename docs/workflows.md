# Human-operated workflows
All commands below run inside Docker with `docker compose run --rm app invest ...`.

## Import and reconciliation
1. Manually sign into Vanguard, Fidelity NetBenefits or PNC in your own browser. This app never receives credentials/cookies.
2. Copy/save the relevant table as HTML. Retain this sensitive file outside Git. Use synthetic account aliases (`taxable`, `roth`, `bank`).
3. `portfolio import /app/local-data/page.html --account taxable --institution vanguard --tax-status TAXABLE` prints a normalized snapshot. Redirect stdout into a JSON file locally.
4. Inspect warnings, quantities, dates, cash and identifiers. No real institution HTML has been validated yet. If table parsing fails, ask for a parser update using an anonymized sample.
5. `portfolio reconcile /app/local-data/snapshot.json` reports state differences, never inferred transactions.
6. `portfolio apply /app/local-data/snapshot.json` explicitly accepts the state and stores a normalized audit record. Subsequent snapshots preserve activity history.

## Tax-loss harvesting
Use `tax lots` then `tax harvest-candidates`; missing basis means insufficient analysis. Analyze a proposed sale with `tax analyze --account taxable --security VTI --quantity 25 --price 200 --sale-date 2026-10-08 --method HIFO`. Optional rates belong in local configuration. Review household acquisition conflicts and missing history; this tool cannot certify wash-sale safety.

## Fund comparisons
Configure FMP yourself; request `fund holdings VTI`, then `fund compare VTI ITOT`. Full available holdings, uncovered weights and original source dates matter more than only the largest positions. A similarity score does not establish tax legality. Use Chrome for qualitative fund research.

## Recording actual activity
Create an activity JSON after you manually execute a trade:

```json
{"account_id":"taxable","type":"BUY","security":"VTI","quantity":"25","price":"142.17","date":"2026-10-08","fee":"0"}
```

`portfolio record-activity /app/local-data/activity.json` previews state; add `--yes` to record it. Known cash and security identity are required. Purchase lots use provided execution cost. For sales, imported broker basis remains authoritative; verify with the next account snapshot.

## Comparing alternatives
```json
[
  {"type":"SELL","account_id":"taxable","security":"AAA","quantity":"5","price":"100","date":"2026-10-08","method":"HIFO"},
  {"type":"BUY","account_id":"taxable","security":"BBB","quantity":"5","price":"100","date":"2026-10-08"}
]
```

These symbols are synthetic fixtures, not recommendations. `portfolio simulate /app/local-data/actions.json` returns before/after cash, allocation, look-through exposure changes, selected lots, ST/LT gains and wash-sale warnings without writing the database (including caches). Compare alternatives and your long-term-gain budget yourself; use Chrome for current research. `portfolio risk` describes historical current-weight behavior. Only after human execution use confirmed activity recording or explicitly apply the next normalized account snapshot.
