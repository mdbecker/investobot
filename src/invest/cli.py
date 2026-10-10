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
    tax_status: str = "OTHER",
    as_of: str = typer.Option(None),
    positions_complete: bool = False,
    lots_complete: bool = False,
):
    emit(
        lambda: parse_html(
            sys.stdin.read() if file == "-" else Path(file).read_text(),
            account,
            institution,
            tax_status,
            as_of=as_of,
            positions_complete=positions_complete,
            lots_complete=lots_complete,
        )
    )


@portfolio.command()
def reconcile(file: str):
    emit(lambda: ledger().reconcile(read_json(file)))


@portfolio.command()
def apply(file: str, allow_older: bool = False, justification: str = typer.Option(None)):
    emit(lambda: ledger().apply(read_json(file), allow_older=allow_older, justification=justification))


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
account = typer.Typer()
bond = typer.Typer()
for group, name in [
    (tax, "tax"),
    (fund, "fund"),
    (market, "market"),
    (security, "security"),
    (account, "account"),
    (bond, "bond"),
]:
    app.add_typer(group, name=name)


@security.command("classify")
def security_classify(security_id: str, asset_type: str = typer.Option(...),
                      source: str = typer.Option(...), confirm: bool = False):
    emit(lambda: ledger().classify_security(security_id, asset_type, source, confirm=confirm))


@account.command("update")
def account_update(account_id: str, file: str = typer.Option(...), yes: bool = False):
    emit(lambda: ledger().update_account(account_id, read_json(file), yes=yes))


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
    fee: str = "0",
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
            fee=fee,
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
    from invest.contracts import schema_contract

    emit(schema_contract)


tools = typer.Typer()
app.add_typer(tools, name="tools")


@tools.command("list")
def tool_list():
    from invest.contracts import tools_list

    emit(tools_list)


@tools.command("describe")
def tool_describe(name: str):
    from invest.contracts import tools_describe

    emit(lambda: tools_describe(name))


@market.command("quote")
def quote(ticker: str, refresh: bool = False):
    emit(lambda: client().quote(ticker, refresh=refresh))


target = typer.Typer()
app.add_typer(target, name="target")


@target.command("save")
def target_save(file: str):
    from invest.targets import save

    emit(lambda: save(ledger(), read_json(file)))


@target.command("list")
def target_list():
    from invest.targets import list_targets

    emit(lambda: list_targets(ledger()))


@target.command("show")
def target_show(target_id: str, version: int = typer.Option(None)):
    from invest.targets import show

    emit(lambda: show(ledger(), target_id, version=version))


@target.command("activate")
def target_activate(target_id: str):
    from invest.targets import activate

    emit(lambda: activate(ledger(), target_id))


@target.command("archive")
def target_archive(target_id: str):
    from invest.targets import archive

    emit(lambda: archive(ledger(), target_id))


@target.command("diff")
def target_diff(target_id: str, version: int = typer.Option(None)):
    from invest.targets import diff

    emit(lambda: diff(ledger(), target_id, version=version))


@security.command("register")
def security_register(file: str):
    emit(lambda: ledger().register_security(read_json(file)))


plan = typer.Typer()
report = typer.Typer()
app.add_typer(plan, name="plan")
app.add_typer(report, name="report")


@plan.command("generate")
def plan_generate(
    target: str = typer.Option(...),
    as_of: str = typer.Option(None),
    prices: str = typer.Option(None),
    name: str = typer.Option(None),
    version: int = typer.Option(None),
):
    from invest.config import load_config
    from invest.plans import generate, plan_summary

    emit(lambda: {'plan': plan_summary(generate(ledger(), client(), target, as_of=as_of,
                          prices=read_json(prices) if prices else None, name=name,
                          rates=load_config().get("tax"), version=version))})


@plan.command("list")
def plan_list():
    from invest.plans import list_plans

    emit(lambda: list_plans(ledger()))


@plan.command("show")
def plan_show(plan_id: str):
    from invest.plans import show

    emit(lambda: show(ledger(), plan_id))


