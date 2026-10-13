"""One JSON CLI; human confirmation remains explicit."""

import json
import sys
from contextlib import closing
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
policy = typer.Typer()
app.add_typer(policy, name='policy')


@policy.command('approve')
def policy_approve(file: str = typer.Option(...), confirm: bool = False):
    from invest.planning import save_policy
    from invest.policy_models import TradingPolicyInput
    from invest.research_identity import read_ledger

    def result():
        payload = TradingPolicyInput.model_validate(read_json(file)).model_dump(mode='json', exclude_unset=True)
        with read_ledger(database_path()) as selected:
            preview = save_policy(selected, payload)
        if not confirm:
            return preview
        selected = ledger()
        with closing(selected.connection):
            return save_policy(selected, payload, confirm=True)
    emit(result)


@policy.command('list')
def policy_list():
    from invest.planning import list_policies
    from invest.research_identity import read_ledger

    def result():
        with read_ledger(database_path()) as selected:
            return list_policies(selected)
    emit(result)


@policy.command('show')
def policy_show(policy_id: str):
    from invest.planning import get_policy
    from invest.research_identity import read_ledger

    def result():
        with read_ledger(database_path()) as selected:
            return get_policy(selected, policy_id)
    emit(result)


def emit(call):
    try:
        result = call()
        print(json.dumps(result, default=str))
    except DomainError as exc:
        print(json.dumps(dict(getattr(exc, 'result', {}), error=str(exc), code=exc.code), default=str), file=sys.stderr)
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


def read_selected(call):
    from invest.research_identity import read_ledger

    with read_ledger(database_path()) as selected:
        return call(selected)


def review_selected(call, *, confirm):
    preview = read_selected(lambda selected: call(selected, False))
    if not confirm:
        return preview
    selected = ledger()
    with closing(selected.connection):
        return call(selected, True)


@portfolio.command("import")
def import_page(
    file: str,
    account: str = typer.Option(...),
    institution: str = "generic",
    tax_status: str = "OTHER",
    as_of: str = typer.Option(None),
    positions_complete: bool = False,
    lots_complete: bool = False,
    data_environment: str = typer.Option(...),
):
    def parsed():
        if data_environment not in {'REAL', 'SYNTHETIC'}:
            raise DomainError('Data environment must be REAL or SYNTHETIC')
        return parse_html(
            sys.stdin.read() if file == '-' else Path(file).read_text(), account,
            institution, tax_status, as_of=as_of,
            positions_complete=positions_complete, lots_complete=lots_complete,
            data_environment=data_environment)
    emit(
        parsed
    )


@portfolio.command()
def reconcile(file: str):
    emit(lambda: read_selected(lambda selected: selected.reconcile(read_json(file))))


@portfolio.command()
def apply(file: str, allow_older: bool = False, justification: str = typer.Option(None), confirm: bool = False):
    from invest.models import Snapshot
    from invest.research_identity import read_ledger

    def result():
        payload = Snapshot.model_validate(read_json(file)).model_dump(mode='json')
        with read_ledger(database_path()) as selected:
            reconciliation = selected.reconcile(payload)
            # Validate the actual acceptance path against a consistent disposable
            # copy before creating/opening a selected writer. No internal mocks.
            staged = Ledger(':memory:')
            with closing(staged.connection):
                selected.connection.backup(staged.connection)
                staged.apply(payload, allow_older=allow_older, justification=justification)
        if not confirm:
            return dict(reconciliation, status='PREVIEW', committed=False)
        selected = ledger()
        with closing(selected.connection):
            accepted = selected.apply(payload, allow_older=allow_older, justification=justification)
            return dict(accepted, committed=accepted['status'] != 'UNCHANGED')
    emit(result)


@portfolio.command()
def summary():
    emit(lambda: read_selected(lambda selected: selected.summary()))


@portfolio.command('check')
def portfolio_check(as_of: str = typer.Option(...)):
    from invest.readiness import check
    from invest.research_identity import read_ledger

    def result():
        with read_ledger(database_path()) as selected:
            return check(selected.planning_state(), as_of=as_of)
    emit(result)


