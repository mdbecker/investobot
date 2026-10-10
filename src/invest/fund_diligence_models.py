"""Strict dated fund disclosures; validation cannot establish factual source truth."""

import re
from datetime import date
from decimal import Decimal, localcontext
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import Field, field_serializer, field_validator, model_validator

from invest.earnings_models import Date, FinancialDecimal, StrictModel, Text
from invest.political_models import safe_url

Identifier = Annotated[str, Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9_.:-]*$', max_length=200)]
CIK = Annotated[str, Field(pattern=r'^\d{10}$')]
SeriesID = Annotated[str, Field(pattern=r'^S\d{9}$')]
ClassID = Annotated[str, Field(pattern=r'^C\d{9}$')]
Count = Annotated[int, Field(strict=True, ge=0)]
FEE_CODES = frozenset({'GROSS_EXPENSE_RATIO', 'NET_EXPENSE_RATIO', 'DISTRIBUTION_12B1_FEE',
                       'MAX_FRONT_LOAD', 'MAX_DEFERRED_LOAD', 'REDEMPTION_FEE'})
ETF_CODES = frozenset({'MEDIAN_BID_ASK_SPREAD', 'AVG_PREMIUM_DISCOUNT', 'AVG_DAILY_DOLLAR_VOLUME'})
DISTRIBUTION_CODES = frozenset({'SHORT_TERM_CAPITAL_GAIN_DISTRIBUTION',
                                'LONG_TERM_CAPITAL_GAIN_DISTRIBUTION',
                                'ORDINARY_INCOME_DISTRIBUTION', 'RETURN_OF_CAPITAL_DISTRIBUTION'})
MetricCode = Literal['GROSS_EXPENSE_RATIO', 'NET_EXPENSE_RATIO', 'DISTRIBUTION_12B1_FEE',
                     'MAX_FRONT_LOAD', 'MAX_DEFERRED_LOAD', 'REDEMPTION_FEE',
                     'PORTFOLIO_TURNOVER', 'NET_ASSETS', 'MEDIAN_BID_ASK_SPREAD',
                     'AVG_PREMIUM_DISCOUNT', 'AVG_DAILY_DOLLAR_VOLUME',
                     'SHORT_TERM_CAPITAL_GAIN_DISTRIBUTION', 'LONG_TERM_CAPITAL_GAIN_DISTRIBUTION',
                     'ORDINARY_INCOME_DISTRIBUTION', 'RETURN_OF_CAPITAL_DISTRIBUTION']


def sec_host(url):
    host = (urlsplit(url).hostname or '').lower()
    return host == 'sec.gov' or host.endswith('.sec.gov')


class FundIdentity(StrictModel):
    name: Text
    ticker: Text | None
    exchange: Text | None
    isin: Text | None
    registrant_cik: CIK
    series_id: SeriesID
    class_id: ClassID
    class_name: Text
    adviser: Text | None
    security_id: Text | None
    fund_type: Literal['ETF', 'MUTUAL_FUND']
    strategy_type: Literal['INDEX', 'ACTIVE']

    @field_validator('fund_type', mode='before')
    @classmethod
    def supported_structure(cls, value):
        if value not in {'ETF', 'MUTUAL_FUND'}:
            raise ValueError('UNSUPPORTED_FUND_STRUCTURE')
        return value


class FundScope(StrictModel):
    researched_as_of: Date
    coverage_status: Literal['COMPLETE_WITHIN_DECLARED_SCOPE', 'PARTIAL', 'BLOCKED']
    coverage_notes: Text


