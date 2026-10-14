import hashlib
import re
from datetime import date
from decimal import Decimal, InvalidOperation, localcontext

from bs4 import BeautifulSoup

from invest.models import DomainError, Snapshot
from invest.parsers.profiles import ALIASES, PROFILES


def number(text):
    value = text.strip().replace("$", "")
    if not value or value in {"—", "-", "N/A", "n/a"}:
        return None
    if value.startswith("(") and value.endswith(")"):
        value = "-" + value[1:-1]
    if not re.fullmatch(r'[+-]?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?', value):
        return None
    try:
        result = Decimal(value.replace(',', ''))
        return result if result.is_finite() else None
    except InvalidOperation:
        return None


def displayed_precision(text):
    """Only a plain printed numeric lexeme establishes its displayed price unit."""
    value = text.strip().replace('$', '').replace(',', '').strip('()')
    match = re.fullmatch(r'[+-]?\d+(?:\.(\d+))?', value)
    return len(match.group(1) or '') if match else None


def issue(code, message, *ids, calculation=False):
    return {'code': code, 'severity': 'ERROR' if calculation else 'WARNING',
            'affected_ids': list(ids), 'blocks_calculation': calculation,
            'blocks_acceptance': calculation, 'blocks_proposals': True,
            'blocks_execution_review': True, 'message': message}


def add_exact(left, right):
    with localcontext() as context:
        context.prec = max(80, len(format(left, 'f')) + len(format(right, 'f')) + 16)
        return left + right