@portfolio.command('performance')
def portfolio_performance(from_date: str = typer.Option(None, '--from'),
                          to_date: str = typer.Option(None, '--to'),
                          as_of: str = typer.Option(None),
                          account: str = typer.Option(None, '--account')):
    from invest.performance_ledger import report
    from invest.research_identity import read_ledger

    def result():
        with read_ledger(database_path()) as selected:
            return report(selected.connection, from_date=from_date, to_date=to_date, as_of=as_of, account_id=account)
    emit(result)


@portfolio.command("record-activity")
def record_activity(file: str, yes: bool = False):
    def result():
        payload = read_json(file)
        return review_selected(lambda selected, confirmed: selected.record_activity(payload, yes=confirmed), confirm=yes)
    emit(result)


@portfolio.command('record-cash-transfer')
def record_cash_transfer(file: str = typer.Option(...), confirm: bool = False):
    from invest.cash_transfers import record
    from invest.research_identity import read_ledger

    def result():
        payload = read_json(file)
        with read_ledger(database_path()) as selected:
            preview = record(selected, payload)
        if not confirm:
            return preview
        selected = ledger()
        with closing(selected.connection):
            return record(selected, payload, confirm=True)
    emit(result)


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
    emit(lambda: review_selected(lambda selected, confirmed:
        selected.classify_security(security_id, asset_type, source, confirm=confirmed), confirm=confirm))


@account.command("update")
def account_update(account_id: str, file: str = typer.Option(...), yes: bool = False):
    def result():
        payload = read_json(file)
        return review_selected(lambda selected, confirmed: selected.update_account(account_id, payload, yes=confirmed), confirm=yes)
    emit(result)


def client(selected=None):
    import os

    from invest.config import load_config
    from invest.market import MarketClient

    config = load_config()
    return MarketClient(
        selected if selected is not None else ledger(),
        api_key=os.environ.get("FMP_API_KEY") or config.get("fmp", {}).get("api_key"),
        fixture_path=os.environ.get("INVEST_FIXTURES"),
    )


@tax.command("lots")
def tax_lots(as_of: str = typer.Option(None)):
    from datetime import date

    from invest.tax import lots

    emit(lambda: read_selected(lambda selected: lots(selected.state(), as_of or date.today().isoformat())))


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
        lambda: read_selected(lambda selected: analyze(
            selected.state(),
            account,
            security,
            quantity,
            price,
            sale_date,
            method=method,
            lot_ids=lot_ids.split(",") if lot_ids else None,
            rates=load_config().get("tax"),
            fee=fee,
        ))
    )


@tax.command("harvest-candidates")
def harvest(as_of: str = typer.Option(None)):
    from datetime import date

    from invest.tax import harvest_candidates

    emit(lambda: read_selected(lambda selected: harvest_candidates(selected.state(), as_of or date.today().isoformat())))


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
def portfolio_exposure(refresh: bool = False, as_of: str = typer.Option(None)):
    from invest.analytics import exposure
    def result():
        if as_of is not None:
            from invest.portfolio_research_inputs import universe
            from invest.research_identity import read_ledger

            with read_ledger(database_path()) as selected:
                return universe(selected, as_of=as_of)
        selected_client = client()
        with closing(selected_client.ledger.connection):
            return exposure(selected_client.ledger.state(), selected_client, refresh)
    emit(result)


@portfolio.command('research-universe')
def portfolio_research_universe(as_of: str = typer.Option(...), top: int = 20,
                                min_exposure: str = '0.01'):
    from invest.portfolio_research_inputs import universe
    from invest.research_identity import read_ledger
    def result():
        with read_ledger(database_path()) as selected:
            return universe(selected, as_of=as_of, top=top, min_exposure=min_exposure)
    emit(result)


@bond.command("analyze")
def bond_analyze(file: str):
    from invest.bonds import analyze

    emit(lambda: analyze(read_json(file)))


