"""Strict human-approved trading policy interchange; approval belongs to the domain."""

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StrictBool

from invest.tax_policy import AnnualTaxPolicy, HarvestReviewPolicy

Text = Annotated[str, Field(strict=True, min_length=1, max_length=4000, pattern=r'\S')]
PlainDecimal = Annotated[str, Field(strict=True, pattern=r'^\d+(?:\.\d+)?$')]


def positive(value):
    if Decimal(value) <= 0:
        raise ValueError('Execution increment must be positive')
    return value


def fraction(value):
    if Decimal(value) > 1:
        raise ValueError('Allocation or tax rate must be a fraction between zero and one')
    return value


PositiveDecimal = Annotated[PlainDecimal, AfterValidator(positive)]
Fraction = Annotated[PlainDecimal, AfterValidator(fraction)]
Environment = Literal['REAL', 'SYNTHETIC']


class TradingPermission(BaseModel):
    """Independent permissions never default from another permission."""

    model_config = ConfigDict(extra='forbid')
    can_buy: StrictBool
    can_sell: StrictBool
    can_hold: StrictBool
    share_increment: PositiveDecimal | None = None


class HarvestPriceInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    price: PlainDecimal | None = None
    currency: Text | None = None
    data_environment: Environment | None = None
    as_of: Text | None = None
    source: Text | None = None


class HarvestReplacementInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    security: Text
    substantially_identical: StrictBool | None = None
    approved_for_purchase: StrictBool | None = None
    source: Text | None = None
    source_locator: Text | None = None


class SavedHarvestReview(HarvestReviewPolicy):
    price_observations: dict[Text, HarvestPriceInput] = Field(default_factory=dict)
    replacement: HarvestReplacementInput | None = None


class PolicyTaxBudget(AnnualTaxPolicy):
    """Reuse household tax coverage fields while requiring exact financial strings."""

    year: int = Field(strict=True, ge=1900, le=9999)
    annual_allowance: PlainDecimal | None = None
    short_term_rate: Fraction | None = None
    long_term_rate: Fraction | None = None
    proposed_positive_tax_cost: PlainDecimal | None = None
    currency: Literal['USD'] | None = None
    covered_account_ids: list[Text] | None = None
    data_environment: Environment | None = None
    source: Text | None = None
    id: Text | None = None


class TradingPolicyInput(BaseModel):
    """Submitted fields are preserved with model_dump(exclude_unset=True).

    Identity resolution, immutable version conflicts and explicit confirmation
    remain checks performed by planning.save_policy, never by this model.
    """

    model_config = ConfigDict(extra='forbid')
    version: Text
    source: Text
    data_environment: Environment
    permissions: dict[Text, dict[Text, TradingPermission]]
    id: Text | None = None
    minimum_notional: PlainDecimal = '25'
    fee_per_trade: PlainDecimal | None = None
    quarterly_months: list[Annotated[int, Field(strict=True, ge=1, le=12)]] = Field(
        default_factory=lambda: [3, 6, 9, 12])
    drift_trigger: Fraction = '0.05'
    max_position_age_days: int = Field(default=120, strict=True, ge=0)
    max_cash_age_days: int = Field(default=120, strict=True, ge=0)
    cash_floors: dict[Text, PlainDecimal] = Field(default_factory=dict)
    cash_confirmation: dict[Text, StrictBool] = Field(default_factory=dict)
    annual_tax_budget: PolicyTaxBudget | None = None
    exception_approved: StrictBool = False
    exception_reason: Text | None = None
    baseline_environment: Environment | None = None
    price_environment: Environment | None = None
    harvest_review: SavedHarvestReview | None = None
