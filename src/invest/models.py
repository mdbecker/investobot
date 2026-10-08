"""Validated interchange models. Decimal strings preserve ledger precision."""

from datetime import date, datetime, timezone
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class DomainError(Exception):
    def __init__(self, message, code=1):
        super().__init__(message)
        self.code = code


class TaxStatus(StrEnum):
    TAXABLE = "TAXABLE"
    TAX_DEFERRED = "TAX_DEFERRED"
    TAX_FREE = "TAX_FREE"
    OTHER = "OTHER"


class Account(BaseModel):
    id: str
    name: str
    institution: str = "manual"
    account_type: str = "brokerage"
    tax_status: TaxStatus = TaxStatus.TAXABLE
    currency: str = "USD"
    active: bool = True
    history_complete: bool = False


class Position(BaseModel):
    model_config = ConfigDict(extra="allow")
    security: str
    name: str = ""
    asset_type: str = "OTHER"
    quantity: Decimal = Field(ge=0)
    market_value: Decimal = Field(ge=0)
    price: Decimal | None = Field(default=None, ge=0)
    cost_basis: Decimal | None = Field(default=None, ge=0)
    as_of: date = Field(default_factory=date.today)


class Lot(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    security: str
    acquisition_date: date
    quantity: Decimal = Field(gt=0)
    remaining_quantity: Decimal = Field(ge=0)
    cost_basis: Decimal = Field(ge=0)


class Snapshot(BaseModel):
    account: Account
    positions: list[Position]
    lots: list[Lot] = []
    cash: Decimal = Field(default=Decimal("0"), ge=0)
    cash_known: bool = True
    source_timestamp: str | None = None
    imported_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source_hash: str
    warnings: list[str] = []
    status: str = "PARSED"


def decimal(value):
    result = Decimal(str(value))
    if not result.is_finite():
        raise DomainError("Numeric values must be finite")
    return result