@portfolio.command("simulate")
def portfolio_simulate(file: str):
    from invest.config import load_config
    from invest.scenarios import simulate

    emit(
        lambda: read_selected(lambda selected: simulate(
            selected.state(), client(selected), read_json(file), rates=load_config().get("tax")
        ))
    )


@portfolio.command("risk")
def portfolio_risk(refresh: bool = False):
    from invest.analytics import risk

    emit(lambda: read_selected(lambda selected: risk(selected.state(), client(selected), refresh)))


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

    emit(lambda: read_selected(list_targets))


@target.command("show")
def target_show(target_id: str, version: int = typer.Option(None)):
    from invest.targets import show

    emit(lambda: read_selected(lambda selected: show(selected, target_id, version=version)))


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

    emit(lambda: read_selected(lambda selected: diff(selected, target_id, version=version)))


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

    def result():
        selected = ledger()
        with closing(selected.connection):
            generated = generate(selected, client(), target, as_of=as_of,
                prices=read_json(prices) if prices else None, name=name,
                rates=load_config().get('tax'), version=version)
            return {'plan': generated if generated['status'] == 'BLOCKED' else plan_summary(generated)}
    emit(result)


@plan.command("list")
def plan_list():
    from invest.plans import list_plans

    emit(lambda: read_selected(list_plans))


@plan.command("show")
def plan_show(plan_id: str):
    from invest.plans import show

    emit(lambda: read_selected(lambda selected: show(selected, plan_id)))


@plan.command("compare")
def plan_compare(plan_ids: list[str] = typer.Argument(...)):
    from invest.plans import compare

    emit(lambda: read_selected(lambda selected: compare(selected, *plan_ids)))


@report.command("export")
def report_export(plan_id: str, output: str = typer.Option(...), format: str = "markdown"):
    from invest.plans import persisted
    from invest.reports import export

    emit(lambda: read_selected(lambda selected: export(persisted(selected, plan_id), output, format=format)))


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

    emit(lambda: read_selected(overview))


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


def _specialty_envelope(payload, kind, yes):
    from invest.models import DomainError
    from invest.research_identity import read_ledger
    from invest.research_storage import import_run

    if payload.get('kind') != kind:
        raise DomainError('Envelope kind differs from specialist import command')
    with read_ledger(database_path()) as selected:
        preview = import_run(selected, payload, confirmed=False)
    if not yes:
        return preview
    selected = ledger()
    try:
        return import_run(selected, payload, confirmed=True)
    finally:
        selected.connection.close()


@political.command('import')
def political_import(file: str, yes: bool = False):
    """Preview research; --yes stores it without financial mutations."""
    from invest.political import import_research
    from invest.political_models import PoliticalResearchInput, enforce_policy

    def run():
        payload = read_json(file)
        if isinstance(payload, dict) and 'package' in payload:
            return _specialty_envelope(payload, 'POLITICAL', yes)
        model = PoliticalResearchInput.model_validate(payload)
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
        payload = read_json(file)
        if isinstance(payload, dict) and 'package' in payload:
            return _specialty_envelope(payload, 'EARNINGS', yes)
        model = EarningsResearchInput.model_validate(payload)
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
    from invest.news import _verify_event_ownership, canonical_package, validation_warnings
    from invest.news_models import NewsResearchInput
    from invest.research_identity import read_ledger, verify_company

    def run():
        model = NewsResearchInput.model_validate(read_json(file))
        data, _, run_id, _ = canonical_package(model)
        with read_ledger(database_path()) as db:
            verify_company(db, data['company'])
            _verify_event_ownership(db, data, run_id)
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
        payload = read_json(file)
        if isinstance(payload, dict) and 'package' in payload:
            return _specialty_envelope(payload, 'NEWS', yes)
        model = NewsResearchInput.model_validate(payload)
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


competitive = typer.Typer()
research.add_typer(competitive, name='competitive')


