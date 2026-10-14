"""Local read-only viewer of accepted facts and persisted analytical results."""

import json
import os
from datetime import date
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from pydantic import ValidationError

from invest.models import DomainError

STATIC = Path(__file__).parent / "static"


def overview(ledger):
    """Read accepted balances, coverage and targets using shared domain calculations."""
    from invest import tax
    from invest.portfolio_research_inputs import exposure_report
    from invest.targets import list_targets

    targets = list_targets(ledger)["targets"]
    active = next((t for t in targets if t["status"] == "ACTIVE"), None)
    state = ledger.state()
    summary = ledger.summary()
    exposure = exposure_report(ledger, state=state)
    latest = {}
    for snapshot in state["snapshots"]:
        account_id = snapshot["account"]["id"]
        if account_id not in latest or snapshot["imported_at"] > latest[account_id]["imported_at"]:
            latest[account_id] = snapshot
    return dict(summary=summary, state=state, active_target=active,
        target_diff=_target_diff(ledger, active["id"]) if active else None,
        exposure=exposure,
        tax_lots=tax.lots(state, date.today().isoformat()),
        data_freshness=[dict(account_id=a, source_timestamp=s.get("source_timestamp"),
            imported_at=s.get("imported_at"), positions_complete=s.get("positions_complete", False),
            lots_complete=s.get("lots_complete", False), cash_known=s.get("cash_known", False))
            for a, s in sorted(latest.items())])


def _target_diff(ledger, target_id, version=None):
    """Keep saved target evidence viewable when accepted valuation coverage is incomplete."""
    from invest import targets

    summary = ledger.summary()
    if summary['total_value'] is None:
        target = targets.show(ledger, target_id, version=version)
        return dict(status='UNAVAILABLE', target_id=target_id, target_version=target['version'],
            target_version_id=target['version_id'], currency=summary['currency'], total_value=None,
            allocations=[], issues=summary['issues'], proposes_trades=False,
            warnings=summary['warnings'] + [
                'Target drift requires complete accepted valuation and cash coverage'])
    return targets.diff(ledger, target_id, version=version)


def _get_api(ledger, path, query):
    from invest import backtest, plans, targets
    from invest.reports import render

    if path == "/api/overview":
        return overview(ledger)
    if path == '/api/check':
        from invest.readiness import check

        return check(ledger.planning_state(), as_of=query['as_of'][0])
    if path == '/api/performance':
        from invest.performance_ledger import report

        return report(ledger.connection, from_date=query.get('from', [None])[0],
                      to_date=query.get('to', [None])[0], as_of=query.get('as_of', [None])[0],
                      account_id=query.get('account', [None])[0])
    if path == '/api/search':
        from invest.search import search

        return search(ledger.path, query=query.get('query', [''])[0],
                      issuer_id=query.get('issuer', [None])[0],
                      date_from=query.get('from', [None])[0], date_to=query.get('to', [None])[0],
                      top_k=int(query.get('top_k', ['10'])[0]))
    if path == "/api/summary":
        return ledger.summary()
    if path == "/api/state":
        return ledger.state()
    if path == "/api/targets":
        return targets.list_targets(ledger)
    if path == "/api/plans":
        return plans.list_plans(ledger)
    if path == '/api/backtests':
        fields = ('id', 'start', 'end', 'status', 'created_at', 'total_return',
                  'annualized_return', 'volatility', 'max_drawdown', 'final_value', 'turnover')
        projection = ','.join(f"json_extract(result_json, '$.{field}')" for field in fields)
        return {'runs': [dict(zip(fields, row)) for row in ledger.connection.execute(
            f'SELECT {projection} FROM backtest_runs ORDER BY created_at DESC,id')]}
    if path == '/api/backtests/compare':
        return backtest.compare(ledger, query.get('run_id', []))
    parts = path.strip("/").split("/")
    if len(parts) == 3 and parts[:2] == ['api', 'backtests']:
        row = ledger.connection.execute('SELECT result_json FROM backtest_runs WHERE id=?',
                                        (parts[2],)).fetchone()
        if row is None:
            raise DomainError('Backtest does not exist')
        return json.loads(row[0])
    version = int(query["version"][0]) if "version" in query else None
    if len(parts) in {3, 4} and parts[:2] == ["api", "targets"]:
        if len(parts) == 3:
            return targets.show(ledger, parts[2], version=version)
        if parts[3] == "diff":
            return _target_diff(ledger, parts[2], version=version)
    if len(parts) in {3, 4} and parts[:2] == ["api", "plans"]:
        if len(parts) == 3:
            return plans.show(ledger, parts[2])
        if parts[3] == "report":
            format = query.get("format", ["markdown"])[0]
            plan = plans.persisted(ledger, parts[2])
            content = render(plan, format).encode()
            content_type = "application/json; charset=utf-8" if format == "json" else "text/markdown; charset=utf-8"
            return (content, content_type, f"plan-{plan['id']}.{'json' if format == 'json' else 'md'}")
    raise DomainError("Route not found", 1)


