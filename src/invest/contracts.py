"""Discover registered CLI tools and reuse authoritative validation schemas."""

from typer.main import get_command

from invest import models
from invest.models import DomainError, Snapshot

OUTPUT_CONTRACT = {
    "successful_output": "JSON object or array on stdout; financial decimals are strings",
    "diagnostics": "stderr JSON",
    "error_schema": {
        "type": "object",
        "properties": {"error": {"type": "string"}},
        "required": ["error"],
    },
    "exit_codes": {
        "0": "success",
        "1": "invalid input",
        "2": "external data unavailable",
        "3": "inconsistent portfolio state",
        "4": "internal error",
    },
}

# This describes behavior, not inputs: parameters come from the registered CLI,
# and financial JSON validation comes from the same models used by domain code.
PURPOSES = {
    "research.funds.validate": "Validate fund series/class identity and dated disclosures without writes.",
    "research.funds.import": "Preview or explicitly accept immutable fund diligence research only.",
    "research.funds.list": "List compact fund share-class research metadata, optionally by ticker.",
    "research.funds.show": "Read one full immutable fund package and trusted provenance.",
    "research.funds.summary": "Inspect sourced fees, methodology, turnover, liquidity and distributions.",
    "research.funds.holdings": "Inspect dated observed holdings without renormalization or portfolio adoption.",
    "research.insiders.validate": "Validate issuer, reporting owner and filing evidence without writes.",
    "research.insiders.import": "Preview or explicitly accept immutable management/insider research only.",
    "research.insiders.list": "List compact management/insider research history, optionally by ticker.",
    "research.insiders.show": "Read one full immutable insider package and trusted provenance.",
    "research.insiders.summary": "Summarize separate reported transaction categories and compensation bases.",
    "research.insiders.activity": "Inspect effective and excluded as-filed transactions with source evidence.",
    "research.insiders.ownership": "Inspect dated beneficial ownership observations, never calculated holdings.",
    "research.competitive.validate": "Validate source-backed operating peer evidence without writes.",
    "research.competitive.import": "Preview or explicitly accept immutable competitive research only.",
    "research.competitive.list": "List compact competitive research history, optionally by ticker.",
    "research.competitive.show": "Read the complete accepted competitive package and trusted provenance.",
    "research.competitive.summary": "Inspect attributed overlaps and interpretations, never investment scores.",
    "research.competitive.matrix": "Compare strictly compatible reported peer facts with Decimal differences.",
    "research.skills.list": "Discover bundled external-agent research skills without executing them.",
    "research.skills.show": "Read a bundled skill and its references without execution.",
    "research.skills.install": "Explicitly copy bundled skills into a project; confirm overwrites modified canonical files.",
    "research.political.validate": "Validate research evidence and reviewed source permissions without writes.",
    "research.political.import": "Preview or explicitly accept immutable research; never mutate financial state.",
    "research.political.list": "List compact research runs, optionally filtered by ticker.",
    "research.political.show": "Read the full immutable research package and provenance.",
    "research.political.summary": "Calculate descriptive net totals and inspect transaction evidence.",
    "research.earnings.validate": "Validate sourced financial facts without writes.",
    "research.earnings.import": "Preview or explicitly accept immutable earnings research.",
    "research.earnings.list": "List compact earnings history, optionally filtered by ticker.",
    "research.earnings.show": "Read the full immutable earnings package and provenance.",
    "research.earnings.summary": "Inspect reported financial facts and source limitations.",
    "research.earnings.compare": "Compare compatible reported facts with Decimal arithmetic.",
    "research.news.validate": "Validate sourced news observations without writes.",
    "research.news.import": "Preview or explicitly accept immutable news research.",
    "research.news.list": "List compact news run metadata.",
    "research.news.show": "Read one immutable full news package.",
    "research.news.summary": "Inspect sourced events, catalysts and research assessments.",
    "research.news.context": "Read compact prior context for incremental research.",
    "research.news.compare": "Compare exactly two saved news observations conservatively.",
    "research.news.changes": "Compare the latest two compatible accepted company runs.",
    "schema": "Discover all command contracts and snapshot validation schemas.",
    "tools.list": "List available commands and persistent mutation scopes.",
    "tools.describe": "Describe a registered command's inputs and output contract.",
    "portfolio.import": "Preview normalized supplied HTML without persisting raw HTML.",
    "portfolio.reconcile": "Compare a snapshot with accepted state, including suggested classifications requiring security.classify.",
    "portfolio.apply": "Explicitly accept a normalized account snapshot atomically.",
    "portfolio.summary": "Read accepted household accounts, holdings and cash.",
    "portfolio.overview": "Read dashboard state, active target drift, exposure and tax warnings without cache writes.",
    "portfolio.record-activity": "Preview or explicitly confirm manually executed activity.",
    "portfolio.simulate": "Simulate hypothetical actions without portfolio or cache writes.",
    "portfolio.exposure": "Calculate household direct and fund look-through exposure.",
    "portfolio.risk": "Analyze hypothetical current-weight historical performance.",
    "tax.lots": "Inspect known tax lots, holding periods and missing tax data.",
    "tax.analyze": "Estimate a hypothetical sale with explicit lot and tax assumptions.",
    "tax.harvest-candidates": "Inspect known loss lots and conservative wash-sale warnings.",
    "fund.holdings": "Retrieve available fund constituents and unresolved coverage.",
    "fund.compare": "Compare normalized identities, holdings overlap and history.",
    "fund.search": "Find structured fund candidates using supplied filters.",
    "fund.replacements": "Compare supplied replacement funds without certifying wash-sale safety.",
    "market.history": "Retrieve adjusted history with dates, provenance and metrics.",
    "market.quote": "Retrieve public quote observations without updating portfolio marks.",
    "security.screen": "Retrieve structured security candidates using supplied filters.",
    "security.register": "Register verified security metadata without creating holdings or activity.",
    "security.classify": "Preview or confirm a sourced correction from OTHER; known-type conflicts require review.",
    "account.update": "Preview or confirm reasoned, sourced authoritative account metadata changes.",
    "bond.analyze": "Calculate deterministic bond measures from supplied terms.",
    "target.save": "Save a hypothetical target as a new immutable version.",
    "target.list": "List saved hypothetical target portfolios.",
    "target.show": "Inspect target allocations, versions and account restrictions.",
    "target.activate": "Explicitly select one active target without placing trades.",
    "target.archive": "Archive a target while preserving historical plans.",
    "target.diff": "Compare accepted household allocation with target allocation.",
    "plan.generate": "Persist an unapproved hypothetical scenario requiring policy review; block REAL inputs.",
    "plan.list": "List compact saved plan summaries with current review or stale status.",
    "plan.show": "Retrieve a complete saved plan; potentially large JSON. Prefer report.export for review.",
    "plan.compare": "Compare compact saved financial summaries and disclose incompatible assumptions.",
    "report.export": "Write a persisted plan report and return its path and content hash.",
    "prompt.list": "List bundled and user Markdown prompts.",
    "prompt.show": "Read full prompt text without executing it.",
    "prompt.save": "Save a local user Markdown prompt.",
    "prompt.delete": "Delete a user prompt while retaining bundled defaults.",
}
SCOPES = {
    'portfolio.record-cash-transfer': 'actual_portfolio',
    'policy.approve': 'policy',
    'policy.list': 'read',
    'policy.show': 'read',
    'db.cleanup-artifacts': 'explicit_unreferenced_managed_artifact_staging',
    'research.search': 'read',
    'research.index': 'derived_index',
    'backtest.run': 'hypothetical_backtests',
    'backtest.compare': 'hypothetical_backtests_and_transition_plans',
    'portfolio.research-universe': 'read',
    'data.snapshot': 'analytical_manifests',
    'data.list': 'read',
    'data.verify': 'read',
    'research.portfolio.plan': 'research_plans',
    'research.portfolio.report': 'read',
    'plan.propose': 'plans',
    'tax.harvest-plan': 'read',
    'tax.budget': 'read',
    'portfolio.performance': 'read',
    'portfolio.check': 'read',
    "research.funds.import": "research",
    "research.skills.install": "project_skill_files",
    "research.political.import": "research",
    "research.earnings.import": "research",
    "research.news.import": "research",
    "research.competitive.import": "research",
    "research.insiders.import": "research",
    "portfolio.apply": "actual_portfolio",
    "portfolio.record-activity": "actual_portfolio",
    "target.save": "targets",
    "target.activate": "targets",
    "target.archive": "targets",
    "plan.generate": "plans",
    "report.export": "requested_output_file",
    "prompt.save": "user_prompt_files",
    "prompt.delete": "user_prompt_files",
    "security.register": "security_metadata",
    "security.classify": "security_metadata",
    "account.update": "account_metadata",
}
CACHE_TOOLS = {
    "portfolio.exposure", "portfolio.risk", "fund.holdings", "fund.compare", "fund.search",
    "fund.replacements", "market.history", "market.quote", "security.screen",
}
JSON_MODELS = {
    "portfolio.reconcile": "Snapshot",
    "portfolio.apply": "Snapshot",
    "portfolio.record-activity": "Activity",
    "target.save": "TargetInput",
    "security.register": "SecurityInput",
    "account.update": "AccountUpdate",
}
JSON_CONTRACTS = {
    "portfolio.simulate": "Nonempty array of BUY, SELL or MOVE_CASH hypothetical actions. "
    "Supply account_id, quantity/amount and explicit hypothetical prices; no actual trades occur.",
    "security.screen": "Object of supported structured security filters.",
    "fund.search": "Object of supported structured fund filters.",
    "bond.analyze": "Object of bond terms; unsupported or missing terms remain unavailable.",
}