@competitive.command('validate')
def competitive_validate(file: str):
    from invest.competitive import validation_warnings, verify_entities
    from invest.competitive_models import CompetitiveResearchInput
    from invest.research_identity import read_ledger

    def run():
        model = CompetitiveResearchInput.model_validate(read_json(file))
        data = model.model_dump(mode='json')
        with read_ledger(database_path()) as db:
            verify_entities(db, data)
        return {'valid': True, 'coverage_status': model.scope.coverage_status,
                'peer_count': len(model.peers), 'overlap_count': len(model.overlaps),
                'finding_count': len(model.findings), 'metric_count': len(model.metrics),
                'warnings': validation_warnings(data)}
    emit(run)


@competitive.command('import')
def competitive_import(file: str, yes: bool = False):
    from invest.competitive import import_research, verify_entities
    from invest.competitive_models import CompetitiveResearchInput
    from invest.research_identity import read_ledger

    def run():
        payload = read_json(file)
        if isinstance(payload, dict) and 'package' in payload:
            return _specialty_envelope(payload, 'COMPETITIVE', yes)
        model = CompetitiveResearchInput.model_validate(payload)
        # Verify canonical identity before even creating a confirmed destination.
        with read_ledger(database_path()) as db:
            if not yes:
                return import_research(db, model, yes=False)
            verify_entities(db, model.model_dump(mode='json'))
        db = ledger()
        try:
            return import_research(db, model, yes=True)
        finally:
            db.connection.close()
    emit(run)


@competitive.command('list')
def competitive_list(ticker: str = typer.Option(None)):
    from invest.competitive_queries import list_runs
    emit(lambda: political_query(list_runs, ticker))


@competitive.command('show')
def competitive_show(run_id: str):
    from invest.competitive_queries import show
    emit(lambda: political_query(show, run_id))


@competitive.command('summary')
def competitive_summary(run_id: str):
    from invest.competitive_queries import summary
    emit(lambda: political_query(summary, run_id))


@competitive.command('matrix')
def competitive_matrix(run_id: str, peer: str = typer.Option(None)):
    from invest.competitive_queries import matrix
    emit(lambda: political_query(matrix, run_id, peer))


insiders = typer.Typer()
research.add_typer(insiders, name='insiders')


@insiders.command('validate')
def insiders_validate(file: str):
    from invest.insider_models import InsiderResearchInput
    from invest.insiders import validation_warnings
    from invest.research_identity import read_ledger, verify_company

    def run():
        model = InsiderResearchInput.model_validate(read_json(file))
        data = model.model_dump(mode='json')
        with read_ledger(database_path()) as db:
            verify_company(db, data['company'])
        return {'valid': True, 'coverage_status': model.scope.coverage_status,
                'person_count': len(model.people), 'compensation_count': len(model.compensation),
                'transaction_count': len(model.transactions), 'ownership_count': len(model.ownership),
                'warnings': validation_warnings(data)}
    emit(run)


@insiders.command('import')
def insiders_import(file: str, yes: bool = False):
    from invest.insider_models import InsiderResearchInput
    from invest.insiders import import_research
    from invest.research_identity import read_ledger, verify_company

    def run():
        payload = read_json(file)
        if isinstance(payload, dict) and 'package' in payload:
            return _specialty_envelope(payload, 'INSIDERS', yes)
        model = InsiderResearchInput.model_validate(payload)
        with read_ledger(database_path()) as db:
            if not yes:
                return import_research(db, model, yes=False)
            verify_company(db, model.model_dump(mode='json')['company'])
        db = ledger()
        try:
            return import_research(db, model, yes=True)
        finally:
            db.connection.close()
    emit(run)


@insiders.command('list')
def insiders_list(ticker: str = typer.Option(None)):
    from invest.insider_queries import list_runs
    emit(lambda: political_query(list_runs, ticker))


@insiders.command('show')
def insiders_show(run_id: str):
    from invest.insider_queries import show
    emit(lambda: political_query(show, run_id))


