"""Public file contract for explicit hypothetical historical experiments."""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool


class HistoricalPoint(BaseModel):
    model_config = ConfigDict(extra='forbid')
    date: str
    total_return_index: Decimal = Field(gt=0, allow_inf_nan=False)


class HistoryProvenance(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: str | None = None
    frequency: str | None = None
    source_id: str | None = None
    data_environment: Literal['REAL', 'SYNTHETIC'] = None
    expected_sessions: list[str] | None = None


class CandidateInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str
    weights: dict[str, Decimal]


class ContributionInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    date: str
    amount: Decimal = Field(ge=0, allow_inf_nan=False)


class BacktestInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    start: str | None = None
    end: str | None = None
    candidates: list[CandidateInput] = Field(default_factory=list)
    candidate_ids: list[str] = Field(default_factory=list)
    data_environment: Literal['REAL', 'SYNTHETIC'] = None
    mode: Literal['HYPOTHETICAL_CURRENT_ALLOCATION', 'HYPOTHETICAL_TARGET_ALLOCATION'] = 'HYPOTHETICAL_TARGET_ALLOCATION'
    history: dict[str, list[HistoricalPoint]] = Field(default_factory=dict)
    history_provenance: HistoryProvenance = Field(default_factory=HistoryProvenance)
    cash_return: Decimal | None = Field(default=None, allow_inf_nan=False)
    fees: Decimal | None = Field(default=None, ge=0, allow_inf_nan=False)
    starting_value: Decimal | None = Field(default=None, gt=0, allow_inf_nan=False)
    rebalancing: str | None = None
    contribution_schedule: list[ContributionInput] = Field(default_factory=list)
    manifest_ids: list[str] = Field(default_factory=list)
    run_ids: list[str] = Field(default_factory=list)
    policy_id: str | None = None
    as_of: str | None = None
    slippage: Decimal = Field(default=Decimal(0), ge=0, allow_inf_nan=False)
    taxes: StrictBool | dict = False