def _registered(app):
    if app is None:
        from invest.cli import app

    def walk(command, prefix=""):
        children = getattr(command, "commands", None)
        if children is None:
            yield prefix, command
        else:
            for name, child in sorted(children.items()):
                yield from walk(child, f"{prefix}.{name}" if prefix else name)

    return dict(walk(get_command(app)))


def _parameter_schema(param):
    type_name = param.type.name
    schema = {"type": {"integer": "integer", "float": "number", "boolean": "boolean"}
              .get(type_name, "string")}
    choices = getattr(param.type, "choices", None)
    if choices:
        schema["enum"] = list(choices)
    if param.nargs == -1 or param.multiple:
        schema = {"type": "array", "items": schema}
    if param.default is not None:
        schema["default"] = param.default
    return schema


def _describe(name, command):
    properties = {}
    required = []
    options = []
    for param in command.params:
        if param.name in {"help", "install_completion", "show_completion"}:
            continue
        properties[param.name] = _parameter_schema(param)
        if param.required:
            required.append(param.name)
        options.append({
            "name": param.name,
            "flags": getattr(param, "opts", []),
            "required": param.required,
            "help": getattr(param, "help", None),
        })
    scope = SCOPES.get(name, "market_cache" if name in CACHE_TOOLS else "none")
    example = "invest " + name.replace(".", " ")
    for param in command.params:
        if param.required:
            flags = getattr(param, "opts", [])
            option = next((flag for flag in flags if flag.startswith("--")), None)
            example += f" {option} {param.name.upper()}" if option else f" {param.name.upper()}"
    result = {
        "name": name,
        "purpose": PURPOSES.get(name) or command.help or f"Invoke {name}.",
        "required_inputs": required,
        "options": options,
        "input_schema": {"type": "object", "properties": properties, "required": required},
        "output_contract": OUTPUT_CONTRACT,
        "mutates_persistent_state": scope not in {"none", "read"},
        "mutation_scope": scope,
        "examples": [example],
        'parameters': options,
        'json_input_schema': {'type': 'object', 'properties': {}, 'additionalProperties': False},
    }
    if name in {"plan.generate", "plan.list", "plan.compare"}:
        from invest.plans import SUMMARY_FIELDS

        result["output_contract"] = dict(OUTPUT_CONTRACT, response_detail="compact_summary",
            summary_fields=list(SUMMARY_FIELDS), full_details_tool="plan.show",
            response_key="plan" if name == "plan.generate" else "plans",
            unknown_financial_values=None,
            summary_metrics="Persisted tax and remaining drift; original generated_status; current status; first five saved warnings")
    elif name == "plan.show":
        result["output_contract"] = dict(OUTPUT_CONTRACT, response_detail="full_plan",
                                         potentially_large_response=True)
    elif name in {'research.news.compare', 'research.news.changes'}:
        from invest.news_queries import DELTA_KEYS

        result['output_contract'] = dict(OUTPUT_CONTRACT,
            delta_arrays=[*DELTA_KEYS, 'warnings'], counts_include_warnings=True,
            reobservations='Prior compatible observations at or before the selected baseline only.',
            disputed_claims='Evidence changes; DISPUTED is not a verified company fact.',
            category_counts='Overlapping evidence categories, never summed as unique developments.')
    elif name == 'research.news.context':
        result['output_contract'] = dict(OUTPUT_CONTRACT,
            response_detail='effective_historical_context', historical_metadata=[
                'last_observed_run_id', 'last_observed_as_of', 'observation_status'],
            observation_status=['OBSERVED_IN_BASELINE', 'NOT_REOBSERVED'],
            historical_context='Latest compatible actual observations; inherited records are not freshly verified.')
    elif name == "portfolio.reconcile":
        result["output_contract"] = dict(OUTPUT_CONTRACT, classification_reviews={
            "fields": ["security_id", "ticker", "canonical_type", "observed_type", "action_required"],
            "action_required": "EXPLICIT_CLASSIFICATION", "correction_tool": "security.classify"})
    model = getattr(models, JSON_MODELS.get(name, ""), None)
    if name in {"research.political.validate", "research.political.import"}:
        from invest.political_models import PoliticalResearchInput

        model = PoliticalResearchInput
    if name in {"research.earnings.validate", "research.earnings.import"}:
        from invest.earnings_models import EarningsResearchInput

        model = EarningsResearchInput
    if name in {"research.news.validate", "research.news.import"}:
        from invest.news_models import NewsResearchInput

        model = NewsResearchInput
    if name in {"research.competitive.validate", "research.competitive.import"}:
        from invest.competitive_models import CompetitiveResearchInput

        model = CompetitiveResearchInput
    if name in {"research.insiders.validate", "research.insiders.import"}:
        from invest.insider_models import InsiderResearchInput

        model = InsiderResearchInput
    if name in {"research.funds.validate", "research.funds.import"}:
        from invest.fund_diligence_models import FundDiligenceInput

        model = FundDiligenceInput
    if model is not None:
        result["json_input_schema"] = model.model_json_schema()
    elif "file" in properties:
        result["json_input_contract"] = JSON_CONTRACTS.get(
            name, "Read the command's validated JSON payload from FILE or stdin with '-'."
        )
    if name in {'data.snapshot', 'data.verify'}:
        from invest.analytics_store import ManifestInput

        result['json_input_schema'] = ManifestInput.model_json_schema()
    if name == 'tax.harvest-plan':
        from invest.tax_policy import HarvestReviewPolicy

        result['json_input_schema'] = HarvestReviewPolicy.model_json_schema()
    if name == 'policy.approve':
        from invest.policy_models import TradingPolicyInput

        result['json_input_schema'] = TradingPolicyInput.model_json_schema()
    if name == 'portfolio.record-cash-transfer':
        from invest.cash_transfers import CashTransferInput

        result['json_input_schema'] = CashTransferInput.model_json_schema()
    if name in {'backtest.run', 'backtest.compare'}:
        from invest.backtest_models import BacktestInput

        result['json_input_schema'] = BacktestInput.model_json_schema()
    if name in {'research.' + family + '.import' for family in (
            'news', 'earnings', 'competitive', 'insiders', 'political')}:
        from invest.research_storage import ResearchEnvelope

        native = result['json_input_schema']
        envelope = ResearchEnvelope.model_json_schema()
        result['json_input_schema'] = {
            'type': 'object', 'additionalProperties': False,
            'properties': {**native['properties'], **envelope['properties']},
            '$defs': {**native.get('$defs', {}), **envelope.get('$defs', {})},
            'anyOf': [native, envelope]}
    return result