@insiders.command('summary')
def insiders_summary(run_id: str):
    from invest.insider_queries import summary
    emit(lambda: political_query(summary, run_id))


@insiders.command('activity')
def insiders_activity(run_id: str, person: str = typer.Option(None)):
    from invest.insider_queries import activity
    emit(lambda: political_query(activity, run_id, person))


@insiders.command('ownership')
def insiders_ownership(run_id: str, person: str = typer.Option(None)):
    from invest.insider_queries import ownership
    emit(lambda: political_query(ownership, run_id, person))


funds_research = typer.Typer()
research.add_typer(funds_research, name='funds')


@funds_research.command('validate')
def funds_validate(file: str):
    from invest.fund_diligence import validation_warnings, verify_fund
    from invest.fund_diligence_models import FundDiligenceInput
    from invest.research_identity import read_ledger

    def run():
        model = FundDiligenceInput.model_validate(read_json(file))
        data = model.model_dump(mode='json')
        with read_ledger(database_path()) as db:
            verify_fund(db, data['fund'])
        return {'valid': True, 'fund': data['fund'],
                'coverage_status': model.scope.coverage_status,
                'holding_count': len(model.holdings), 'metric_count': len(model.metrics),
                'finding_count': len(model.findings), 'source_count': len(model.sources),
                'warnings': validation_warnings(data)}
    emit(run)


@funds_research.command('import')
def funds_import(file: str, yes: bool = False):
    from invest.fund_diligence import import_research, verify_fund
    from invest.fund_diligence_models import FundDiligenceInput
    from invest.research_identity import read_ledger

    def run():
        model = FundDiligenceInput.model_validate(read_json(file))
        with read_ledger(database_path()) as db:
            preview = import_research(db, model, yes=False)
            if not yes or preview['status'] == 'UNCHANGED':
                return preview
            verify_fund(db, model.model_dump(mode='json')['fund'])
        db = ledger()
        try:
            return import_research(db, model, yes=True)
        finally:
            db.connection.close()
    emit(run)


@funds_research.command('list')
def funds_list(ticker: str = typer.Option(None)):
    from invest.fund_diligence_queries import list_runs
    emit(lambda: political_query(list_runs, ticker))


@funds_research.command('show')
def funds_show(run_id: str):
    from invest.fund_diligence_queries import show
    emit(lambda: political_query(show, run_id))


@funds_research.command('summary')
def funds_summary(run_id: str):
    from invest.fund_diligence_queries import summary
    emit(lambda: political_query(summary, run_id))


@funds_research.command('holdings')
def funds_holdings(run_id: str):
    from invest.fund_diligence_queries import holdings
    emit(lambda: political_query(holdings, run_id))


database = typer.Typer()
app.add_typer(database, name='db')


@database.command('status')
def database_status():
    from invest.db import status
    emit(lambda: status(database_path()))


@database.command('backup')
def database_backup(output: str = typer.Option(...)):
    from invest.backup import create
    emit(lambda: create(database_path(), output))


@database.command('verify')
def database_verify(file: str):
    from invest.backup import verify
    emit(lambda: verify(file))


@database.command('restore')
def database_restore(file: str, dry_run: bool = False, confirm: bool = False):
    from invest.backup import restore
    emit(lambda: restore(file, database_path(), dry_run=dry_run, confirm=confirm))


@database.command('migrate')
def database_migrate():
    from invest.migrations import migrate
    emit(lambda: migrate(database_path()))


@database.command('cleanup-artifacts')
def database_cleanup_artifacts(artifact_root: str = typer.Option(...), confirm: bool = False):
    """Preview or explicitly remove abandoned managed artifact staging files."""
    from invest.artifact_cleanup import cleanup
    from invest.research_identity import read_ledger

    def result():
        with read_ledger(database_path()) as selected:
            return cleanup(selected, artifact_root, confirm=confirm)
    emit(result)


data = typer.Typer()
app.add_typer(data, name='data')
portfolio_research = typer.Typer()
research.add_typer(portfolio_research, name='portfolio')


