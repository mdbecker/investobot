"""Validated interchange models. Decimal strings preserve ledger precision."""

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator


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
    tax_status: TaxStatus = TaxStatus.OTHER
    currency: str = "USD"
    active: bool = True
    history_complete: StrictBool = False


AssetType = Literal["STOCK", "ETF", "MUTUAL_FUND", "TREASURY", "BOND", "OTHER"]


class ClassificationInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    asset_type: AssetType
    source: str = Field(min_length=1, max_length=1000)


class AccountUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    reason: str = Field(min_length=1, max_length=1000)
    source: str = Field(min_length=1, max_length=1000)
    name: str = Field(default=None, min_length=1, max_length=200)
    institution: str = Field(default=None, min_length=1, max_length=200)
    account_type: str = Field(default=None, min_length=1, max_length=200)
    tax_status: TaxStatus = None
    currency: str = Field(default=None, pattern=r"^[A-Z]{3}$")
    active: StrictBool = None
    history_complete: StrictBool = None


class Position(BaseModel):
    model_config = ConfigDict(extra="allow")
    security: str
    name: str = ""
    asset_type: str = "OTHER"
    quantity: Decimal = Field(ge=0)
    market_value: Decimal = Field(ge=0)
    price: Decimal | None = Field(default=None, ge=0)
    cost_basis: Decimal | None = Field(default=None, ge=0)
    as_of: date | None = None


class Lot(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    security: str
    acquisition_date: date
    quantity: Decimal = Field(gt=0)
    remaining_quantity: Decimal = Field(ge=0)
    cost_basis: Decimal | None = Field(default=None, ge=0)


class Snapshot(BaseModel):
    model_config = ConfigDict(extra='forbid')
    account: Account
    positions: list[Position]
    lots: list[Lot] = []
    cash: Decimal = Field(default=Decimal("0"), ge=0)
    cash_known: StrictBool = False
    positions_complete: StrictBool = False
    lots_complete: StrictBool = False
    source_timestamp: str | None = None
    imported_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source_hash: str
    warnings: list[str] = []
    status: str = "PARSED"
    data_environment: Literal['REAL', 'SYNTHETIC'] | None = None
    provenance: dict[str, dict] | None = None
    issues: list[dict] = []
    institution_status: Literal['PROVISIONAL', 'VERIFIED'] | None = None

    @field_validator('source_timestamp')
    @classmethod
    def valid_source_timestamp(cls, value):
        if value is not None:
            if len(value) == 10:
                date.fromisoformat(value)
            else:
                parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
                if parsed.tzinfo is None:
                    raise ValueError('Source datetime requires a timezone')
        return value

    @model_validator(mode="before")
    @classmethod
    def explicit_cash(cls, value):
        if isinstance(value, dict) and "cash" in value and "cash_known" not in value:
            return dict(value, cash_known=True)
        return value


def decimal(value):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise DomainError("Invalid numeric value") from exc
    if not result.is_finite():
        raise DomainError("Numeric values must be finite")
    return result


Nonnegative = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
Positive = Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
Weight = Annotated[Decimal, Field(ge=0, le=1, allow_inf_nan=False)]


class PlanningConstraints(BaseModel):
    model_config = ConfigDict(extra="forbid")
    eligible_accounts: list[str] = Field(default_factory=list)
    permitted_securities: dict[str, list[str]] = Field(default_factory=dict)
    excluded_positions: list[str] = Field(default_factory=list)
    cash_minimums: dict[str, Nonnegative] = Field(default_factory=dict)
    target_tolerance: Weight = Decimal("0.01")
    short_term_gain_budget: Nonnegative | None = None
    long_term_gain_budget: Nonnegative | None = None
    trade_increments: dict[str, dict[str, Positive]] = Field(default_factory=dict)
    price_max_age_days: int = Field(default=1, ge=0)


class TargetInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str | None = None
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=10000)
    data_environment: Literal['REAL', 'SYNTHETIC'] | None = None
    status: Literal["DRAFT", "ACTIVE", "ARCHIVED"] = "DRAFT"
    target_allocations: dict[str, Weight]
    planning_constraints: PlanningConstraints = Field(default_factory=PlanningConstraints)

    @model_validator(mode="after")
    def total_weights(self):
        if not self.name.strip() or not self.target_allocations:
            raise ValueError("A target requires a name and investable allocations")
        if abs(sum(self.target_allocations.values(), Decimal("0")) - 1) > Decimal("0.000001"):
            raise ValueError("Target weights must total 1 (100%) within 0.000001")
        return self