class FundSource(StrictModel):
    id: Identifier
    source_type: Text
    publisher: Text
    url: Text
    published_at: Date | None
    filed_at: Date | None
    accessed_at: Date
    source_locator: Text
    accession_number: Annotated[str, Field(pattern=r'^\d{10}-\d{2}-\d{6}$')] | None
    registrant_cik: CIK | None
    series_id: SeriesID | None
    class_id: ClassID | None

    @field_validator('url')
    @classmethod
    def public_url(cls, value):
        parts = urlsplit(value)
        if parts.username is not None or parts.password is not None:
            raise ValueError('credential-bearing source URL is forbidden')
        return safe_url(value)

    @model_validator(mode='after')
    def source_identity(self):
        for observed in (self.published_at, self.filed_at):
            if observed and observed > self.accessed_at:
                raise ValueError('source disclosure follows access date')
        if sec_host(self.url):
            parts = urlsplit(self.url)
            archive = re.search(r'/Archives/edgar/data/(\d+)/(\d{18})/', parts.path, re.I)
            if archive:
                if self.registrant_cik and archive[1].zfill(10) != self.registrant_cik:
                    raise ValueError('SEC archive CIK contradicts fund registrant')
                if not self.accession_number or archive[2] != self.accession_number.replace('-', ''):
                    raise ValueError('SEC accession contradicts archive URL')
            elif '/Archives/' in parts.path:
                raise ValueError('SEC filing needs an unambiguous accession locator')
        elif self.source_type.startswith('SEC_'):
            raise ValueError('SEC identity evidence requires an original SEC URL')
        return self


class FundMethodology(StrictModel):
    objective: Text
    index_name: Text | None
    index_provider: Text | None
    benchmark_name: Text | None
    selection_rules: Text | None
    weighting_method: Text | None
    rebalance_policy: Text | None
    reconstitution_policy: Text | None
    replication_method: Text | None
    active_approach: Text | None
    source_ids: list[Identifier] = Field(min_length=1)
    uncertainty: Text


class FundSnapshot(StrictModel):
    as_of_date: Date | None
    coverage: Literal['FULL', 'TOP_N', 'PARTIAL', 'UNAVAILABLE']
    source_id: Identifier | None
    holdings_count_reported: Count | None
    notes: Text


class FundHolding(StrictModel):
    id: Identifier
    name: Text
    security_identifier: Text | None
    asset_class: Literal['EQUITY', 'FIXED_INCOME', 'FUND', 'CASH', 'OTHER']
    weight_pct: FinancialDecimal
    source_id: Identifier
    source_locator: Text

    @field_serializer('weight_pct')
    def plain_weight(self, value):
        return format(value, 'f')

    @model_validator(mode='after')
    def valid_weight(self):
        if not Decimal(0) <= self.weight_pct <= Decimal(100):
            raise ValueError('holdings weight must be between zero and 100 percent')
        return self


class FundMetric(StrictModel):
    id: Identifier
    code: MetricCode
    value: FinancialDecimal
    unit: Literal['PCT', 'USD', 'USD_PER_SHARE']
    scope: Literal['CLASS', 'SERIES']
    period_start: Date | None
    period_end: Date | None
    observed_as_of: Date | None
    waiver_end_date: Date | None
    source_id: Identifier
    source_locator: Text
    notes: Text

    @field_serializer('value')
    def plain_value(self, value):
        return format(value, 'f')

    @model_validator(mode='after')
    def metric_semantics(self):
        expected = ('USD_PER_SHARE' if self.code in DISTRIBUTION_CODES else
                    'USD' if self.code in {'NET_ASSETS', 'AVG_DAILY_DOLLAR_VOLUME'} else 'PCT')
        if self.unit != expected:
            raise ValueError('metric code and published unit are incompatible')
        if self.value < 0 and self.code != 'AVG_PREMIUM_DISCOUNT':
            raise ValueError('only premium/discount observations may be negative')
        if self.code in FEE_CODES | DISTRIBUTION_CODES and self.scope != 'CLASS':
            raise ValueError('fees and distributions require share-class disclosures')
        if self.period_start and (not self.period_end or self.period_start > self.period_end):
            raise ValueError('metric reporting period must have ordered start/end dates')
        if not self.period_end and not self.observed_as_of:
            raise ValueError('reported numerical metric requires an actual observation date')
        if self.code in {'PORTFOLIO_TURNOVER'} | ETF_CODES:
            if not self.period_start or not self.period_end:
                raise ValueError('turnover/trading measurement requires its reporting window')
        if self.code in DISTRIBUTION_CODES:
            if not self.period_end or not re.search(r'\b(?:pay|payable|payment|ex[- ]?date|ex[- ]?dividend)\b',
                                                    self.notes, re.I):
                raise ValueError('distribution needs identified payable or ex date')
        if self.waiver_end_date and self.code != 'NET_EXPENSE_RATIO':
            raise ValueError('waiver expiration belongs to reported net expenses')
        if self.code == 'NET_EXPENSE_RATIO' and 'waiver' in self.notes.lower() and not self.waiver_end_date:
            if not re.search(r'unknown|not (?:disclosed|verified|available)|could not|unverified',
                             self.notes, re.I):
                raise ValueError('undisclosed waiver expiry requires an explicit limitation')
        return self


