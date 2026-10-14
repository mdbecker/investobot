"""Household look-through and reproducible historical calculations."""

from decimal import Decimal

from invest.ledger import household_currency
from invest.models import DomainError, decimal

ZERO = Decimal("0")


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
    aligned = pd.DataFrame(series).sort_index()
    if aligned.isna().any().any():
        return dict(base, status="UNAVAILABLE", annualized_volatility=None,
                    maximum_drawdown=None, correlations={}, usable_period=None,
                    issues=[{"code": "INCOMPLETE_HISTORY_ALIGNMENT",
                             "message": "Historical series do not cover identical sessions",
                             "blocks_calculation": True, "blocks_proposals": True,
                             "blocks_execution_review": True}])
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
