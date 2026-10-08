"""One JSON CLI; human confirmation remains explicit."""
import json
import sys
from pathlib import Path
import typer
from pydantic import ValidationError
from invest.config import database_path
from invest.ledger import Ledger
from invest.models import DomainError
from invest.parsers.generic import parse_html
app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)
portfolio = typer.Typer()
app.add_typer(portfolio, name='portfolio')

def emit(call):
    try:
        result = call()
        print(json.dumps(result, default=str))
    except DomainError as exc:
        print(json.dumps({'error': str(exc)}), file=sys.stderr)
        raise typer.Exit(exc.code)
    except (ValueError, KeyError, OSError, ValidationError) as exc:
        print(json.dumps({'error': str(exc)}), file=sys.stderr)
        raise typer.Exit(1)
    except Exception:
        print(json.dumps({'error': 'Internal error'}), file=sys.stderr)
        raise typer.Exit(4)

def read_json(path):
    return json.loads(sys.stdin.read() if path == '-' else Path(path).read_text())

def ledger():
    return Ledger(database_path())

@portfolio.command('import')
def import_page(file: str, account: str = typer.Option(...), institution: str = 'generic', tax_status: str = 'TAXABLE'):
    emit(lambda: parse_html(sys.stdin.read() if file == '-' else Path(file).read_text(), account, institution, tax_status))

@portfolio.command()
def reconcile(file: str):
    emit(lambda: ledger().reconcile(read_json(file)))

@portfolio.command()
def apply(file: str):
    emit(lambda: ledger().apply(read_json(file)))

@portfolio.command()
def summary():
    emit(lambda: ledger().summary())

@portfolio.command('record-activity')
def record_activity(file: str, yes: bool = False):
    emit(lambda: ledger().record_activity(read_json(file), yes=yes))