@plan.command("compare")
def plan_compare(plan_ids: list[str] = typer.Argument(...)):
    from invest.plans import compare

    emit(lambda: compare(ledger(), *plan_ids))


@report.command("export")
def report_export(plan_id: str, output: str = typer.Option(...), format: str = "markdown"):
    from invest.plans import persisted
    from invest.reports import export

    emit(lambda: export(persisted(ledger(), plan_id), output, format=format))


prompt = typer.Typer()
app.add_typer(prompt, name="prompt")


@prompt.command("list")
def prompt_list():
    from invest.prompts import PromptLibrary

    emit(lambda: PromptLibrary().list())


@prompt.command("show")
def prompt_show(prompt_id: str):
    from invest.prompts import PromptLibrary

    emit(lambda: PromptLibrary().show(prompt_id))


@prompt.command("save")
def prompt_save(prompt_id: str, file: str):
    from invest.prompts import PromptLibrary

    emit(lambda: PromptLibrary().save(prompt_id, sys.stdin.read() if file == "-" else Path(file).read_text()))


@prompt.command("delete")
def prompt_delete(prompt_id: str):
    from invest.prompts import PromptLibrary

    emit(lambda: PromptLibrary().delete(prompt_id))


@portfolio.command("overview")
def portfolio_overview():
    from invest.web import overview

    emit(lambda: overview(ledger()))


research = typer.Typer()
political = typer.Typer()
app.add_typer(research, name='research')
research.add_typer(political, name='political')
earnings = typer.Typer()
research.add_typer(earnings, name='earnings')
news = typer.Typer()
research.add_typer(news, name='news')
skills = typer.Typer()
research.add_typer(skills, name='skills')


@skills.command('list')
def research_skills_list():
    from invest.research_skills import list_skills
    emit(list_skills)


@skills.command('show')
def research_skills_show(name: str):
    from invest.research_skills import show_skill
    emit(lambda: show_skill(name))


@skills.command('install')
def research_skills_install(agent: str = typer.Option(...),
                            workspace: str = typer.Option(...), confirm: bool = False):
    from invest.research_skills import install_skills
    emit(lambda: install_skills(agent, workspace, confirm=confirm))


@political.command('validate')
def political_validate(file: str):
    """Validate evidence and independently reviewed permissions without writes."""
    from invest.political_models import PoliticalResearchInput, enforce_policy

    def run():
        model = PoliticalResearchInput.model_validate(read_json(file))
        enforce_policy(model)
        from invest.research_identity import read_ledger, verify_company
        with read_ledger(database_path()) as db:
            verify_company(db, model.company.model_dump(mode='json'))
        return {'valid': True, 'ready': True, 'coverage_status': model.scope.coverage_status,
                'rights_status': model.scope.rights_status,
                'verified_transactions': len(model.contributions),
                'unresolved_match_count': len(model.unresolved_matches),
                'limitations': model.limitations}
    emit(run)


@political.command('import')
def political_import(file: str, yes: bool = False):
    """Preview research; --yes stores it without financial mutations."""
    from invest.political import import_research
    from invest.political_models import PoliticalResearchInput, enforce_policy

    def run():
        model = PoliticalResearchInput.model_validate(read_json(file))
        enforce_policy(model)
        from invest.research_identity import read_ledger
        if not yes:
            with read_ledger(database_path()) as db:
                return import_research(db, model, yes=False)
        db = ledger()
        try:
            return import_research(db, model, yes=yes)
        finally:
            db.connection.close()
    emit(run)


def political_query(operation, *args):
    from invest.research_identity import read_ledger
    with read_ledger(database_path()) as db:
        return operation(db, *args)


@political.command('list')
def political_list(ticker: str = typer.Option(None)):
    from invest.political_queries import list_runs
    emit(lambda: political_query(list_runs, ticker))


@political.command('show')
def political_show(run_id: str):
    from invest.political_queries import show
    emit(lambda: political_query(show, run_id))