@data.command('snapshot')
def data_snapshot(file: str = typer.Option(...)):
    from invest.analytics_store import snapshot

    def result():
        payload = read_json(file)
        if 'issuers' in payload:
            payload = {'id': payload.get('manifest_id'),
                       'as_of': payload.get('as_of'),
                       'data_environment': payload.get('data_environment'),
                       'purpose': 'RESEARCH_UNIVERSE', 'metadata': {'universe': payload}}
        selected = ledger()
        with closing(selected.connection):
            return snapshot(selected, payload, confirm=True)
    emit(result)


@data.command('list')
def data_list():
    from invest.analytics_store import list_snapshots
    from invest.research_identity import read_ledger
    def result():
        with read_ledger(database_path()) as selected:
            return list_snapshots(selected)
    emit(result)


@data.command('verify')
def data_verify(file: str = typer.Option(...)):
    from invest.analytics_store import verify_snapshot
    from invest.research_identity import read_ledger
    def result():
        with read_ledger(database_path()) as selected:
            return verify_snapshot(selected, read_json(file))
    emit(result)


@portfolio_research.command('plan')
def research_portfolio_plan(universe_manifest: str = typer.Option(...),
                            window_start: str = typer.Option(None),
                            window_end: str = typer.Option(None)):
    from invest.research_portfolio import plan
    def result():
        selected = ledger()
        with closing(selected.connection):
            return plan(selected, universe_manifest, window_start=window_start, window_end=window_end)
    emit(result)


@portfolio_research.command('report')
def research_portfolio_report(plan: str = typer.Option(...)):
    from invest.research_identity import read_ledger
    from invest.research_portfolio import report
    def result():
        with read_ledger(database_path()) as selected:
            return report(selected, plan)
    emit(result)


@plan.command('propose')
def plan_propose(file: str = typer.Option(...), policy: str = typer.Option(...),
                 mode: str = typer.Option(...), as_of: str = typer.Option(...)):
    from invest.planning import propose
    from invest.targets import save
    def result():
        payload = read_json(file)
        selected = ledger()
        with closing(selected.connection):
            target = payload.get('target_id') or payload.get('target')
            if isinstance(target, dict):
                identifier = target.get('id')
                existing = {item['id'] for item in selected.rows('targets')}
                target = save(selected, {'id': identifier if identifier in existing else None,
                    'name': target.get('name') or target.get('id') or 'Reviewed proposal target',
                    'target_allocations': target['weights'],
                    'data_environment': payload.get('data_environment'),
                    'planning_constraints': {'eligible_accounts': [payload['account_id']]}
                    if payload.get('account_id') else {}})['id']
            proposal = propose(selected, target, policy=policy, mode=mode,
                               as_of=as_of, prices=payload.get('prices', {}))
            proposal['proposed_actions'] = [
                {key: action[key] for key in ('type', 'account_id', 'security', 'quantity', 'notional')}
                for action in proposal['proposed_actions']]
            return proposal
    emit(result)


@tax.command('harvest-plan')
def tax_harvest_plan(file: str = typer.Option(None), as_of: str = typer.Option(...),
                     policy_version: str = typer.Option(None)):
    from invest.ledger import _issue
    from invest.research_identity import read_ledger
    from invest.tax import harvest_plan
    def result():
        if file is not None and policy_version is not None:
            raise DomainError('Choose an approved policy version or an unsaved review file')
        if policy_version is not None:
            from invest.planning import get_policy

            with read_ledger(database_path()) as selected:
                return harvest_plan(selected.state(), get_policy(selected, policy_version), as_of)
        if file is None:
            return {'status': 'REVIEW_REQUIRED', 'as_of': as_of,
                    'issues': [_issue('MISSING_HARVEST_REVIEW_SCOPE',
                                     'Supply reviewed household acquisition coverage and loss-sale scope')],
                    'replacement_candidates': [], 'guaranteed_tax_savings': None,
                    'legal_wash_sale_safe': None, 'wash_sale_certified': False}
        with read_ledger(database_path()) as selected:
            report = harvest_plan(selected.state(), read_json(file), as_of)
            report['wash_sale_certified'] = False
            for issue in list(report['issues']):
                if issue['code'] in {'HOUSEHOLD_IRA_ACQUISITION_CONFLICT', 'POTENTIAL_WASH_SALE_CONFLICT'}:
                    report['issues'].append(dict(issue, code='HOUSEHOLD_PURCHASE_CONFLICT'))
                elif issue['code'] in {'UNKNOWN_OUTSIDE_ACCOUNT_HISTORY', 'UNKNOWN_DIVIDEND_REINVESTMENTS'}:
                    report['issues'].append(dict(issue, code='HOUSEHOLD_HISTORY_INCOMPLETE'))
            return report
    emit(result)


