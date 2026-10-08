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
    "schema": "Discover all command contracts and snapshot validation schemas.",
    "tools.list": "List available commands and persistent mutation scopes.",
    "tools.describe": "Describe a registered command's inputs and output contract.",
    "portfolio.import": "Preview normalized supplied HTML without persisting raw HTML.",
    "portfolio.reconcile": "Compare a normalized snapshot with accepted portfolio state.",
    "portfolio.apply": "Explicitly accept a normalized account snapshot atomically.",
    "portfolio.summary": "Read accepted household accounts, holdings and cash.",
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
    "bond.analyze": "Calculate deterministic bond measures from supplied terms.",
    "target.save": "Save a hypothetical target as a new immutable version.",
    "target.list": "List saved hypothetical target portfolios.",
    "target.show": "Inspect target allocations, versions and account restrictions.",
    "target.activate": "Explicitly select one active target without placing trades.",
    "target.archive": "Archive a target while preserving historical plans.",
    "target.diff": "Compare accepted household allocation with target allocation.",
    "plan.generate": "Persist an explainable hypothetical plan for human review.",
    "plan.list": "List saved plans and their review or stale status.",
    "plan.show": "Inspect immutable proposed trades, assumptions and limitations.",
    "plan.compare": "Compare proposed plans and disclose differing source assumptions.",
    "report.export": "Write a persisted plan report and return its path and content hash.",
    "prompt.list": "List bundled and user Markdown prompts.",
    "prompt.show": "Read full prompt text without executing it.",
    "prompt.save": "Save a local user Markdown prompt.",
    "prompt.delete": "Delete a user prompt while retaining bundled defaults.",
}
SCOPES = {
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
        "mutates_persistent_state": scope != "none",
        "mutation_scope": scope,
        "examples": [example],
    }
    model = getattr(models, JSON_MODELS.get(name, ""), None)
    if model is not None:
        result["json_input_schema"] = model.model_json_schema()
    elif "file" in properties:
        result["json_input_contract"] = JSON_CONTRACTS.get(
            name, "Read the command's validated JSON payload from FILE or stdin with '-'."
        )
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
    return {
        "snapshot": Snapshot.model_json_schema(),
        "output_contract": OUTPUT_CONTRACT,
        "tools": [_describe(name, cmd) for name, cmd in _registered(app).items()],
    }
