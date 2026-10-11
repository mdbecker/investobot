"""Household look-through and reproducible historical calculations."""

from decimal import Decimal

from invest.ledger import household_currency
from invest.market import normalized_identities
from invest.models import DomainError, decimal

ZERO = Decimal("0")


def exposure(state, client, refresh=False):
    currency = household_currency(state)
    total = sum((decimal(p["market_value"]) for p in state["positions"]), ZERO) + sum(
        (decimal(c["amount"]) for c in state["cash_balances"]), ZERO
    )
    unknown, entries, warnings, provenance, fund_coverage = ZERO, [], [], {}, {}
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
            fund_coverage[position["security"]] = {
                "reported_weight": str(coverage),
                "represented_weight": "0",
                "source": data.get("source"),
                "data_as_of": data.get("data_as_of"),
            }
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
                        contribution=dict(
                            source,
                            fund=position["security"],
                            value=str(amount),
                            source=data.get("source"),
                            data_as_of=data.get("data_as_of"),
                        ),
                    )
                )
                allocated += amount
            fund_coverage[position["security"]]["represented_weight"] = str(
                allocated / value if value else ZERO
            )
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
    merged, sectors, asset_types = {}, {}, {}
    for row, identity in zip(entries, normalized_identities(entries)):
        confidence = (
            "STRONG"
            if any(row.get(key) for key in ("isin", "cusip", "figi"))
            else "CASH"
            if row.get("ticker") == "CASH"
            else "LOWER_CONFIDENCE_TICKER"
        )
        row["contribution"]["identifier_confidence"] = confidence
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
                identifier_confidence=confidence,
            ),
        )
        if confidence == "LOWER_CONFIDENCE_TICKER":
            target["identifier_confidence"] = confidence
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
        "currency": currency,
        "total_value": str(total),
        "exposures": results,
        "unknown_exposure_value": str(unknown),
        "unknown_exposure_percentage": str(unknown / total * 100 if total else ZERO),
        "by_sector": {k: str(v) for k, v in sectors.items()},
        "by_asset_type_known": {k: str(v) for k, v in asset_types.items()},
        "provenance": provenance,
        "fund_coverage": fund_coverage,
        "warnings": list(dict.fromkeys(warnings)),
    }


def series_metrics(prices, rolling_window=21):
    from datetime import date

    import numpy as np
    import pandas as pd

    if len(prices) < 3:
        raise DomainError("Historical analysis requires at least three adjusted prices", 2)
    series = pd.Series(
        [float(decimal(p["adjusted_close"])) for p in prices], index=[p["date"] for p in prices]
    )
    returns = series.pct_change().dropna()
    days = (date.fromisoformat(series.index[-1]) - date.fromisoformat(series.index[0])).days
    if days <= 0 or rolling_window < 1:
        raise DomainError("Invalid historical period or rolling window")
    total = series.iloc[-1] / series.iloc[0] - 1
    rolling = series.pct_change(rolling_window).dropna()
    return {
        "total_return": float(total),
        "annualized_return": float((1 + total) ** (365.25 / days) - 1),
        "annualized_volatility": float(returns.std(ddof=1) * np.sqrt(252)),
        "maximum_drawdown": float((series / series.cummax() - 1).min()),
        "rolling_returns": [{"date": d, "return": float(v)} for d, v in rolling.items()],
        "rolling_window_sessions": rolling_window,
        "usable_period": {
            "start": series.index[0],
            "end": series.index[-1],
            "observations": len(series),
        },
        "annualization": {
            "return": "calendar days, 365.25/year",
            "volatility": "sample daily standard deviation, 252 sessions/year",
        },
    }


def risk(state, client, refresh=False):
    household_currency(state)
    import numpy as np
    import pandas as pd

    from invest.scenarios import readonly_client

    client = readonly_client(client)
    total = sum((decimal(p["market_value"]) for p in state["positions"]), ZERO) + sum(
        (decimal(c["amount"]) for c in state["cash_balances"]), ZERO
    )
    if total <= 0:
        raise DomainError("Portfolio has no known positive value", 3)
    weights = {}
    for p in state["positions"]:
        if decimal(p["market_value"]) > 0:
            weights[p["security"]] = (
                weights.get(p["security"], ZERO) + decimal(p["market_value"]) / total
            )
    concentration = {
        "largest_weight": float(max(weights.values(), default=ZERO)),
        "hhi": float(sum((w * w for w in weights.values()), ZERO)),
        "effective_positions": float(1 / sum((w * w for w in weights.values()), ZERO))
        if weights
        else None,
    }
    histories, warnings, series = {}, [], {}
    for ticker in weights:
        try:
            data = client.history(ticker, refresh=refresh)
            histories[ticker] = data
            warnings += data["warnings"]
            if len(data["prices"]) < 3:
                warnings.append(f"{ticker}: insufficient adjusted history")
            else:
                series[ticker] = pd.Series(
                    {p["date"]: float(decimal(p["adjusted_close"])) for p in data["prices"]}
                )
        except DomainError as exc:
            if exc.code != 2:
                raise
            warnings.append(f"{ticker}: historical data unavailable")
    base = {
        "mode": "HYPOTHETICAL_CURRENT_ALLOCATION",
        "position_concentration": concentration,
        "provenance": histories,
        "warnings": warnings,
        "assumptions": {
            "cash_return": "0", "fees": "0", "modeled_taxes": False,
            "weights": "CURRENT_WEIGHTS_REBALANCED_EACH_OBSERVATION",
            "performance": "HYPOTHETICAL",
        },
    }
    if len(series) != len(weights) or not series:
        return dict(
            base,
            status="INSUFFICIENT_DATA",
            annualized_volatility=None,
            maximum_drawdown=None,
            correlations={},
            usable_period=None,
        )
    aligned = pd.DataFrame(series).sort_index().dropna()
    if len(aligned) < 3:
        return dict(
            base,
            status="INSUFFICIENT_DATA",
            annualized_volatility=None,
            maximum_drawdown=None,
            correlations={},
            usable_period=None,
        )
    returns = aligned.pct_change().dropna()
    portfolio_returns = sum((returns[t] * float(weights[t]) for t in weights))
    wealth = np.concatenate(([1.0], (1 + portfolio_returns).cumprod().to_numpy()))
    drawdown = wealth / np.maximum.accumulate(wealth) - 1
    correlations = returns.corr()
    correlation_json = {
        a: {
            b: None if pd.isna(correlations.loc[a, b]) else float(correlations.loc[a, b])
            for b in weights
        }
        for a in weights
    }
    return dict(
        base,
        status="AVAILABLE",
        annualized_volatility=float(portfolio_returns.std(ddof=1) * np.sqrt(252)),
        maximum_drawdown=float(drawdown.min()),
        correlations=correlation_json,
        usable_period={
            "start": aligned.index[0],
            "end": aligned.index[-1],
            "observations": len(aligned),
        },
        cash_weight=str(sum((decimal(c["amount"]) / total for c in state["cash_balances"]), ZERO)),
    )