class SecurityTickerAlias(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticker: str = Field(min_length=1, max_length=32, pattern=r"^[A-Z0-9.\-^]+$")
    source: str = Field(min_length=1, max_length=1000)


class IssuerIdentityEvidence(BaseModel):
    model_config = ConfigDict(extra='forbid')
    source_locator: str = Field(min_length=1, max_length=2000)
    source: str = Field(min_length=1, max_length=1000)
    reviewed: StrictBool
    cik: str = Field(pattern=r'^\d{10}$')
    lei: str | None = Field(default=None, pattern=r'^[A-Z0-9]{20}$')

    @model_validator(mode='after')
    def reviewed_locator(self):
        parts = urlsplit(self.source_locator)
        if (not self.reviewed or parts.scheme != 'https' or not parts.hostname
                or parts.username is not None or parts.password is not None
                or parts.query or parts.fragment or any(char.isspace() for char in self.source_locator)):
            raise ValueError('Issuer identity needs reviewed credential-free HTTPS source evidence')
        return self


class SecurityInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticker: str = Field(min_length=1, max_length=32, pattern=r"^[A-Z0-9.\-^]+$")
    name: str = Field(min_length=1, max_length=200)
    asset_type: Literal["STOCK", "ETF", "MUTUAL_FUND", "BOND", "TREASURY", "OTHER"]
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    cusip: str | None = None
    isin: str | None = None
    figi: str | None = None
    source: str = Field(min_length=1, max_length=1000)
    ticker_aliases: list[SecurityTickerAlias] | None = None
    cik: str | None = Field(default=None, pattern=r'^\d{10}$')
    lei: str | None = Field(default=None, pattern=r'^[A-Z0-9]{20}$')
    issuer_id: str | None = None
    issuer_identity_evidence: IssuerIdentityEvidence | None = None
    data_environment: Literal['REAL', 'SYNTHETIC'] | None = None

    @model_validator(mode='after')
    def sourced_issuer(self):
        if any(value is not None for value in (self.cik, self.lei, self.issuer_id,
                                               self.issuer_identity_evidence)):
            evidence = self.issuer_identity_evidence
            if (not self.cik or self.issuer_id != self.cik or evidence is None
                    or self.data_environment is None or evidence.cik != self.cik
                    or evidence.lei != self.lei):
                raise ValueError('Issuer mapping needs matching reviewed strong IDs and explicit environment')
        return self


class ActivityAllocation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lot_id: str = Field(min_length=1)
    quantity: Positive


class Activity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    activity_id: str = Field(min_length=1)
    account_id: str = Field(min_length=1)
    type: Literal["BUY", "SELL", "TRANSFER_IN", "TRANSFER_OUT", "DIVIDEND", "INTEREST", "FEE", "CASH_DEPOSIT", "CASH_WITHDRAWAL", "DIVIDEND_REINVESTMENT", "STOCK_SPLIT", "RETURN_OF_CAPITAL"]
    date: date
    event_timestamp: str | None = None
    security: str | None = None
    quantity: Positive | None = None
    price: Nonnegative | None = None
    fee: Nonnegative = Decimal("0")
    amount: Positive | None = None
    lot_allocations: list[ActivityAllocation] | None = None
    source: str | None = None
    to_account: str | None = None
    from_account: str | None = None
    classification: str | None = None
    split_ratio: Positive | None = None

    @field_validator('event_timestamp')
    @classmethod
    def timestamp(cls, value):
        return Snapshot.valid_source_timestamp(value)

    @model_validator(mode="after")
    def required_values(self):
        if self.event_timestamp and self.event_timestamp[:10] != self.date.isoformat():
            raise ValueError('Event timestamp must match the confirmed activity date')
        if self.type == 'STOCK_SPLIT':
            if not self.security or self.split_ratio is None:
                raise ValueError('Stock split requires security and explicit ratio')
        elif self.type == 'RETURN_OF_CAPITAL':
            if not self.security or self.amount is None:
                raise ValueError('Return of capital requires security and amount')
        elif self.type == 'DIVIDEND_REINVESTMENT':
            if not self.security or self.quantity is None or self.price is None or self.amount is None:
                raise ValueError('Reinvestment requires security, gross amount, quantity and price')
        elif self.type in {"BUY", "SELL", "TRANSFER_IN", "TRANSFER_OUT"}:
            if not self.security or self.quantity is None or self.price is None:
                raise ValueError("Trade activities require security, quantity and price")
        elif self.amount is None:
            raise ValueError("Cash activities require amount")
        return self
