"""Read-only accepted balance summaries and currency guards."""

from decimal import Decimal, localcontext

from invest.issues import _issue
from invest.models import DomainError, decimal


def household_currency(state):
    currencies = {a.get("currency", "USD") for a in state.get("accounts", [])}
    if len(currencies) > 1:
        raise DomainError("Household currencies differ; no FX conversion is configured", 3)
    return next(iter(currencies), "USD")


def summarize(state):
    values = [decimal(row[key]) for table, keys in (
        ('positions', ('market_value', 'cost_basis')), ('cash_balances', ('amount',)))
        for row in state[table] for key in keys if row.get(key) is not None]
    with localcontext() as context:
        context.prec = max(80, sum(len(format(value, 'f')) for value in values) + 32)
        return _summarize(state)


def _summarize(state):
    currency = household_currency(state)
    missing_cash = [row['id'] for row in state['accounts'] if not any(
        cash['account_id'] == row['id'] for cash in state['cash_balances'])]
    unmarked = [row for row in state['positions'] if row.get('market_value') is None]
    issues = [_issue('UNKNOWN_CASH_COVERAGE', 'Confirm cash coverage', account_id=identity) for identity in missing_cash]
    issues.extend(_issue('MISSING_VALUATION_MARK', 'Confirm an independent valuation mark', security_id=row['security_id']) for row in unmarked)
    cash = sum((decimal(c["amount"]) for c in state["cash_balances"]), Decimal("0"))
    value = sum((decimal(p["market_value"]) for p in state["positions"] if p.get('market_value') is not None), cash)
    accounts, taxes, allocation = {}, {}, {"CASH": str(cash)}
    warnings = []
    for a in state["accounts"]:
        if not any(c["account_id"] == a["id"] for c in state["cash_balances"]):
            warnings.append(f"{a['id']}: cash balance unavailable; total excludes unknown cash")
        total = sum(
            (decimal(p["market_value"]) for p in state["positions"] if p["account_id"] == a["id"] and p.get('market_value') is not None),
            Decimal("0"),
        )
        total += sum(
            (decimal(c["amount"]) for c in state["cash_balances"] if c["account_id"] == a["id"]),
            Decimal("0"),
        )
        accounts[a["id"]] = str(total)
        taxes[a["tax_status"]] = str(decimal(taxes.get(a["tax_status"], "0")) + total)
    unrealized = Decimal("0")
    for p in state["positions"]:
        asset = p.get("asset_type", "OTHER")
        if p.get('market_value') is None:
            continue
        allocation[asset] = str(decimal(allocation.get(asset, "0")) + decimal(p["market_value"]))
        if p.get("cost_basis") is None:
            warnings.append(f"{p['security']}: basis unavailable")
        else:
            unrealized += decimal(p["market_value"]) - decimal(p["cost_basis"])
    return {
        "currency": currency,
        'status': 'PARTIAL' if issues else 'AVAILABLE', 'issues': issues,
        "total_value": None if unmarked or missing_cash else str(value),
        'known_value_subtotal': str(value),
        "cash": None if missing_cash else str(cash),
        "by_account": accounts,
        "by_tax_status": taxes,
        "allocation": allocation,
        "largest_positions": sorted(
            state["positions"], key=lambda p: (p.get('market_value') is not None, decimal(p['market_value']) if p.get('market_value') is not None else Decimal(0)), reverse=True
        )[:10],
        "unrealized_gain_loss_known_basis": str(unrealized),
        "snapshot_dates": sorted({p["as_of"] for p in state["positions"]}),
        "warnings": warnings,
    }