def tools_list(app=None):
    """List only registered commands; never open the ledger or provider cache."""
    fields = ("name", "purpose", "mutates_persistent_state", "mutation_scope")
    return {"tools": [{key: tool[key] for key in fields} for tool in
                      (_describe(name, cmd) for name, cmd in _registered(app).items())]}


def tools_describe(name, app=None):
    commands = _registered(app)
    if name not in commands:
        raise DomainError(f"Unknown tool: {name}")
    return _describe(name, commands[name])


def schema_contract(app=None):
    from invest.competitive_models import CompetitiveResearchInput
    from invest.earnings_models import EarningsResearchInput
    from invest.fund_diligence_models import FundDiligenceInput
    from invest.insider_models import InsiderResearchInput
    from invest.news_models import NewsResearchInput
    from invest.political_models import PoliticalResearchInput

    return {
        "fund_diligence": FundDiligenceInput.model_json_schema(),
        "insider_research": InsiderResearchInput.model_json_schema(),
        "competitive_research": CompetitiveResearchInput.model_json_schema(),
        "news_research": NewsResearchInput.model_json_schema(),
        "earnings_research": EarningsResearchInput.model_json_schema(),
        "political_research": PoliticalResearchInput.model_json_schema(),
        "snapshot": Snapshot.model_json_schema(),
        "output_contract": OUTPUT_CONTRACT,
        "tools": [_describe(name, cmd) for name, cmd in _registered(app).items()],
    }
