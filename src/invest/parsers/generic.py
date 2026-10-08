import hashlib
import re
from datetime import date
from decimal import Decimal, InvalidOperation

from bs4 import BeautifulSoup

from invest.models import DomainError, Snapshot
from invest.parsers.profiles import ALIASES, PROFILES


def number(text):
    value = text.strip().replace("$", "").replace(",", "")
    if not value or value in {"—", "-", "N/A", "n/a"}:
        return None
    if value.startswith("(") and value.endswith(")"):
        value = "-" + value[1:-1]
    try:
        result = Decimal(value)
        return result if result.is_finite() else None
    except InvalidOperation:
        return None


def parse_html(html, account_id, institution="generic", tax_status="TAXABLE", as_of=None):
    if institution.lower() not in PROFILES:
        raise DomainError("Unknown profile; use generic or a documented provisional profile")
    if not account_id or not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]{0,63}", account_id):
        raise DomainError("Use a synthetic account alias beginning with a letter")
    soup = BeautifulSoup(html, "lxml")
    positions, lots, warnings, cash = [], [], [], Decimal("0")
    cash_known = False
    aliases = {alias: key for key, items in ALIASES.items() for alias in items}
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue
        headers = [
            aliases.get(c.get_text(" ", strip=True).lower()) for c in rows[0].find_all(["th", "td"])
        ]
        if "market_value" not in headers:
            continue
        for index, row in enumerate(rows[1:]):
            cells = row.find_all(["td", "th"])
            if len(cells) != len(headers):
                warnings.append("Skipped row with inconsistent columns")
                continue
            values = {key: c.get_text(" ", strip=True) for key, c in zip(headers, cells) if key}
            symbol = values.get("security", "").strip().upper()
            name = values.get("name", "")
            value = number(values.get("market_value", ""))
            if symbol in {"CASH", "USD"} or name.lower() in {
                "cash",
                "cash balance",
                "available cash",
            }:
                if value is not None and value >= 0:
                    cash += value
                    cash_known = True
                continue
            qty = number(values.get("quantity", ""))
            if not symbol or qty is None or value is None or qty < 0 or value < 0:
                warnings.append("Unresolved or ambiguous row omitted; review source manually")
                continue
            asset = values.get("asset_type", "OTHER").upper().replace(" ", "_")
            if asset not in {"STOCK", "ETF", "MUTUAL_FUND", "TREASURY", "BOND", "CASH", "OTHER"}:
                asset = "OTHER"
            if asset == "OTHER":
                warnings.append(f"{symbol}: asset type unavailable; stored as unsupported OTHER")
            basis = number(values.get("cost_basis", ""))
            position = dict(
                security=symbol,
                name=name,
                asset_type=asset,
                quantity=str(qty),
                market_value=str(value),
                price=number(values.get("price", "")),
                cost_basis=basis,
                as_of=as_of or date.today().isoformat(),
            )
            acquired = values.get("acquisition_date")
            if acquired and basis is not None:
                try:
                    acquisition = date.fromisoformat(acquired)
                    lots.append(
                        dict(
                            id=f"{account_id}-{symbol}-{index}",
                            security=symbol,
                            acquisition_date=acquisition.isoformat(),
                            quantity=str(qty),
                            remaining_quantity=str(qty),
                            cost_basis=str(basis),
                        )
                    )
                except ValueError:
                    warnings.append(f"{symbol}: acquisition date must be ISO YYYY-MM-DD")
            prior = next((p for p in positions if p["security"] == symbol), None)
            if prior:
                if not acquired:
                    warnings.append(f"{symbol}: duplicate position row omitted")
                    continue
                prior["quantity"] = str(Decimal(prior["quantity"]) + qty)
                prior["market_value"] = str(Decimal(prior["market_value"]) + value)
            else:
                positions.append(position)
    if not positions and not cash_known:
        raise DomainError("No supported position/cash table found; no state can be applied")
    if not cash_known:
        warnings.append("Cash balance unavailable")
    if not lots:
        warnings.append("Lot detail unavailable; tax analysis may be insufficient")
    snapshot = Snapshot(
        account=dict(
            id=account_id, name=account_id, institution=institution, tax_status=tax_status
        ),
        positions=positions,
        lots=lots,
        cash=cash,
        cash_known=cash_known,
        source_hash=hashlib.sha256(html.encode()).hexdigest(),
        warnings=warnings,
    )
    return snapshot.model_dump(mode="json")