def create_server(db_path, host="127.0.0.1", port=8765, *, docker_internal=False):
    """Create a local viewer; Docker publishes its internal listener to loopback only."""
    if host not in {'127.0.0.1', 'localhost', '::1'}:
        if not (docker_internal and host == '0.0.0.0' and Path('/.dockerenv').is_file()):
            raise DomainError('Native dashboard must bind to loopback', 3)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass  # Account identifiers never enter access logs.

        def reply(self, status, value, content_type="application/json", download_name=None):
            body = json.dumps(value, default=str).encode() if content_type == "application/json" else value
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            if status == 405:
                self.send_header('Allow', 'GET')
            if download_name:
                self.send_header("Content-Disposition", f'attachment; filename="{download_name}"')
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy",
                "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(body)

        def local_request(self):
            try:
                host_url = urlsplit("http://" + self.headers.get("Host", ""))
                allowed = host_url.hostname in {"localhost", "127.0.0.1", "::1"}
                allowed = allowed and host_url.port == self.server.server_port
            except ValueError:
                allowed = False
            if not allowed:
                self.reply(403, {"error": "Only local inspection requests are allowed", "code": 1})
            return allowed

        def do_GET(self):
            if not self.local_request():
                return
            parsed = urlsplit(self.path)
            path = unquote(parsed.path)
            if path.startswith("/api/"):
                try:
                    from invest.research_identity import read_ledger

                    with read_ledger(db_path) as ledger:
                        ledger.connection.execute('PRAGMA query_only=ON')
                        result = _get_api(ledger, path, parse_qs(parsed.query))
                    if isinstance(result, tuple):
                        self.reply(200, result[0], result[1], download_name=result[2])
                    else:
                        self.reply(200, result)
                except DomainError as error:
                    status = 404 if str(error) == "Route not found" else 409 if error.code == 3 else 400
                    self.reply(status, {"error": str(error), "code": error.code})
                except (ValueError, KeyError, TypeError, ValidationError):
                    self.reply(400, {"error": "Invalid request parameters", "code": 1})
                except Exception:
                    self.reply(500, {"error": "Internal inspection error", "code": 4})
                return
            files = {"/": ("index.html", "text/html; charset=utf-8"),
                     "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                     "/style.css": ("style.css", "text/css; charset=utf-8")}
            item = files.get(path)
            if item:
                self.reply(200, (STATIC / item[0]).read_bytes(), item[1])
            else:
                self.reply(404, {"error": "Route not found", "code": 1})

        def do_POST(self):
            self.reply(405, {"error": "Dashboard is read-only; use the reviewed CLI workflow", "code": 1})

    return HTTPServer((host, port), Handler)


def main():
    from invest.config import database_path

    path = os.environ.get("INVEST_DB") or database_path()
    server = create_server(path, host=os.environ.get("INVEST_BIND", "127.0.0.1"),
                           docker_internal=os.environ.get('INVEST_DOCKER_INTERNAL') == '1')
    print(json.dumps({"status": "RUNNING", "url": "http://localhost:8765"}), flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
