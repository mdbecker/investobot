"""FMP structured data with explicit provenance and conservative freshness rules."""

import json
import os
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from itertools import pairwise
from pathlib import Path

import httpx
import numpy as np

from invest.models import DomainError

ZERO = Decimal(0)
ENDPOINTS = {
    "holdings": "etf/holdings",
    "history": "historical-price-eod/dividend-adjusted",
    "metadata": "etf/info",
    "profile": "profile",
}


def _symbol(value):
    result = str(value).strip().upper()
    if not result or len(result) > 32 or not all(c.isalnum() or c in ".-^" for c in result):
        raise DomainError("Invalid security symbol")
    return result


def _number(value):
    try:
        result = Decimal(str(value))
        if not result.is_finite():
            raise InvalidOperation
        return result
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise DomainError("Provider returned an invalid numeric value", 2) from exc


def _alias(value):
    return str(value).strip().upper() if value not in (None, "") else None


class MarketClient:
    """Public market data only: never accepts account or brokerage credentials."""

    def __init__(self, ledger, api_key=None, fixture_path=None):
        self.ledger = ledger
        self.api_key = api_key or os.environ.get("FMP_API_KEY")
        self.fixture_path = Path(fixture_path) if fixture_path else None
        self.source = "SYNTHETIC_FMP_FIXTURE" if fixture_path else "FMP"

    def _fetch(self, kind, ticker):
        if self.fixture_path:
            try:
                payload = json.loads(self.fixture_path.read_text())
                return payload.get(kind, {}).get(ticker, [])
            except (OSError, ValueError, AttributeError) as exc:
                raise DomainError("Synthetic fixture is unavailable or invalid", 2) from exc
        if not self.api_key:
            raise DomainError(
                "FMP_API_KEY is required; use explicit fixture mode for demonstrations", 2
            )
        try:
            response = httpx.get(
                f"https://financialmodelingprep.com/stable/{ENDPOINTS[kind]}",
                params={"symbol": ticker, "apikey": self.api_key},
                timeout=20,
            )
            response.raise_for_status()
            rows = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            # Exception strings often include URLs and API keys: never echo them.
            raise DomainError(
                "FMP data unavailable; check connection, API entitlement and rate limit", 2
            ) from exc
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise DomainError("FMP returned an error or unexpected data format", 2)
        return rows

    def _cached(self, kind, ticker, refresh, normalize):
        ticker = _symbol(ticker)
        key = f"{self.source}:{kind}:{ticker}"
        table = "fund_holdings_cache" if kind == "holdings" else "market_data_cache"
        cached = next((row for row in self.ledger.rows(table) if row.get("id") == key), None)
        now = datetime.now(UTC)
        ttl = 604800 if kind == "profile" else 86400
        if cached and not refresh:
            try:
                age = (now - datetime.fromisoformat(cached["retrieved_at"])).total_seconds()
                if 0 <= age < ttl:
                    return dict(cached, cached=True)
            except (ValueError, KeyError, TypeError):
                pass
        rows = self._fetch(kind, ticker)
        result = normalize(rows)
        dates = [
            str(row[field])
            for row in rows
            for field in ("date", "asOfDate", "updated", "updatedAt")
            if row.get(field)
        ]
        # Oldest constituent update bounds a dataset's freshness conservatively.
        as_of = (max(dates) if kind == "history" else min(dates)) if dates else None
        result.update(
            id=key,
            ticker=ticker,
            source=self.source,
            retrieved_at=now.isoformat(),
            data_as_of=as_of,
            cached=False,
            cache_ttl_seconds=ttl,
        )
        with self.ledger.connection:
            self.ledger.put(table, key, result)
        return result

    def holdings(self, ticker, refresh=False):
        def normalize(rows):
            holdings, warnings = [], []
            for index, row in enumerate(rows):
                ticker = _alias(row.get("asset") or row.get("ticker"))
                isin = _alias(row.get("isin"))
                cusip = _alias(row.get("securityCusip") or row.get("cusip"))
                figi = _alias(row.get("figi"))
                identity = (
                    f"ISIN:{isin}"
                    if isin
                    else f"CUSIP:{cusip}"
                    if cusip
                    else f"FIGI:{figi}"
                    if figi
                    else f"TICKER:{ticker}"
                    if ticker
                    else f"UNRESOLVED:{index}"
                )
                raw_weight = row.get("weightPercentage")
                weight = _number(raw_weight) / 100 if raw_weight is not None else None
                if weight is None or weight < 0 or weight > 1:
                    warnings.append(
                        f"{identity}: missing or unsupported weight; exposure is unresolved"
                    )
                    weight = None
                if identity.startswith("UNRESOLVED:"):
                    warnings.append(
                        "Constituent identity unavailable; excluded from similarity matching"
                    )
                holdings.append(
                    {
                        "identifier": identity,
                        "ticker": ticker,
                        "isin": isin,
                        "cusip": cusip,
                        "figi": figi,
                        "name": row.get("name"),
                        "weight": str(weight) if weight is not None else None,
                        "shares": str(row.get("sharesNumber", row.get("shares")))
                        if row.get("sharesNumber", row.get("shares")) is not None
                        else None,
                        "market_value": str(row["marketValue"])
                        if row.get("marketValue") is not None
                        else None,
                        "sector": row.get("sector"),
                        "asset_type": row.get("assetType"),
                    }
                )
            coverage = sum(
                (_number(h["weight"]) for h in holdings if h["weight"] is not None), ZERO
            )
            partial = (
                not holdings
                or abs(coverage - 1) > Decimal("0.005")
                or any(h["weight"] is None for h in holdings)
            )
            if partial:
                warnings.append(
                    "Available holdings appear partial or inconsistent; weights are not rescaled"
                )
            return {
                "status": "AVAILABLE" if holdings else "DATA_UNAVAILABLE",
                "holdings": holdings,
                "weight_coverage": str(coverage),
                "partial": partial,
                "warnings": warnings,
            }

        return self._cached("holdings", ticker, refresh, normalize)

    def history(self, ticker, refresh=False):
        def normalize(rows):
            prices, warnings = [], []
            for row in rows:
                adjusted = row.get("adjClose", row.get("adjustedClose"))
                if adjusted is None:
                    warnings.append("Adjusted close unavailable; unadjusted price was excluded")
                    continue
                try:
                    day = date.fromisoformat(str(row["date"]))
                except (KeyError, ValueError) as exc:
                    raise DomainError("Provider history has an invalid date", 2) from exc
                price = _number(adjusted)
                if price <= 0:
                    warnings.append(f"{day}: nonpositive adjusted price excluded")
                    continue
                prices.append({"date": day.isoformat(), "adjusted_close": str(price)})
            prices.sort(key=lambda p: p["date"])
            if len({p["date"] for p in prices}) != len(prices):
                raise DomainError("Provider history contains duplicate dates", 2)
            for previous, current in pairwise(prices):
                start, end = (
                    date.fromisoformat(previous["date"]),
                    date.fromisoformat(current["date"]),
                )
                if np.busday_count(start.isoformat(), end.isoformat()) > 1:
                    warnings.append(
                        f"Possible missing sessions between {start} and {end}; holiday calendar not applied"
                    )
            return {
                "status": "AVAILABLE" if prices else "DATA_UNAVAILABLE",
                "prices": prices,
                "usable_period": {"start": prices[0]["date"], "end": prices[-1]["date"]}
                if prices
                else None,
                "warnings": warnings,
            }

        return self._cached("history", ticker, refresh, normalize)

    def metadata(self, ticker, refresh=False):
        def normalize(rows):
            data = rows[0] if rows else {}
            return {
                "status": "AVAILABLE" if rows else "DATA_UNAVAILABLE",
                "expense_ratio": str(data["expenseRatio"])
                if data.get("expenseRatio") is not None
                else None,
                "aum": str(data.get("assetsUnderManagement", data.get("aum")))
                if data.get("assetsUnderManagement", data.get("aum")) is not None
                else None,
                "issuer": data.get("issuer"),
                "name": data.get("name"),
                "fund_type": "ETF"
                if data.get("isEtf") is True
                else "MUTUAL_FUND"
                if data.get("isFund") is True
                else None,
                "benchmark": data.get("benchmark"),
                "metadata": data,
                "warnings": [] if rows else ["Fund metadata unavailable"],
            }

        return self._cached("metadata", ticker, refresh, normalize)

    def security_metadata(self, ticker, refresh=False):
        def normalize(rows):
            data = rows[0] if rows else {}
            asset_type = (
                "ETF"
                if data.get("isEtf") is True
                else "MUTUAL_FUND"
                if data.get("isFund") is True
                else "STOCK"
                if data.get("isEtf") is False and data.get("isFund") is False
                else None
            )
            return {
                "status": "AVAILABLE" if rows else "DATA_UNAVAILABLE",
                "name": data.get("companyName"),
                "sector": data.get("sector"),
                "industry": data.get("industry"),
                "country": data.get("country"),
                "currency": data.get("currency"),
                "asset_type": asset_type,
                "isin": _alias(data.get("isin")),
                "cusip": _alias(data.get("cusip")),
                "figi": _alias(data.get("figi")),
                "warnings": [] if rows else ["Security metadata unavailable"],
            }

        return self._cached("profile", ticker, refresh, normalize)


