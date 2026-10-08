"""Household look-through and reproducible historical calculations."""

from decimal import Decimal

from invest.models import DomainError, decimal

ZERO = Decimal("0")


def exposure(state, client, refresh=False):
    total = sum((decimal(p["market_value"]) for p in state["positions"]), ZERO) + sum(
        (decimal(c["amount"]) for c in state["cash_balances"]), ZERO
    )
    unknown, entries, warnings, provenance = ZERO, [], [], {}
    securities = {s["id"]: s for s in state["securities"]}
    for position in state["positions"]:
        value = decimal(position["market_value"])
        asset = position.get("asset_type", "OTHER")
        source = {"account_id": position["account_id"], "position": position["security"]}
        if asset in {"ETF", "MUTUAL_FUND"}:
            try:
                data = client.holdings(position["security"], refresh=refresh)
                provenance[position["security"]] = data
            except DomainError as exc:
                if exc.code != 2:
                    raise
                warnings.append(f"{position['security']}: holdings unavailable")
                unknown += value
                continue
            warnings.extend(data["warnings"])
            coverage = sum(
                (decimal(h["weight"]) for h in data["holdings"] if h["weight"] is not None), ZERO
            )
            if coverage > 1:
                warnings.append(
                    f"{position['security']}: weights exceed 100%; entire fund unresolved"
                )
                unknown += value
                continue
            allocated = ZERO
            for holding in data["holdings"]:
                if holding["weight"] is None or holding["identifier"].startswith("UNRESOLVED:"):
                    continue
                amount = value * decimal(holding["weight"])
                entries.append(
                    dict(
                        holding,
                        direct=ZERO,
                        indirect=amount,
                        contribution=dict(source, fund=position["security"], value=str(amount)),
                    )
                )
                allocated += amount
            unknown += value - allocated
        elif asset == "OTHER":
            unknown += value
            warnings.append(f"{position['security']}: unsupported asset exposure unresolved")
        else:
            security = securities.get(position.get("security_id"), {})
            entries.append(
                dict(
                    security,
                    ticker=position["security"],
                    identifier=position.get("security_id", position["security"]),
                    direct=value,
                    indirect=ZERO,
                    contribution=dict(source, value=str(value)),
                )
            )
    for cash in state["cash_balances"]:
        entries.append(
            dict(
                ticker="CASH",
                identifier="CASH",
                asset_type="CASH",
                direct=decimal(cash["amount"]),
                indirect=ZERO,
                contribution=dict(
                    account_id=cash["account_id"], position="CASH", value=cash["amount"]
                ),
            )
        )
    # Map ticker-only constituent records to a unique strong alias when supplied.
    aliases = {}
    for row in entries:
        strong = next(
            (f"{key.upper()}:{row[key]}" for key in ("isin", "cusip", "figi") if row.get(key)), None
        )
        if row.get("ticker") and strong:
            aliases.setdefault(row["ticker"], set()).add(strong)
    merged, sectors, asset_types = {}, {}, {}
    for row in entries:
        strong = next(
            (f"{key.upper()}:{row[key]}" for key in ("isin", "cusip", "figi") if row.get(key)), None
        )
        candidates = aliases.get(row.get("ticker"), set())
        identity = strong or (
            next(iter(candidates))
            if len(candidates) == 1
            else f"TICKER:{row.get('ticker')}"
            if row.get("ticker")
            else row["identifier"]
        )
        target = merged.setdefault(
            identity,
            dict(
                identifier=identity,
                ticker=row.get("ticker"),
                name=row.get("name"),
                direct_value=ZERO,
                indirect_value=ZERO,
                total_value=ZERO,
                contributions=[],
            ),
        )
        target["direct_value"] += row["direct"]
        target["indirect_value"] += row["indirect"]
        amount = row["direct"] + row["indirect"]
        target["total_value"] += amount
        target["contributions"].append(row["contribution"])
        if row.get("sector"):
            sectors[row["sector"]] = sectors.get(row["sector"], ZERO) + amount
        if row.get("asset_type"):
            asset_types[row["asset_type"]] = asset_types.get(row["asset_type"], ZERO) + amount
    results = []
    for row in merged.values():
        row["percentage"] = str(row["total_value"] / total * 100 if total else ZERO)
        results.append({k: str(v) if isinstance(v, Decimal) else v for k, v in row.items()})
    results.sort(key=lambda r: decimal(r["total_value"]), reverse=True)
    return {
        "total_value": str(total),
        "exposures": results,
        "unknown_exposure_value": str(unknown),
        "unknown_exposure_percentage": str(unknown / total * 100 if total else ZERO),
        "by_sector": {k: str(v) for k, v in sectors.items()},
        "by_asset_type_known": {k: str(v) for k, v in asset_types.items()},
        "provenance": provenance,
        "warnings": list(dict.fromkeys(warnings)),
    }
