"""Structured candidates and transparent portfolio similarity, never recommendations."""

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from invest.market import _symbol, compare
from invest.models import DomainError

DISCLAIMER = (
    "This score does not determine whether securities are substantially identical for tax purposes."
)
TEXT_FILTERS = {"sector", "industry", "country", "exchange"}
BOOL_FILTERS = {"isEtf", "isFund", "isActivelyTrading"}
NUMERIC_FILTERS = {
    f"{name}{suffix}"
    for name in ("marketCap", "price", "beta", "volume", "avgVolume", "dividend")
    for suffix in ("MoreThan", "LowerThan")
}
FUND_FILTERS = {"fund_type", "expense_ratio_max", "aum_min", "issuer"}


def _decimal(value, name):
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number < 0:
            raise InvalidOperation
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise DomainError(f"{name} must be a finite nonnegative number") from exc
    return number


def _filters(filters):
    if not isinstance(filters, dict):
        raise DomainError("Filters must be a JSON object")
    unknown = filters.keys() - TEXT_FILTERS - BOOL_FILTERS - NUMERIC_FILTERS - {"limit"}
    if unknown:
        raise DomainError(f"Unsupported provider filters: {', '.join(sorted(unknown))}")
    result = {}
    for key, value in filters.items():
        if key in NUMERIC_FILTERS:
            result[key] = str(_decimal(value, key))
        elif key in TEXT_FILTERS:
            if not isinstance(value, str) or not value.strip():
                raise DomainError(f"{key} must be nonempty text")
            result[key] = value.strip()
        elif key in BOOL_FILTERS:
            if not isinstance(value, bool):
                raise DomainError(f"{key} must be a JSON boolean")
            result[key] = value
        else:
            number = _decimal(value, key)
            if number != number.to_integral_value() or not 1 <= number <= 1000:
                raise DomainError("limit must be an integer from 1 to 1000")
            result[key] = int(number)
    for name in ("marketCap", "price", "beta", "volume", "avgVolume", "dividend"):
        low, high = result.get(f"{name}MoreThan"), result.get(f"{name}LowerThan")
        if low is not None and high is not None and Decimal(low) >= Decimal(high):
            raise DomainError(f"{name} lower bound must be below upper bound")
    result.setdefault("limit", 1000)
    return result


def screen(client, filters):
    params = _filters(filters)
    if params.get("isEtf") is True or params.get("isFund") is True:
        raise DomainError("Equity screens exclude funds; use fund search")
    params.update(isEtf=False, isFund=False)
    return dict(client.screen(params), filters=params, purpose="STRUCTURED_CANDIDATES")


def search(client, filters):
    if not isinstance(filters, dict):
        raise DomainError("Fund filters must be a JSON object")
    unknown = filters.keys() - FUND_FILTERS - {"limit"}
    if unknown:
        raise DomainError(f"Unsupported fund filters: {', '.join(sorted(unknown))}")
    kind = filters.get("fund_type", "ETF")
    if kind not in {"ETF", "MUTUAL_FUND"}:
        raise DomainError("fund_type must be ETF or MUTUAL_FUND")
    if "issuer" in filters and (
        not isinstance(filters["issuer"], str) or not filters["issuer"].strip()
    ):
        raise DomainError("issuer must be nonempty text")
    expense = (
        _decimal(filters["expense_ratio_max"], "expense_ratio_max")
        if "expense_ratio_max" in filters
        else None
    )
    aum = _decimal(filters["aum_min"], "aum_min") if "aum_min" in filters else None
    params = _filters(
        {
            "limit": filters.get("limit", 1000),
            "isEtf": kind == "ETF",
            "isFund": kind == "MUTUAL_FUND",
        }
    )
    response = client.screen(params)
    candidates, warnings, provenance = [], list(response["warnings"]), []
    for row in response["candidates"]:
        symbol = row.get("symbol")
        if not symbol:
            warnings.append("Provider candidate without a symbol excluded")
            continue
        try:
            metadata = client.metadata(symbol)
        except DomainError as exc:
            if exc.code != 2:
                raise
            warnings.append(f"{symbol}: fund metadata unavailable; candidate excluded")
            continue
        provenance.append(
            {k: metadata[k] for k in ("ticker", "source", "retrieved_at", "data_as_of")}
        )
        if metadata["status"] != "AVAILABLE":
            warnings.append(f"{symbol}: fund metadata unavailable; candidate excluded")
            continue
        missing = (
            (expense is not None and metadata["expense_ratio"] is None)
            or (aum is not None and metadata["aum"] is None)
            or ("issuer" in filters and metadata["issuer"] is None)
        )
        if missing:
            warnings.append(f"{symbol}: required filter metadata missing; candidate excluded")
            continue
        if expense is not None and Decimal(metadata["expense_ratio"]) > expense:
            continue
        if aum is not None and Decimal(metadata["aum"]) < aum:
            continue
        if (
            "issuer" in filters
            and metadata["issuer"].casefold() != filters["issuer"].strip().casefold()
        ):
            continue
        candidates.append(
            dict(
                row,
                expense_ratio=metadata["expense_ratio"],
                aum=metadata["aum"],
                issuer=metadata["issuer"],
                fund_type=kind,
                metadata_provenance=provenance[-1],
            )
        )
    return dict(
        response,
        candidates=candidates,
        filters=filters,
        metadata_provenance=provenance,
        partial=response["partial"] or bool(warnings),
        warnings=warnings,
        purpose="STRUCTURED_CANDIDATES",
    )