@tax.command('budget')
def tax_budget(year: int = typer.Option(...), as_of: str = typer.Option(...),
               policy: str = typer.Option(None)):
    from invest.config import load_config
    from invest.planning import get_policy
    from invest.research_identity import read_ledger
    from invest.tax import annual_budget
    def result():
        identifier = policy or load_config().get('planning', {}).get('policy_id')
        with read_ledger(database_path()) as selected:
            approved = get_policy(selected, identifier)
            allowance = dict(approved.get('annual_tax_budget', {}), year=year,
                             as_of=as_of + 'T23:59:59+00:00', data_environment=approved['data_environment'])
            return annual_budget(selected.state(), allowance)
    emit(result)


backtests = typer.Typer()
app.add_typer(backtests, name='backtest')


def _backtest_file(file, compare_runs=False):
    from invest.backtest import compare, run
    from invest.backtest_models import BacktestInput
    from invest.ledger import _issue
    payload = BacktestInput.model_validate(read_json(file)).model_dump(mode='json', exclude_none=True)
    selected = ledger()
    with closing(selected.connection):
        if payload.get('run_ids'):
            return compare(selected, payload['run_ids'])
        provenance = payload.get('history_provenance', {})
        manifest = {'id': payload.get('manifest_ids', [None])[0],
                    'data_environment': provenance.get('data_environment'),
                    'series': payload.get('history', {}),
                    'sessions': provenance.get('expected_sessions'),
                    'provenance': provenance}
        policy = {'cash_return': payload.get('cash_return'),
                  'fee_per_trade': payload.get('fees'),
                  'starting_value': payload.get('starting_value'),
                  'rebalance_frequency': 'BUY_AND_HOLD' if payload.get('rebalancing') == 'NONE'
                  else payload.get('rebalancing')}
        if (provenance.get('kind') != 'DIVIDEND_ADJUSTED_TOTAL_RETURN_INDEX'
                or not provenance.get('source_id') or any(value is None for value in policy.values())):
            return {'status': 'UNAVAILABLE', 'classification': 'HYPOTHETICAL',
                    'issues': [_issue('INCOMPLETE_BACKTEST_ASSUMPTIONS',
                                     'Supply sourced adjusted history and explicit cash, fee and rebalancing assumptions')],
                    'candidates': [], 'comparable': False}
        policy['contribution_schedule'] = payload.get('contribution_schedule', [])
        for assumption in ('slippage', 'taxes'):
            if assumption in payload:
                policy[assumption] = payload[assumption]
        candidates = payload.get('candidates', [])
        if not candidates:
            raise DomainError('Supply explicit candidate allocations or saved run IDs')
        if payload.get('candidate_ids') and payload['candidate_ids'] != [item['id'] for item in candidates]:
            raise DomainError('Candidate IDs contradict explicit candidate allocations')
        if payload.get('data_environment') and payload['data_environment'] != provenance.get('data_environment'):
            raise DomainError('Candidate and history data environments differ', 3)
        runs = [run(selected, portfolio=candidate['weights'], start=payload['start'],
                    end=payload['end'], policy=policy, manifest=manifest) for candidate in candidates]
        comparison = compare(selected, [value['id'] for value in runs]) if compare_runs else None
        issues = comparison['issues'] if comparison else [issue for value in runs for issue in value['issues']]
        result = {'status': 'PARTIAL' if issues else 'AVAILABLE',
                'classification': 'HYPOTHETICAL', 'comparable': not issues,
                'requested_mode': payload['mode'],
                'period': {'start': payload['start'], 'end': payload['end']},
                'manifest_ids': payload.get('manifest_ids', []), 'issues': issues,
                'candidates': [dict(value, candidate_id=candidate['id'])
                               for candidate, value in zip(candidates, runs)],
                'assumptions': runs[0]['assumptions']}
        if compare_runs:
            from invest.config import load_config
            from invest.planning import get_policy, propose
            from invest.targets import save
            policy_id = payload.get('policy_id') or load_config().get('planning', {}).get('policy_id')
            result['transition_plans'] = []
            if policy_id:
                approved = get_policy(selected, policy_id)
                state = selected.planning_state()
                dated = [row['source_timestamp'][:10] for row in state['snapshots']
                         if row.get('source_timestamp')]
                transition_date = payload.get('as_of') or max(dated, default=None)
                if transition_date is not None:
                    prices = {}
                    for position in state['positions']:
                        if position.get('price') is None or position.get('source_timestamp') is None:
                            continue
                        source = next((row for row in state['snapshots']
                                       if row['account']['id'] == position['account_id']), None)
                        if source is None:
                            continue
                        prices[position['security_id']] = {
                            'price': position['price'], 'as_of': position['source_timestamp'],
                            'currency': next(row['currency'] for row in state['accounts']
                                             if row['id'] == position['account_id']),
                            'data_environment': source['data_environment'],
                            'source': 'ACCEPTED_SQLITE_OBSERVATION:' + source['id'],
                            'source_snapshot_id': source['id'], 'source_hash': source['source_hash']}
                    for candidate in candidates:
                        target = save(selected, {'name': candidate['id'],
                            'data_environment': payload.get('data_environment'),
                            'target_allocations': candidate['weights'],
                            'planning_constraints': {'eligible_accounts': sorted(approved['permissions'])}})
                        result['transition_plans'].append(propose(selected, target['id'],
                            policy=policy_id, mode='rebalance', as_of=transition_date, prices=prices))
            return result
        return result