def parse_html(
    html, account_id, institution="generic", tax_status="OTHER", as_of=None,
    positions_complete=False, lots_complete=False, data_environment=None,
):
    if institution.lower() not in PROFILES:
        raise DomainError("Unknown profile; use generic or a documented provisional profile")
    if not account_id or not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]{0,63}", account_id):
        raise DomainError("Use a synthetic account alias beginning with a letter")
    if type(positions_complete) is not bool or type(lots_complete) is not bool:
        raise DomainError("Snapshot completeness must be explicit booleans")
    if data_environment not in {None, 'REAL', 'SYNTHETIC'}:
        raise DomainError('Data environment must be explicit REAL or SYNTHETIC')
    if as_of:
        try:
            as_of = date.fromisoformat(as_of).isoformat()
        except (TypeError, ValueError) as exc:
            raise DomainError("Source date must be ISO YYYY-MM-DD") from exc
    soup = BeautifulSoup(html, "lxml")
    source_hash = hashlib.sha256(html.encode()).hexdigest()
    positions, lots, warnings, cash = [], [], [], Decimal("0")
    issues = []
    if institution.lower() != 'generic':
        issues.append(issue('UNVALIDATED_INSTITUTION_ADAPTER',
            'Institution pattern is provisional until reviewed real anonymized HTML is supplied', account_id))
    if data_environment is None:
        issues.append(issue('UNKNOWN_DATA_ENVIRONMENT',
            'Identify whether this candidate evidence is REAL or SYNTHETIC', account_id))
    source_rows, cash_rows, row_kinds, broker_lot_refs = set(), set(), {}, set()
    omitted_rows = False
    omitted_lots = False
    cash_known = False
    cash_unresolved = False
    aliases = {alias: key for key, items in ALIASES.items() for alias in items}
    aliases.update({label: 'source_lot_id' for label in ('lot id', 'tax lot id', 'broker lot id', 'lot reference')})
    aliases.update({label: 'remaining_adjusted_basis' for label in (
        'remaining adjusted basis', 'remaining adjusted cost basis')})
    for table_index, table in enumerate(soup.find_all("table")):
        caption = table.find('caption', recursive=False)
        caption_text = caption.get_text(' ', strip=True).lower() if caption else ''
        if (re.search(r'\b(summary|totals?|allocation|performance)\b', caption_text)
                and not re.search(r'\b(holdings?|positions?|lots?)\b', caption_text)):
            issues.append(issue('AMBIGUOUS_SUMMARY_ROW',
                'Summary table excluded from holdings; review its coverage separately', account_id))
            omitted_rows = True
            continue
        rows = table.find_all("tr")
        if not rows:
            continue
        headers = [
            aliases.get(c.get_text(" ", strip=True).lower()) for c in rows[0].find_all(["th", "td"])
        ]
        if "market_value" not in headers:
            continue
        recognized = [header for header in headers if header]
        if len(recognized) != len(set(recognized)):
            raise DomainError("Ambiguous duplicated financial columns in source table", code=2)
        for row_index, row in enumerate(rows[1:], start=1):
            cells = row.find_all(["td", "th"])
            if len(cells) != len(headers):
                warnings.append("Skipped row with inconsistent columns")
                issues.append(issue('UNRESOLVED_SOURCE_ROW',
                    'Financial row column count is inconsistent; coverage remains partial', account_id))
                omitted_rows = True
                continue
            values = {key: c.get_text(" ", strip=True) for key, c in zip(headers, cells) if key}
            symbol = values.get("security", "").strip().upper()
            name = values.get("name", "")
            if (symbol in {'TOTAL', 'SUBTOTAL', 'GRAND TOTAL', 'ACCOUNT TOTAL', 'PORTFOLIO TOTAL'}
                    or name.strip().lower() in {'total', 'subtotal', 'grand total', 'account total', 'portfolio total'}):
                issues.append(issue('AMBIGUOUS_SUMMARY_ROW',
                    'Aggregate summary row excluded from holdings; do not accept it as a security', account_id))
                omitted_rows = True
                continue
            value = number(values.get("market_value", ""))
            if symbol in {"CASH", "USD"} or name.lower() in {
                "cash",
                "cash balance",
                "available cash",
            }:
                cash_signature = (symbol, name.strip().lower())
                if cash_signature in cash_rows:
                    raise DomainError("Duplicate cash balance row in source tables", code=2)
                cash_rows.add(cash_signature)
                if value is not None and value >= 0:
                    cash = add_exact(cash, value)
                    cash_known = True
                else:
                    omitted_rows = True
                    cash_unresolved = True
                    warnings.append("Unresolved cash balance omitted; review source manually")
                    issues.append(issue('UNKNOWN_CASH_COVERAGE',
                        'Cash row could not establish a balance; review the original cell', account_id))
                continue
            qty = number(values.get("quantity", ""))
            if not symbol or qty is None or value is None or qty < 0 or value < 0:
                warnings.append("Unresolved or ambiguous row omitted; review source manually")
                issues.append(issue('UNRESOLVED_SOURCE_ROW',
                    'Row identity, quantity or valuation is unavailable; coverage remains partial', account_id))
                omitted_rows = True
                continue
            asset = values.get("asset_type", "OTHER").upper().replace(" ", "_")
            if asset not in {"STOCK", "ETF", "MUTUAL_FUND", "TREASURY", "BOND", "CASH", "OTHER"}:
                asset = "OTHER"
            if asset == "OTHER":
                warnings.append(f"{symbol}: asset type unavailable; stored as unsupported OTHER")
            basis = number(values.get("cost_basis", ""))
            remaining_basis = number(values.get('remaining_adjusted_basis', ''))
            provenance = {}
            for column_index, field in enumerate(headers):
                if field in {'quantity', 'price', 'market_value', 'cost_basis', 'remaining_adjusted_basis'}:
                    text = cells[column_index].get_text(' ', strip=True)
                    if number(text) is not None:
                        provenance[field] = [{'source_hash': source_hash, 'table_index': table_index,
                            'row_index': row_index, 'column_index': column_index,
                            'displayed_precision': displayed_precision(text), 'source_text': text}]
            price_precision = displayed_precision(values.get('price', ''))
            value_precision = displayed_precision(values.get('market_value', ''))
            if price_precision is None:
                issues.append(issue('UNKNOWN_PRICE_PRECISION',
                    'Printed price precision is unavailable; verify before accepting this observation', symbol))
            position = dict(
                security=symbol,
                name=name,
                asset_type=asset,
                quantity=str(qty),
                market_value=str(value),
                price=number(values.get("price", "")),
                cost_basis=basis,
                as_of=as_of,
                displayed_price_precision=price_precision,
                displayed_market_value_precision=value_precision,
                cell_provenance=provenance,
            )
            acquired = values.get("acquisition_date")
            for identifier in ("cusip", "isin", "figi"):
                if values.get(identifier):
                    position[identifier] = values[identifier].strip().upper()
            signature = tuple(sorted(values.items()))
            if signature in source_rows:
                raise DomainError(f"{symbol}: duplicate source row", code=2)
            source_rows.add(signature)
            prior = next((p for p in positions if p["security"] == symbol), None)
            if prior:
                if not acquired or not row_kinds[symbol]:
                    raise DomainError(f"{symbol}: duplicate or mixed position/lot rows", code=2)
                for field in ("asset_type", "price", "cusip", "isin", "figi"):
                    previous, current = prior.get(field), position.get(field)
                    if previous is not None and current is not None and previous != current:
                        raise DomainError(f"{symbol}: conflicting {field} in source rows", code=2)
                    if previous is None and current is not None:
                        prior[field] = current
            if acquired and (basis is not None or remaining_basis is not None):
                try:
                    acquisition = date.fromisoformat(acquired)
                    source_lot_id = values.get('source_lot_id') or None
                    if source_lot_id:
                        if (symbol, source_lot_id) in broker_lot_refs:
                            raise DomainError(f'{symbol}: duplicated original broker lot reference', code=2)
                        broker_lot_refs.add((symbol, source_lot_id))
                        provenance['source_lot_id'] = [{'source_hash': source_hash,
                            'table_index': table_index, 'row_index': row_index,
                            'column_index': headers.index('source_lot_id')}]
                    reference = (account_id, symbol, source_lot_id) if source_lot_id else (
                        account_id, symbol, acquisition.isoformat(), table_index, row_index)
                    lot_id = f'{account_id}-{symbol}-' + hashlib.sha256(repr(reference).encode()).hexdigest()[:16]
                    lots.append(
                        dict(
                            id=lot_id,
                            security=symbol,
                            acquisition_date=acquisition.isoformat(),
                            quantity=str(qty),
                            remaining_quantity=str(qty),
                            cost_basis=str(basis) if basis is not None else None,
                            remaining_adjusted_basis=str(remaining_basis) if remaining_basis is not None else None,
                            basis_state='REVIEW_REQUIRED' if remaining_basis is None else 'OBSERVED',
                            source_lot_id=source_lot_id,
                            identity_status='UNRESOLVED',
                            identity_source=None,
                            saleable=False,
                            cell_provenance=provenance,
                            **{
                                identifier: position[identifier]
                                for identifier in ("cusip", "isin", "figi")
                                if identifier in position
                            },
                        )
                    )
                    issues.append(issue('UNVERIFIED_LOT_IDENTITY',
                        'Candidate lot needs original broker reference review or an explicit reviewed mapping', lot_id))
                    if remaining_basis is None:
                        issues.append(issue('UNKNOWN_LOT_BASIS_SEMANTICS',
                            'Printed cost basis is candidate evidence; remaining adjusted meaning needs source review', lot_id))
                except ValueError:
                    omitted_lots = True
                    warnings.append(f"{symbol}: acquisition date must be ISO YYYY-MM-DD")
            else:
                omitted_lots = True
            if prior:
                prior["quantity"] = str(add_exact(Decimal(prior["quantity"]), qty))
                prior["market_value"] = str(add_exact(Decimal(prior["market_value"]), value))
                for field, sources in provenance.items():
                    prior['cell_provenance'].setdefault(field, []).extend(sources)
                if prior['displayed_price_precision'] != price_precision:
                    prior['displayed_price_precision'] = None
                    issues.append(issue('UNKNOWN_PRICE_PRECISION',
                        'Lot rows show incompatible price precision; verify the position mark', symbol))
                if prior["cost_basis"] is not None and basis is not None:
                    prior["cost_basis"] = add_exact(prior['cost_basis'], basis)
                else:
                    prior["cost_basis"] = None
            else:
                positions.append(position)
                row_kinds[symbol] = bool(acquired)
            if basis is None:
                warnings.append(f"{symbol}: cost basis unavailable; aggregate basis is unknown")
    cash_known = cash_known and not cash_unresolved
    if not positions and not cash_known:
        raise DomainError("No supported position/cash table found; no state can be applied")
    if not cash_known:
        warnings.append("Cash balance unavailable")
        if not any(row['code'] == 'UNKNOWN_CASH_COVERAGE' for row in issues):
            issues.append(issue('UNKNOWN_CASH_COVERAGE',
                'No complete usable cash balance was supplied', account_id))
    if not as_of:
        warnings.append("Source snapshot date unavailable; observed position date remains unknown")
        issues.append(issue('UNKNOWN_SOURCE_DATE', 'Supply a verified source date; retrieval does not establish freshness', account_id))
    if not lots:
        warnings.append("Lot detail unavailable; tax analysis may be insufficient")
    if omitted_rows and (positions_complete or lots_complete):
        raise DomainError("Cannot confirm complete coverage after omitting source rows", code=2)
    if omitted_lots and lots_complete:
        raise DomainError("Cannot confirm complete lots without acquisition dates and basis", code=2)
    snapshot = Snapshot(
        account=dict(
            id=account_id, name=account_id, institution=institution, tax_status=tax_status
        ),
        positions=positions,
        lots=lots,
        cash=cash,
        cash_known=cash_known,
        positions_complete=positions_complete,
        lots_complete=lots_complete,
        source_timestamp=as_of,
        source_hash=source_hash,
        warnings=warnings,
        issues=issues,
        institution_status='PROVISIONAL' if institution.lower() != 'generic' else None,
        status='REVIEW_REQUIRED' if issues else 'PARSED',
        data_environment=data_environment,
        provenance={
            'positions': {'source_timestamp': as_of, 'coverage': 'COMPLETE' if positions_complete else 'PARTIAL'},
            'lots': {'source_timestamp': as_of, 'coverage': 'COMPLETE' if lots_complete else 'PARTIAL'},
            'cash': {'source_timestamp': as_of if cash_known else None,
                     'coverage': 'COMPLETE' if cash_known else 'UNKNOWN'}},
    )
    return snapshot.model_dump(mode="json")
