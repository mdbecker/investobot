"""Thin local inspection surface over the canonical ledger, without account authentication."""

import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import ValidationError

from invest.ledger import Ledger
from invest.models import DomainError
from invest.parsers.generic import parse_html

MAX_BODY = 2_000_000
STATIC = Path(__file__).parent / "static"

ANALYSIS_INPUTS = {
    "exposure": {"refresh"},
    "tax_lots": {"as_of"},
    "tax_analyze": {"account", "security", "quantity", "price", "sale_date", "method", "lot_ids", "fee"},
    "harvest": {"as_of"},
    "simulate": {"actions"},
    "risk": {"refresh"},
    "fund_holdings": {"ticker", "refresh"},
    "fund_compare": {"a", "b", "refresh"},
    "bond_analyze": {"terms"},
}


def analysis(ledger, tool, inputs):
    """A closed set of direct service calls; analysis does not write provider caches."""
    from datetime import date

    from invest import analytics, bonds, market, scenarios, tax
    from invest.config import load_config

    if not isinstance(tool, str) or tool not in ANALYSIS_INPUTS:
        raise DomainError("Unknown analysis tool")
    if not isinstance(inputs, dict) or set(inputs) - ANALYSIS_INPUTS[tool]:
        raise DomainError("Invalid or unsupported analysis input fields")
    if "refresh" in inputs and type(inputs["refresh"]) is not bool:
        raise DomainError("refresh must be a JSON boolean")
    config = load_config()
    client = scenarios.readonly_client(
        market.MarketClient(
            ledger,
            api_key=os.environ.get("FMP_API_KEY") or config.get("fmp", {}).get("api_key"),
            fixture_path=os.environ.get("INVEST_FIXTURES"),
        )
    )
    state = ledger.state()
    refresh = inputs.get("refresh", False)
    as_of = inputs.get("as_of") or date.today().isoformat()
    if tool == "exposure":
        return analytics.exposure(state, client, refresh)
    if tool == "tax_lots":
        return tax.lots(state, as_of)
    if tool == "harvest":
        return tax.harvest_candidates(state, as_of)
    if tool == "tax_analyze":
        return tax.analyze(
            state,
            inputs["account"],
            inputs["security"],
            inputs["quantity"],
            inputs["price"],
            inputs["sale_date"],
            method=inputs.get("method", "FIFO"),
            lot_ids=inputs.get("lot_ids"),
            rates=config.get("tax"),
            fee=inputs.get("fee", "0"),
        )
    if tool == "simulate":
        return scenarios.simulate(state, client, inputs["actions"], rates=config.get("tax"))
    if tool == "risk":
        return analytics.risk(state, client, refresh)
    if tool == "fund_holdings":
        return client.holdings(inputs["ticker"], refresh=refresh)
    if tool == "fund_compare":
        return market.compare(client, inputs["a"], inputs["b"], refresh=refresh)
    return bonds.analyze(inputs["terms"])


def create_server(db_path, host="0.0.0.0", port=8765):
    """Create a single-request-at-a-time local server; Docker publishes to loopback only."""

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass  # Account identifiers, bodies, and imported HTML never enter access logs.

        def reply(self, status, value, content_type="application/json"):
            body = (
                json.dumps(value, default=str).encode()
                if content_type == "application/json"
                else value
            )
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
            )
            self.end_headers()
            self.wfile.write(body)

        def local_request(self, mutation=False):
            host_header = self.headers.get("Host", "")
            try:
                host_url = urlsplit("http://" + host_header)
                allowed = host_url.hostname in {"localhost", "127.0.0.1", "::1"}
                allowed = allowed and host_url.port == self.server.server_port
            except ValueError:
                allowed = False
            if not allowed:
                self.reply(403, {"error": "Only local inspection requests are allowed", "code": 1})
                return False
            if mutation and self.headers.get("Origin") != "http://" + host_header:
                self.reply(403, {"error": "Same-origin requests are required", "code": 1})
                return False
            return True

        def do_GET(self):
            if not self.local_request():
                return
            if self.path in {"/api/summary", "/api/state"}:
                ledger = Ledger(db_path)
                try:
                    self.reply(
                        200, ledger.summary() if self.path.endswith("summary") else ledger.state()
                    )
                except DomainError as error:
                    self.reply(
                        409 if error.code == 3 else 400, {"error": str(error), "code": error.code}
                    )
                except Exception:
                    self.reply(500, {"error": "Internal inspection error", "code": 4})
                finally:
                    ledger.connection.close()
                return
            files = {
                "/": ("index.html", "text/html; charset=utf-8"),
                "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                "/style.css": ("style.css", "text/css; charset=utf-8"),
            }
            item = files.get(self.path)
            if item:
                self.reply(200, (STATIC / item[0]).read_bytes(), item[1])
            else:
                self.reply(404, {"error": "Route not found", "code": 1})

        def do_POST(self):
            if not self.local_request(mutation=True):
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = -1
            if length < 1 or length > MAX_BODY:
                self.reply(
                    413, {"error": "JSON body must be between 1 and 2000000 bytes", "code": 1}
                )
                return
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                self.reply(415, {"error": "Use application/json", "code": 1})
                return
            ledger = None
            try:
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise DomainError("Request must be a JSON object")
                ledger = Ledger(db_path)
                if self.path == "/api/import":
                    if not isinstance(payload.get("html"), str):
                        raise DomainError("Account HTML is required")
                    result = parse_html(
                        payload["html"],
                        account_id=payload["account_id"],
                        institution=payload.get("institution", "generic"),
                        tax_status=payload.get("tax_status", "TAXABLE"),
                        as_of=payload.get("as_of") or None,
                        positions_complete=payload.get("positions_complete", False),
                        lots_complete=payload.get("lots_complete", False),
                    )
                elif self.path == "/api/reconcile":
                    result = ledger.reconcile(payload["snapshot"])
                elif self.path == "/api/apply":
                    if payload.get("confirm") is not True:
                        raise DomainError("Explicit confirmation is required to apply a snapshot")
                    result = ledger.apply(payload["snapshot"], allow_older=payload.get("allow_older") is True, justification=payload.get("justification"))
                elif self.path == "/api/activity":
                    result = ledger.record_activity(
                        payload["activity"], yes=payload.get("confirm") is True
                    )
                elif self.path == "/api/analyze":
                    result = analysis(ledger, payload.get("tool"), payload.get("input", {}))
                else:
                    self.reply(404, {"error": "Route not found", "code": 1})
                    return
                self.reply(200, result)
            except DomainError as error:
                self.reply(
                    409 if error.code == 3 else 400, {"error": str(error), "code": error.code}
                )
            except (ValueError, KeyError, TypeError, ValidationError):
                self.reply(
                    400,
                    {
                        "error": "Invalid request; check required fields and normalized values",
                        "code": 1,
                    },
                )
            except Exception:
                self.reply(500, {"error": "Internal inspection error", "code": 4})
            finally:
                if ledger:
                    ledger.connection.close()

    return HTTPServer((host, port), Handler)


def main():
    from invest.config import database_path

    path = os.environ.get("INVEST_DB") or database_path()
    server = create_server(path)
    print(json.dumps({"status": "RUNNING", "url": "http://localhost:8765"}), flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