def normalized_identities(rows):
    """Bridge explicit strong aliases, then unambiguous ticker-only observations.

    A shared ticker never joins different strong identities. Security names do
    not establish identity. Results correspond to input row order.
    """
    parents = {}

    def root(alias):
        parents.setdefault(alias, alias)
        while parents[alias] != alias:
            parents[alias] = parents[parents[alias]]
            alias = parents[alias]
        return alias

    def aliases(row):
        return [f"{key.upper()}:{row[key]}" for key in ("isin", "cusip", "figi") if row.get(key)]

    for row in rows:
        strong = aliases(row)
        for alias in strong[1:]:
            parents[root(alias)] = root(strong[0])
        if strong:
            root(strong[0])
    components = {}
    for alias in parents:
        components.setdefault(root(alias), set()).add(alias)
    priority = {"ISIN": 0, "CUSIP": 1, "FIGI": 2}
    labels = {
        key: min(value, key=lambda a: (priority[a.split(":")[0]], a))
        for key, value in components.items()
    }
    ticker_ids = {}
    for row in rows:
        strong = aliases(row)
        if strong and row.get("ticker"):
            ticker_ids.setdefault(row["ticker"], set()).add(labels[root(strong[0])])
    result = []
    for row in rows:
        strong = aliases(row)
        matches = ticker_ids.get(row.get("ticker"), set())
        result.append(
            labels[root(strong[0])]
            if strong
            else next(iter(matches))
            if len(matches) == 1
            else row["identifier"]
        )
    return result