def replacements(client, original, candidates):
    original = _symbol(original)
    if not isinstance(candidates, list):
        raise DomainError("Replacement candidates must be an explicit list of symbols")
    rows = []
    for ticker in sorted({_symbol(candidate) for candidate in candidates} - {original}):
        result = {
            "ticker": ticker,
            "status": "DATA_UNAVAILABLE",
            "score": None,
            "overlap": None,
            "active_share": None,
            "historical_return_correlation": None,
            "expense_ratio_difference": None,
            "fund_type": None,
            "benchmark": None,
            "warnings": [],
            "source": client.source,
        }
        try:
            comparison = compare(client, original, ticker)
        except DomainError as exc:
            if exc.code != 2:
                raise
            result["warnings"].append(str(exc))
            rows.append(result)
            continue
        result.update(
            status="AVAILABLE",
            overlap=comparison["overlap"],
            active_share=comparison["active_share"],
            historical_return_correlation=comparison["historical_return_correlation"],
            partial=comparison["partial"],
            warnings=comparison["warnings"],
            provenance=comparison["provenance"],
        )
        original_meta = comparison["provenance"]["metadata"].get(original, {})
        candidate_meta = comparison["provenance"]["metadata"].get(ticker, {})
        result["fund_type"] = candidate_meta.get("fund_type")
        result["benchmark"] = candidate_meta.get("benchmark")
        result["original_fund_type"] = original_meta.get("fund_type")
        result["original_benchmark"] = original_meta.get("benchmark")
        if (
            original_meta.get("expense_ratio") is not None
            and candidate_meta.get("expense_ratio") is not None
        ):
            result["expense_ratio_difference"] = str(
                Decimal(candidate_meta["expense_ratio"]) - Decimal(original_meta["expense_ratio"])
            )
        if comparison["historical_return_correlation"] is not None and not comparison["partial"]:
            result["score"] = 0.7 * float(comparison["overlap"]) + 0.3 * max(
                0, comparison["historical_return_correlation"]
            )
        else:
            result["warnings"].append(
                "Score unavailable without complete holdings and historical correlation"
            )
        rows.append(result)
    rows.sort(key=lambda row: (row["score"] is None, -(row["score"] or 0), row["ticker"]))
    return {
        "status": "AVAILABLE",
        "original": original,
        "candidates": rows,
        "source": client.source,
        "retrieved_at": datetime.now(UTC).isoformat(),
        "data_as_of": None,
        "score_definition": "0.7 * holdings_overlap + 0.3 * max(0, return_correlation)",
        "purpose": "PORTFOLIO_SIMILARITY",
        "disclaimer": DISCLAIMER,
    }