@political.command('summary')
def political_summary(run_id: str):
    from invest.political_queries import summary
    emit(lambda: political_query(summary, run_id))


@earnings.command('validate')
def earnings_validate(file: str):
    from invest.earnings import validation_warnings
    from invest.earnings_models import EarningsResearchInput
    from invest.research_identity import read_ledger, verify_company

    def run():
        model = EarningsResearchInput.model_validate(read_json(file))
        data = model.model_dump(mode='json')
        with read_ledger(database_path()) as db:
            verify_company(db, data['company'])
        return {'valid': True, 'coverage_status': model.coverage_status,
                'metric_count': len(model.metrics), 'guidance_count': len(model.guidance),
                'finding_count': len(model.findings), 'warnings': validation_warnings(data)}
    emit(run)


@earnings.command('import')
def earnings_import(file: str, yes: bool = False):
    from invest.earnings import import_research
    from invest.earnings_models import EarningsResearchInput
    from invest.research_identity import read_ledger

    def run():
        model = EarningsResearchInput.model_validate(read_json(file))
        if not yes:
            with read_ledger(database_path()) as db:
                return import_research(db, model, yes=False)
        db = ledger()
        try:
            return import_research(db, model, yes=True)
        finally:
            db.connection.close()
    emit(run)


@earnings.command('list')
def earnings_list(ticker: str = typer.Option(None)):
    from invest.earnings_queries import list_runs
    emit(lambda: political_query(list_runs, ticker))


@earnings.command('show')
def earnings_show(run_id: str):
    from invest.earnings_queries import show
    emit(lambda: political_query(show, run_id))


@earnings.command('summary')
def earnings_summary(run_id: str):
    from invest.earnings_queries import summary
    emit(lambda: political_query(summary, run_id))


@earnings.command('compare')
def earnings_compare(run_a: str, run_b: str):
    from invest.earnings_queries import compare
    emit(lambda: political_query(compare, run_a, run_b))


@news.command('validate')
def news_validate(file: str):
    from invest.news import _verify_event_ownership, validation_warnings
    from invest.news_models import NewsResearchInput
    from invest.research_identity import read_ledger, verify_company

    def run():
        model = NewsResearchInput.model_validate(read_json(file))
        data = model.model_dump(mode='json')
        with read_ledger(database_path()) as db:
            verify_company(db, data['company'])
            _verify_event_ownership(db, data)
        return {'valid': True, 'coverage_status': model.scope.coverage_status,
                'event_count': len(model.events), 'catalyst_count': len(model.catalysts),
                'thesis_count': len(model.theses), 'warnings': validation_warnings(data)}
    emit(run)


@news.command('import')
def news_import(file: str, yes: bool = False):
    from invest.news import import_research
    from invest.news_models import NewsResearchInput
    from invest.research_identity import read_ledger

    def run():
        model = NewsResearchInput.model_validate(read_json(file))
        if not yes:
            with read_ledger(database_path()) as db:
                return import_research(db, model, yes=False)
        db = ledger()
        try:
            return import_research(db, model, yes=True)
        finally:
            db.connection.close()
    emit(run)


@news.command('list')
def news_list(ticker: str = typer.Option(None)):
    from invest.news_queries import list_runs
    emit(lambda: political_query(list_runs, ticker))


@news.command('show')
def news_show(run_id: str):
    from invest.news_queries import show
    emit(lambda: political_query(show, run_id))


@news.command('summary')
def news_summary(run_id: str):
    from invest.news_queries import summary
    emit(lambda: political_query(summary, run_id))


@news.command('context')
def news_context(ticker: str = typer.Option(...)):
    from invest.news_queries import context
    emit(lambda: political_query(context, ticker))


@news.command('compare')
def news_compare(run_old: str, run_new: str):
    from invest.news_queries import compare
    emit(lambda: political_query(compare, run_old, run_new))


@news.command('changes')
def news_changes(ticker: str = typer.Option(...)):
    from invest.news_queries import changes
    emit(lambda: political_query(changes, ticker))
