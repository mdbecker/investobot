"""Authoritative, source-backed earnings input contract; no disclosure fetching."""

import re
from datetime import date, datetime
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
    StrictBool,
    field_validator,
    model_validator,
)

from .political_models import safe_url

Text = Annotated[str, Field(min_length=1, max_length=4000)]
Year = Annotated[int, Field(strict=True, ge=1900, le=2200)]
FiscalPeriod = Literal['Q1', 'Q2', 'Q3', 'Q4', 'FY', 'YTD', 'TTM']
Basis = Literal['GAAP', 'NON_GAAP', 'IFRS', 'OTHER']
MetricCode = Literal[
    'REVENUE', 'GROSS_PROFIT', 'OPERATING_INCOME', 'NET_INCOME', 'DILUTED_EPS',
    'OPERATING_CASH_FLOW', 'CAPITAL_EXPENDITURES', 'FREE_CASH_FLOW',
    'DILUTED_WEIGHTED_AVERAGE_SHARES', 'SEGMENT_REVENUE', 'SEGMENT_OPERATING_INCOME', 'OTHER',
]
CURRENCIES = frozenset('USD EUR GBP CAD JPY CHF AUD CNY HKD INR KRW SEK NOK DKK NZD BRL MXN ZAR SGD TWD'.split())


def exact_decimal(value):
    if not isinstance(value, str) or not re.fullmatch(r'-?\d+(?:\.\d+)?', value):
        raise ValueError('financial values require finite plain decimal strings')
    return Decimal(value)


FinancialDecimal = Annotated[
    Decimal, BeforeValidator(exact_decimal, json_schema_input_type=str),
    PlainSerializer(str, return_type=str),
]


def iso_date(value):
    if not isinstance(value, (str, date)) or isinstance(value, datetime):
        raise ValueError('dates require ISO date strings')
    if isinstance(value, str) and not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('dates require YYYY-MM-DD')
    return value


Date = Annotated[date, BeforeValidator(iso_date)]


def unit_valid(value):
    if not isinstance(value, str):
        raise ValueError('financial units require strings')
    if value not in CURRENCIES and value not in {'shares', 'percent', 'ratio', 'count'}:
        if not value.endswith('/share') or value[:-6] not in CURRENCIES:
            raise ValueError('unsupported explicit financial unit')
    return value


Unit = Annotated[str, BeforeValidator(unit_valid)]


def cik_valid(value):
    if value is None:
        return value
    if not isinstance(value, str) or not re.fullmatch(r'\d{1,10}', value):
        raise ValueError('CIK requires one to ten digits as a string')
    return value.zfill(10)