def _matched_weights(a, b):
    identities = normalized_identities(a + b)
    maps = []
    index = 0
    for group in (a, b):
        weights = {}
        for row in group:
            identity = identities[index]
            index += 1
            if row["weight"] is None or row["identifier"].startswith("UNRESOLVED:"):
                continue
            weights[identity] = weights.get(identity, ZERO) + _number(row["weight"])
        maps.append(weights)
    return maps


def compare(client, a, b, refresh=False):
    a, b = _symbol(a), _symbol(b)
    ha, hb = client.holdings(a, refresh), client.holdings(b, refresh)
    if ha["status"] != "AVAILABLE" or hb["status"] != "AVAILABLE":
        raise DomainError("Fund comparison requires available holdings for both funds", 2)
    wa, wb = _matched_weights(ha["holdings"], hb["holdings"])
    identities, shared = wa.keys() | wb.keys(), wa.keys() & wb.keys()
    overlap = sum((min(wa.get(k, ZERO), wb.get(k, ZERO)) for k in identities), ZERO)
    active = sum((abs(wa.get(k, ZERO) - wb.get(k, ZERO)) for k in identities), ZERO) / 2
    warnings = ha["warnings"] + hb["warnings"]
    correlation, histories, metadata = None, {}, {}
    for ticker in (a, b):
        try:
            histories[ticker] = client.history(ticker, refresh)
            warnings.extend(histories[ticker]["warnings"])
        except DomainError as exc:
            if exc.code != 2:
                raise
            warnings.append(f"{ticker}: historical data unavailable")
        try:
            metadata[ticker] = client.metadata(ticker, refresh)
        except DomainError as exc:
            if exc.code != 2:
                raise
            warnings.append(f"{ticker}: fund metadata unavailable")
    usable_period = None
    if a in histories and b in histories:
        pa = {p["date"]: _number(p["adjusted_close"]) for p in histories[a]["prices"]}
        pb = {p["date"]: _number(p["adjusted_close"]) for p in histories[b]["prices"]}
        dates = sorted(pa.keys() & pb.keys())
        if len(dates) >= 3:
            ra = [float(pa[v] / pa[u] - 1) for u, v in pairwise(dates)]
            rb = [float(pb[v] / pb[u] - 1) for u, v in pairwise(dates)]
            if np.std(ra) > 0 and np.std(rb) > 0:
                correlation = float(np.corrcoef(ra, rb)[0, 1])
            usable_period = {"start": dates[0], "end": dates[-1], "observations": len(dates)}
    if correlation is None:
        warnings.append(
            "Historical correlation requires at least three aligned prices and nonconstant returns"
        )
    sectors = {}
    for label, holdings in ((a, ha), (b, hb)):
        sectors[label] = {}
        for row in holdings["holdings"]:
            if row.get("sector") and row["weight"] is not None:
                sector = row["sector"]
                sectors[label][sector] = sectors[label].get(sector, ZERO) + _number(row["weight"])
    return {
        "fund_a": a,
        "fund_b": b,
        "overlap": str(overlap),
        "active_share": str(active),
        "shared_holdings_count": len(shared),
        "shared_assets_a": str(sum((wa[k] for k in shared), ZERO)),
        "shared_assets_b": str(sum((wb[k] for k in shared), ZERO)),
        "top_shared_holdings": [
            {"identifier": k, "weight_a": str(wa[k]), "weight_b": str(wb[k])}
            for k in sorted(shared, key=lambda k: min(wa[k], wb[k]), reverse=True)[:10]
        ],
        "largest_unique_exposures": {
            a: [
                {"identifier": k, "weight": str(wa[k])}
                for k in sorted(wa.keys() - shared, key=lambda k: wa[k], reverse=True)[:10]
            ],
            b: [
                {"identifier": k, "weight": str(wb[k])}
                for k in sorted(wb.keys() - shared, key=lambda k: wb[k], reverse=True)[:10]
            ],
        },
        "sector_differences": {
            s: str(sectors[a].get(s, ZERO) - sectors[b].get(s, ZERO))
            for s in sectors[a].keys() | sectors[b].keys()
        },
        "historical_return_correlation": correlation,
        "correlation_usable_period": usable_period,
        "expense_ratios": {
            ticker: metadata.get(ticker, {}).get("expense_ratio") for ticker in (a, b)
        },
        "partial": ha["partial"] or hb["partial"],
        "source": client.source,
        "retrieved_at": datetime.now(UTC).isoformat(),
        "data_as_of": {a: ha["data_as_of"], b: hb["data_as_of"]},
        "provenance": {"holdings": {a: ha, b: hb}, "history": histories, "metadata": metadata},
        "warnings": warnings,
    }