@backtests.command('run')
def backtest_run(file: str):
    emit(lambda: _backtest_file(file))


@backtests.command('compare')
def backtest_compare(file: str):
    emit(lambda: _backtest_file(file, compare_runs=True))


@research.command('search')
def research_search(query: str = '', top_k: int = 10, issuer_id: str = typer.Option(None),
                     date_from: str = typer.Option(None), date_to: str = typer.Option(None),
                     semantic: bool = False, embedding_file: str = typer.Option(None),
                     model_id: str = typer.Option(None)):
    from invest.search import search

    def result():
        if semantic and (not embedding_file or not model_id):
            raise DomainError('Semantic search requires an explicit query embedding file and model ID')
        if not semantic and (embedding_file or model_id):
            raise DomainError('Embedding file/model ID require explicit semantic search')
        return search(database_path(), query=query, top_k=top_k, issuer_id=issuer_id,
                      date_from=date_from, date_to=date_to,
                      vector=read_json(embedding_file) if semantic else None, model_id=model_id)
    emit(result)


@research.command('index')
def research_index(confirm: bool = False):
    from invest.ledger import _issue
    from invest.search import rebuild_index
    def result():
        if not confirm:
            return {'status': 'PREVIEW', 'canonical_changed': False, 'committed': False}
        if not database_path().exists():
            return {'status': 'UNAVAILABLE', 'committed': False, 'canonical_changed': False,
                    'issues': [_issue('CORPUS_UNAVAILABLE', 'Accept authorized canonical corpus evidence first')]}
        return dict(rebuild_index(database_path()), committed=True)
    emit(result)