class FundFinding(StrictModel):
    id: Identifier
    category: Literal['FEES', 'METHODOLOGY', 'CONCENTRATION', 'TURNOVER', 'LIQUIDITY', 'TAX', 'RISK', 'OTHER']
    fact: Text
    interpretation: Text | None
    uncertainty: Text
    source_ids: list[Identifier] = Field(min_length=1)
    source_locator: Text


class FundDiligenceInput(StrictModel):
    schema_version: Literal['1.0']
    research_type: Literal['ETF_MUTUAL_FUND_DILIGENCE']
    fund: FundIdentity
    scope: FundScope
    sources: list[FundSource] = Field(min_length=1)
    methodology: FundMethodology
    holdings_snapshot: FundSnapshot
    holdings: list[FundHolding] = Field(max_length=100)
    metrics: list[FundMetric]
    findings: list[FundFinding]
    limitations: list[Text]

    @model_validator(mode='after')
    def evidence(self):
        cutoff = self.scope.researched_as_of
        if cutoff > date.today():
            raise ValueError('research cutoff cannot be in the future')
        if len(set(self.limitations)) != len(self.limitations):
            raise ValueError('limitations must be distinct')
        if self.scope.coverage_status != 'COMPLETE_WITHIN_DECLARED_SCOPE' and not self.limitations:
            raise ValueError('partial/blocked research requires limitations')
        records = self.sources + self.holdings + self.metrics + self.findings
        if len({record.id for record in records}) != len(records):
            raise ValueError('all in-run record IDs must be unique')
        sources = {source.id: source for source in self.sources}
        identity_proven = False
        for source in self.sources:
            for key in ('registrant_cik', 'series_id', 'class_id'):
                supplied = getattr(source, key)
                if supplied is not None and supplied != getattr(self.fund, key):
                    raise ValueError('source contradicts researched fund series/share class')
            for observed in (source.published_at, source.filed_at, source.accessed_at):
                if observed and observed > cutoff:
                    raise ValueError('source is after the researched cutoff')
            if (sec_host(source.url) and source.source_type.startswith('SEC_')
                    and source.registrant_cik == self.fund.registrant_cik
                    and source.series_id == self.fund.series_id
                    and source.class_id == self.fund.class_id):
                path = urlsplit(source.url).path.lower()
                identity_proven |= bool(source.accession_number or 'series' in path or 'browse' in path)
        if not identity_proven:
            raise ValueError('original SEC evidence must prove registrant, series and exact class identity')

        def reference(source_id):
            if source_id not in sources:
                raise ValueError('source reference must belong to this run')
            return sources[source_id]

        for source_id in self.methodology.source_ids:
            reference(source_id)
        if len(set(self.methodology.source_ids)) != len(self.methodology.source_ids):
            raise ValueError('methodology source references must be distinct')
        if self.fund.strategy_type == 'INDEX':
            if not self.methodology.index_name:
                raise ValueError('index strategy requires disclosed index and source evidence')
        elif not self.methodology.active_approach or self.methodology.index_name is not None:
            raise ValueError('active strategy requires active approach and no index-tracking claim')
        snapshot = self.holdings_snapshot
        if snapshot.coverage == 'UNAVAILABLE':
            if self.holdings or snapshot.as_of_date or snapshot.source_id or snapshot.holdings_count_reported:
                raise ValueError('unavailable holdings require empty undated snapshot')
        else:
            if not snapshot.as_of_date or not snapshot.source_id:
                raise ValueError('available holdings require dated source-backed snapshot')
            reference(snapshot.source_id)
            if snapshot.as_of_date > cutoff:
                raise ValueError('holdings observation follows researched cutoff')
            if snapshot.holdings_count_reported is not None and snapshot.holdings_count_reported < len(self.holdings):
                raise ValueError('reported holdings count cannot be less than supplied rows')
            if snapshot.coverage == 'FULL':
                affirmative = re.search(r'\b(?:complete|full|all)\b', snapshot.notes, re.I)
                negative = re.search(r'\b(?:not|incomplete|partial|only|top)\b', snapshot.notes, re.I)
                if (not affirmative or negative or snapshot.holdings_count_reported != len(self.holdings)):
                    raise ValueError('FULL requires affirmative completeness evidence and every reported holding')
        for holding in self.holdings:
            source = reference(holding.source_id)
            if holding.source_id != snapshot.source_id:
                same_date = snapshot.as_of_date.isoformat() if snapshot.as_of_date else ''
                if not same_date or same_date not in source.source_locator:
                    raise ValueError('holdings must cite the declared snapshot or explicit same-date evidence')
        if snapshot.coverage == 'TOP_N':
            weights = [holding.weight_pct for holding in self.holdings]
            if weights != sorted(weights, reverse=True):
                raise ValueError('reported TOP_N weights must remain in descending order')
        with localcontext() as context:
            context.prec = max(50, sum(len(holding.weight_pct.as_tuple().digits)
                                       + abs(holding.weight_pct.as_tuple().exponent)
                                       for holding in self.holdings) + 10)
            if sum((holding.weight_pct for holding in self.holdings), Decimal(0)) > Decimal('100.5'):
                raise ValueError('UNSUPPORTED_FUND_STRUCTURE: observed long-only weights exceed 100.5 percent')
        observations = set()
        for metric in self.metrics:
            source = reference(metric.source_id)
            if metric.code in FEE_CODES | DISTRIBUTION_CODES and source.class_id != self.fund.class_id:
                raise ValueError('class fee/distribution source must identify the exact share class')
            if self.fund.fund_type == 'MUTUAL_FUND' and metric.code in ETF_CODES:
                raise ValueError('mutual fund cannot contain ETF exchange liquidity metrics')
            for observed in (metric.period_start, metric.period_end, metric.observed_as_of):
                if observed and observed > cutoff:
                    raise ValueError('metric observation follows researched cutoff')
            key = (metric.code, metric.scope, metric.period_start, metric.period_end, metric.observed_as_of)
            if key in observations:
                raise ValueError('duplicate metric observation')
            observations.add(key)
        for finding in self.findings:
            if len(set(finding.source_ids)) != len(finding.source_ids):
                raise ValueError('finding source references must be distinct')
            for source_id in finding.source_ids:
                reference(source_id)
            if self.fund.fund_type == 'ETF' and finding.category == 'LIQUIDITY':
                if re.search(r'\b(?:shareholder|investor)\b.*\b(?:deal|dealing|redeem)\w*.*\bNAV\b',
                             finding.fact, re.I):
                    raise ValueError('ETF shareholder dealing cannot be represented as mutual-fund NAV dealing')
        return self
