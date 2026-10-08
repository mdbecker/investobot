# Local inspection site

The inspection site is a thin view over the same SQLite ledger used by `invest`.
It is included at the user's request as an explicit exception to the original
PRD's GUI and Docker runtime exclusions. It runs without a second service,
JavaScript build system, telemetry, account authentication, or trading access.

Start with `docker compose up --build -d` and open <http://localhost:8765>.
The port is published only on host loopback. Do not change that binding to a
public interface: this is a single-user inspection tool, not a hosted app.
Persisted normalized state lives in the Docker data volume. Stop with
`docker compose down`; do not add `--volumes` unless you intend to delete state.

## Import and acceptance

1. Choose a synthetic account alias, provisional institution profile, tax
   status, and known snapshot date. Do not enter account numbers or credentials.
2. Paste copied HTML or open a locally saved HTML file. Raw HTML is read into
   memory only, cleared from the browser textarea after preview, and never
   written to SQLite or server logs. Delete your own saved file if desired.
3. Click **Preview import**. Review positions, cash-known status, lots, and
   warnings in the normalized JSON. A preview does not update the ledger.
4. Click **Compare with ledger** and review state differences. The tool does
   not infer trades from changed quantities.
5. Check the acceptance box and click **Accept snapshot into ledger** only
   when values match the known account state.

Vanguard, Fidelity/NetBenefits, and PNC aliases are provisional common-table
profiles. They have not been validated against real account pages. Missing or
ambiguous fields produce warnings; absent cost basis and asset classification
are never invented. No balances are preloaded or presented as real holdings.

## Manually executed activities

Use the activity JSON editor for an activity you executed yourself. Preview
first, review the cash/state effect, then explicitly confirm. The editor does
not execute trades. For more analysis, use the documented CLI commands.

## Local API

`GET /api/summary` and `GET /api/state` inspect the ledger. JSON POST endpoints
are `/api/import` (HTML plus synthetic alias/profile/tax status),
`/api/reconcile` (normalized `snapshot`), `/api/apply` (`snapshot` and explicit
`confirm: true`), and `/api/activity` (`activity`, optional `confirm: true`).
Requests require local Host headers and POSTs require a matching Origin.
Bodies larger than 2 MB are rejected. Responses use the CLI domain error-code
convention inside JSON; invalid requests return HTTP 400, inconsistent state
409, and internal failures 500. Security rejections return 403.
