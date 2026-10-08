"""One JSON CLI; human confirmation remains explicit."""

import json
import sys
from pathlib import Path

import typer
from pydantic import ValidationError
from typer._click.exceptions import UsageError
from typer.core import TyperGroup

from invest.config import database_path
from invest.ledger import Ledger
from invest.models import DomainError
from invest.parsers.generic import parse_html


class JsonGroup(TyperGroup):
    def main(self, *args, **kwargs):
        kwargs["standalone_mode"] = False
        try:
            result = super().main(*args, **kwargs)
        except UsageError as exc:
            print(json.dumps({"error": exc.format_message()}), file=sys.stderr)
            raise SystemExit(1)
        if isinstance(result, int) and result:
            raise SystemExit(result)
        return result


app = typer.Typer(cls=JsonGroup, no_args_is_help=True, pretty_exceptions_enable=False)
portfolio = typer.Typer()
app.add_typer(portfolio, name="portfolio")


def emit(call):
    try:
        result = call()
        print(json.dumps(result, default=str))
    except DomainError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        raise typer.Exit(exc.code)
    except (ValueError, KeyError, OSError, ValidationError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        raise typer.Exit(1)
    except Exception:
        print(json.dumps({"error": "Internal error"}), file=sys.stderr)
        raise typer.Exit(4)


def read_json(path):
    return json.loads(sys.stdin.read() if path == "-" else Path(path).read_text())


def ledger():
    return Ledger(database_path())


@portfolio.command("import")
def import_page(
    file: str,
    account: str = typer.Option(...),
    institution: str = "generic",
    tax_status: str = "TAXABLE",
):
    emit(
        lambda: parse_html(
            sys.stdin.read() if file == "-" else Path(file).read_text(),
            account,
            institution,
            tax_status,
        )
    )


@portfolio.command()
def reconcile(file: str):
    emit(lambda: ledger().reconcile(read_json(file)))


@portfolio.command()
def apply(file: str):
    emit(lambda: ledger().apply(read_json(file)))


@portfolio.command()
def summary():
    emit(lambda: ledger().summary())


@portfolio.command("record-activity")
def record_activity(file: str, yes: bool = False):
    emit(lambda: ledger().record_activity(read_json(file), yes=yes))


tax = typer.Typer()
fund = typer.Typer()
market = typer.Typer()
security = typer.Typer()
bond = typer.Typer()
for group, name in [
    (tax, "tax"),
    (fund, "fund"),
    (market, "market"),
    (security, "security"),
    (bond, "bond"),
]:
    app.add_typer(group, name=name)


def client():
    import os

    from invest.config import load_config
    from invest.market import MarketClient

    config = load_config()
    return MarketClient(
        ledger(),
        api_key=os.environ.get("FMP_API_KEY") or config.get("fmp", {}).get("api_key"),
        fixture_path=os.environ.get("INVEST_FIXTURES"),
    )


@tax.command("lots")
def tax_lots(as_of: str = typer.Option(None)):
    from datetime import date

    from invest.tax import lots

    emit(lambda: lots(ledger().state(), as_of or date.today().isoformat()))


@tax.command("analyze")
def tax_analyze(
    account: str = typer.Option(...),
    security: str = typer.Option(...),
    quantity: str = typer.Option(...),
    price: str = typer.Option(...),
    sale_date: str = typer.Option(...),
    method: str = "FIFO",
    lot_ids: str = "",
):
    from invest.config import load_config
    from invest.tax import analyze

    emit(
        lambda: analyze(
            ledger().state(),
            account,
            security,
            quantity,
            price,
            sale_date,
            method=method,
            lot_ids=lot_ids.split(",") if lot_ids else None,
            rates=load_config().get("tax"),
        )
    )


@tax.command("harvest-candidates")
def harvest(as_of: str = typer.Option(None)):
    from datetime import date

    from invest.tax import harvest_candidates

    emit(lambda: harvest_candidates(ledger().state(), as_of or date.today().isoformat()))


@fund.command("holdings")
def holdings(ticker: str, refresh: bool = False):
    emit(lambda: client().holdings(ticker, refresh=refresh))


@fund.command("compare")
def fund_compare(a: str, b: str, refresh: bool = False):
    from invest.market import compare

    emit(lambda: compare(client(), a, b, refresh=refresh))


@market.command("history")
def history(ticker: str, refresh: bool = False):
    from invest.analytics import series_metrics

    def result():
        data = client().history(ticker, refresh=refresh)
        data["analytics"] = series_metrics(data["prices"]) if len(data["prices"]) >= 3 else None
        return data

    emit(result)


@portfolio.command("exposure")
def portfolio_exposure(refresh: bool = False):
    from invest.analytics import exposure

    emit(lambda: exposure(ledger().state(), client(), refresh))


@bond.command("analyze")
def bond_analyze(file: str):
    from invest.bonds import analyze

    emit(lambda: analyze(read_json(file)))


@portfolio.command("simulate")
def portfolio_simulate(file: str):
    from invest.config import load_config
    from invest.scenarios import simulate

    emit(
        lambda: simulate(
            ledger().state(), client(), read_json(file), rates=load_config().get("tax")
        )
    )


@portfolio.command("risk")
def portfolio_risk(refresh: bool = False):
    from invest.analytics import risk

    emit(lambda: risk(ledger().state(), client(), refresh))


@security.command("screen")
def security_screen(file: str):
    from invest.discovery import screen

    emit(lambda: screen(client(), read_json(file)))


@fund.command("search")
def fund_search(file: str):
    from invest.discovery import search

    emit(lambda: search(client(), read_json(file)))


@fund.command("replacements")
def replacements(original: str, candidates: list[str] = typer.Argument(...)):
    from invest.discovery import replacements as rank

    emit(lambda: rank(client(), original, candidates))


@app.command("schema")
def schema():
    from invest.models import Snapshot

    emit(
        lambda: {
            "snapshot": Snapshot.model_json_schema(),
            "output_contract": {
                "successful_output": "JSON object",
                "diagnostics": "stderr JSON",
                "exit_codes": {
                    "0": "success",
                    "1": "invalid input",
                    "2": "external data unavailable",
                    "3": "inconsistent portfolio state",
                    "4": "internal error",
                },
            },
        }
    )