CIK = Annotated[str | None, BeforeValidator(cik_valid)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class EarningsCompany(StrictModel):
    name: Text
    ticker: Text | None = None
    cik: CIK = None
    security_id: Text | None = None


class ReportingPeriod(StrictModel):
    fiscal_year: Year
    fiscal_period: FiscalPeriod
    period_end: Date


class EarningsSource(StrictModel):
    id: Text
    source_type: Text
    url: Text
    accession_number: Text | None = None
    filed_at: Date | None = None
    accessed_at: Date
    publisher: Text
    cik: CIK = None
    accepted_at: datetime | None = None
    is_amendment: StrictBool = False
    is_restatement: StrictBool = False
    original_accession_number: Text | None = None

    @field_validator('url')
    @classmethod
    def normalize_url(cls, value):
        return safe_url(value)

    @model_validator(mode='after')
    def provenance(self):
        if self.source_type.startswith('SEC_') and not self.accession_number:
            raise ValueError('SEC sources require accession references')
        if self.filed_at and self.filed_at > self.accessed_at:
            raise ValueError('source filed after retrieval')
        if self.accepted_at:
            if self.accepted_at.tzinfo is None:
                raise ValueError('filing acceptance timestamp requires timezone')
            if self.accepted_at.date() > self.accessed_at:
                raise ValueError('filing accepted after retrieval')
            if self.filed_at and self.accepted_at.date() < self.filed_at:
                raise ValueError('filing acceptance precedes filed date')
        if self.is_amendment or self.is_restatement:
            if not self.original_accession_number or self.original_accession_number == self.accession_number:
                raise ValueError('amendments and restatements require distinct original accession')
        return self


def compatible_unit(code, unit):
    if code == 'DILUTED_EPS' and not unit.endswith('/share'):
        raise ValueError('EPS requires currency/share unit')
    if code == 'DILUTED_WEIGHTED_AVERAGE_SHARES' and unit != 'shares':
        raise ValueError('weighted-average shares require shares unit')
    if code not in {'OTHER', 'DILUTED_EPS', 'DILUTED_WEIGHTED_AVERAGE_SHARES'}:
        if unit not in CURRENCIES:
            raise ValueError('monetary metric requires currency unit')


class EarningsMetric(StrictModel):
    id: Text
    metric_code: MetricCode
    metric_label: Text
    metric_definition: Text | None = None
    value: FinancialDecimal
    unit: Unit
    accounting_basis: Basis
    measurement_type: Literal['REPORTED']
    period_type: Literal['INSTANT', 'DURATION']
    period_start: Date | None = None
    period_end: Date
    fiscal_year: Year
    fiscal_period: FiscalPeriod
    period_length: Literal['QUARTER', 'YTD', 'ANNUAL', 'TTM'] | None = None
    scope: Literal['CONSOLIDATED', 'SEGMENT']
    segment_name: Text | None = None
    source_id: Text
    source_locator: Text
    xbrl_taxonomy: Text | None = None
    xbrl_concept: Text | None = None
    source_value: FinancialDecimal | None = None
    source_unit: Text | None = None
    source_scale: FinancialDecimal | None = None
    reconciliation_disclosed: StrictBool | None = None

    @model_validator(mode='after')
    def measurement(self):
        self.metric_definition = self.metric_definition or self.metric_label
        if bool(self.segment_name) != (self.scope == 'SEGMENT'):
            raise ValueError('segment metric scope requires segment name exclusively')
        if self.metric_code.startswith('SEGMENT_') and self.scope != 'SEGMENT':
            raise ValueError('segment metric code requires segment scope')
        compatible_unit(self.metric_code, self.unit)
        if bool(self.xbrl_taxonomy) != bool(self.xbrl_concept):
            raise ValueError('XBRL taxonomy and concept must be supplied together')
        inferred = 'ANNUAL' if self.fiscal_period == 'FY' else (
            self.fiscal_period if self.fiscal_period in {'YTD', 'TTM'} else 'QUARTER')
        self.period_length = self.period_length or inferred
        if self.period_type == 'INSTANT':
            if self.period_start is not None:
                raise ValueError('instant measurements cannot have a start date')
            if self.metric_code != 'OTHER':
                raise ValueError('standard income/cash-flow/share metrics require duration')
        else:
            if self.period_start is None or self.period_start > self.period_end:
                raise ValueError('duration measurements require valid start/end dates')
            days = (self.period_end - self.period_start).days + 1
            if self.period_length == 'QUARTER':
                if self.fiscal_period not in {'Q1', 'Q2', 'Q3', 'Q4'} or not 70 <= days <= 110:
                    raise ValueError('quarterly measurement must have quarterly duration')
            elif self.period_length in {'ANNUAL', 'TTM'}:
                expected = 'FY' if self.period_length == 'ANNUAL' else 'TTM'
                if self.fiscal_period != expected or not 350 <= days <= 380:
                    raise ValueError('annual/TTM measurement requires matching fiscal context and duration')
            else:
                ranges = {'Q1': (70, 110), 'Q2': (150, 220), 'Q3': (240, 310),
                          'Q4': (350, 380), 'YTD': (70, 380)}
                low, high = ranges.get(self.fiscal_period, (1, 0))
                if not low <= days <= high:
                    raise ValueError('YTD measurement requires consistent fiscal context and duration')
        scaling = [self.source_value is not None, self.source_unit is not None,
                   self.source_scale is not None]
        if any(scaling):
            if not all(scaling) or self.source_scale <= 0:
                raise ValueError('source scaling requires value, unit and positive scale')
            scales = {'THOUSANDS': Decimal('1000'), 'MILLIONS': Decimal('1000000'),
                      'BILLIONS': Decimal('1000000000')}
            source_base = self.source_unit
            expected_scale = Decimal('1')
            for suffix, scale in scales.items():
                if self.source_unit.endswith('_' + suffix):
                    source_base = self.source_unit.removesuffix('_' + suffix)
                    expected_scale = scale
            if source_base != self.unit or self.source_scale != expected_scale:
                raise ValueError('source unit and scale must match normalized unit')
            decimals = [self.value, self.source_value, self.source_scale]
            with localcontext() as context:
                context.prec = max(28, sum(len(v.as_tuple().digits) + abs(v.as_tuple().exponent)
                                           for v in decimals) + 2)
                if self.source_value * self.source_scale != self.value:
                    raise ValueError('normalized value contradicts exact source scaling')
        return self


class EarningsGuidance(StrictModel):
    id: Text
    metric_code: MetricCode
    period_start: Date
    period_end: Date
    lower_value: FinancialDecimal | None = None
    upper_value: FinancialDecimal | None = None
    unit: Unit
    accounting_basis: Basis
    guidance_status: Literal['ISSUED', 'REVISED', 'REAFFIRMED', 'WITHDRAWN']
    source_id: Text
    source_locator: Text
    qualifiers: str = Field(default='', max_length=4000)
    issued_at: Date | None = None
    prior_guidance_id: Text | None = None

    @model_validator(mode='after')
    def outlook(self):
        if self.period_start > self.period_end:
            raise ValueError('guidance period dates are reversed')
        compatible_unit(self.metric_code, self.unit)
        if self.lower_value is None and self.upper_value is None:
            if self.guidance_status != 'WITHDRAWN' or not self.prior_guidance_id:
                raise ValueError('numeric guidance needs bounds or withdrawn prior reference')
        if self.lower_value is not None and self.upper_value is not None:
            if self.lower_value > self.upper_value:
                raise ValueError('guidance lower exceeds upper bound')
        if self.prior_guidance_id == self.id:
            raise ValueError('guidance cannot reference itself')
        return self


class EarningsFinding(StrictModel):
    id: Text
    category: Literal[
        'VERIFIED_FACT', 'MANAGEMENT_EXPLANATION', 'ANALYST_INTERPRETATION', 'RISK', 'UNRESOLVED',
    ]
    statement: Text
    source_id: Text | None = None
    source_locator: Text | None = None
    limitations: list[Text] = Field(default_factory=list)

    @model_validator(mode='after')
    def evidence(self):
        if self.category != 'UNRESOLVED' and not (self.source_id and self.source_locator):
            raise ValueError('findings require source evidence; missing evidence is UNRESOLVED')
        if bool(self.source_id) != bool(self.source_locator):
            raise ValueError('finding source and locator must be supplied together')
        return self


class EarningsResearchInput(StrictModel):
    schema_version: Literal['1.0']
    research_type: Literal['EARNINGS_FINANCIAL_STATEMENTS']
    company: EarningsCompany
    reporting_period: ReportingPeriod
    researched_as_of: Date
    coverage_status: Literal['COMPLETE_WITHIN_DECLARED_SCOPE', 'PARTIAL', 'BLOCKED']
    sources: list[EarningsSource]
    metrics: list[EarningsMetric]
    guidance: list[EarningsGuidance]
    findings: list[EarningsFinding]
    limitations: list[Text]

    @model_validator(mode='after')
    def consistency(self):
        if self.reporting_period.period_end > self.researched_as_of:
            raise ValueError('reporting period extends beyond research date')
        if self.researched_as_of > date.today():
            raise ValueError('research date is in the future')
        for collection in [self.sources, self.metrics, self.guidance, self.findings]:
            if len({item.id for item in collection}) != len(collection):
                raise ValueError('duplicate record identifiers')
        if not self.metrics and self.coverage_status == 'COMPLETE_WITHIN_DECLARED_SCOPE':
            raise ValueError('empty financial research must declare incomplete coverage')
        sources = {s.id: s for s in self.sources}
        facts = set()
        for source in self.sources:
            if source.accessed_at > self.researched_as_of:
                raise ValueError('source retrieved after research date')
            if source.cik and self.company.cik and source.cik != self.company.cik:
                raise ValueError('source reporting entity CIK contradicts company')
            parts = urlsplit(source.url)
            if parts.hostname == 'sec.gov' or parts.hostname.endswith('.sec.gov'):
                match = re.search(r'/Archives/edgar/data/(\d+)/', parts.path, re.IGNORECASE)
                if not match:
                    match = re.search(r'/(?:api/xbrl/companyfacts|submissions)/CIK(\d+)\.json$',
                                      parts.path, re.IGNORECASE)
                if match and self.company.cik and match[1].zfill(10) != self.company.cik:
                    raise ValueError('SEC filing URL reporting entity contradicts company CIK')
        for metric in self.metrics:
            if metric.source_id not in sources:
                raise ValueError('invalid metric source reference')
            if metric.period_end > self.reporting_period.period_end:
                raise ValueError('metric period exceeds researched reporting period')
            if metric.fiscal_year > self.reporting_period.fiscal_year:
                raise ValueError('metric fiscal year exceeds declared reporting context')
            if metric.period_end == self.reporting_period.period_end:
                if metric.fiscal_year != self.reporting_period.fiscal_year:
                    raise ValueError('current metric fiscal year contradicts reporting context')
                if (metric.fiscal_period not in {'YTD', 'TTM'} and
                        self.reporting_period.fiscal_period not in {'YTD', 'TTM'} and
                        metric.fiscal_period != self.reporting_period.fiscal_period):
                    raise ValueError('current metric fiscal period contradicts reporting context')
            source = sources[metric.source_id]
            if source.filed_at and metric.period_end > source.filed_at:
                raise ValueError('reported metric period ends after source filing')
            if metric.xbrl_concept and not source.accession_number:
                raise ValueError('XBRL observation requires filing accession')
            key = (metric.metric_code, metric.metric_definition, metric.accounting_basis,
                   metric.unit, metric.period_type, metric.period_start, metric.period_end,
                   metric.scope, metric.segment_name)
            if key in facts:
                raise ValueError('duplicate or conflicting observations of the same reported fact')
            facts.add(key)
        for guidance in self.guidance:
            if guidance.source_id not in sources:
                raise ValueError('invalid guidance source reference')
            source = sources[guidance.source_id]
            if guidance.issued_at and guidance.issued_at > self.researched_as_of:
                raise ValueError('guidance issued after research date')
            if guidance.issued_at and guidance.issued_at > source.accessed_at:
                raise ValueError('guidance issued after source retrieval')
        for finding in self.findings:
            if finding.source_id and finding.source_id not in sources:
                raise ValueError('invalid finding source reference')
        return self


def load_earnings(path):
    return EarningsResearchInput.model_validate_json(Path(path).read_text())
