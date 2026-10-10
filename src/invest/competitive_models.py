"""Strict reported peer evidence; structural checks do not establish source truth."""

import re
from datetime import date
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator

from invest.earnings_models import (
    CIK,
    CURRENCIES,
    Basis,
    Date,
    EarningsCompany,
    FinancialDecimal,
    StrictModel,
    Text,
)
from invest.political_models import safe_url

Identifier = Annotated[str, Field(min_length=1, max_length=200, pattern=r'^[A-Za-z0-9][A-Za-z0-9_.:-]*$')]
Relationship = Literal['DIRECT_COMPETITOR', 'ADJACENT_COMPETITOR', 'POTENTIAL_BUSINESS_SUBSTITUTE']
MetricCode = Literal['REVENUE', 'GROSS_PROFIT', 'OPERATING_INCOME', 'NET_INCOME',
                     'OPERATING_CASH_FLOW', 'CAPITAL_EXPENDITURES', 'FREE_CASH_FLOW',
                     'CUSTOMER_COUNT', 'OTHER']


def normalized_text(value):
    return ' '.join(value.split())


def sec_cik(url):
    parts = urlsplit(url)
    if parts.hostname == 'sec.gov' or parts.hostname.endswith('.sec.gov'):
        match = re.search(r'/Archives/edgar/data/(\d+)/', parts.path, re.IGNORECASE)
        if not match:
            match = re.search(r'/(?:api/xbrl/companyfacts|submissions)/CIK(\d+)\.json$',
                              parts.path, re.IGNORECASE)
        if match:
            return match[1].zfill(10)
    return None


class CompetitiveEntity(EarningsCompany):
    entity_id: Identifier


class CompetitiveSubject(CompetitiveEntity):
    entity_id: Literal['subject']


class CompetitivePeer(CompetitiveEntity):
    relationship: Relationship
    rationale: Text
    selection_source_id: Identifier

    @model_validator(mode='after')
    def peer(self):
        if self.entity_id == 'subject':
            raise ValueError('subject cannot also be a peer')
        return self


class CompetitiveScope(StrictModel):
    market_focus: Text
    geography: Text
    researched_as_of: Date
    coverage_status: Literal['COMPLETE_WITHIN_DECLARED_SCOPE', 'PARTIAL', 'BLOCKED']
    coverage_notes: Text

    @model_validator(mode='after')
    def dates(self):
        if self.researched_as_of > date.today():
            raise ValueError('research date is in the future')
        return self


class CompetitiveSource(StrictModel):
    id: Identifier
    source_type: Text
    publisher: Text
    url: Text
    published_at: Date | None = None
    accessed_at: Date
    source_locator: Text
    accession_number: Text | None = None
    cik: CIK = None

    @field_validator('url')
    @classmethod
    def normalize_url(cls, value):
        return safe_url(value)

    @model_validator(mode='after')
    def provenance(self):
        if self.published_at and self.published_at > self.accessed_at:
            raise ValueError('source publication follows retrieval')
        url_cik = sec_cik(self.url)
        if url_cik and self.cik and url_cik != self.cik:
            raise ValueError('SEC URL contradicts source CIK')
        if self.accession_number and not re.fullmatch(r'\d{10}-\d{2}-\d{6}', self.accession_number):
            raise ValueError('invalid accession number')
        if self.source_type.startswith('SEC_') and not self.accession_number:
            raise ValueError('SEC disclosures require accession number')
        return self


class CompetitiveOverlap(StrictModel):
    id: Identifier
    peer_id: Identifier
    market: Text
    geography: Text
    subject_segment: Text
    peer_segment: Text
    overlap_type: Literal['DIRECT', 'PARTIAL', 'POTENTIAL']
    description: Text
    subject_source_id: Identifier
    peer_source_id: Identifier
    uncertainty: Text


class CompetitiveFinding(StrictModel):
    id: Identifier
    peer_id: Identifier
    overlap_id: Identifier | None = None
    kind: Literal['SUBJECT_ADVANTAGE', 'SUBJECT_DISADVANTAGE', 'TRADEOFF', 'UNRESOLVED']
    factual_basis: Text
    interpretation: Text
    assumptions: Text
    uncertainty: Text
    source_id: Identifier
    source_locator: Text
    corroborating_source_ids: list[Identifier]


class CompetitiveMetric(StrictModel):
    id: Identifier
    entity_id: Identifier
    metric_code: MetricCode
    metric_definition: Text
    value: FinancialDecimal
    unit: Text
    accounting_basis: Basis
    period_type: Literal['DURATION', 'INSTANT']
    period_start: Date | None = None
    period_end: Date
    scope: Literal['CONSOLIDATED', 'SEGMENT']
    segment_name: Text | None = None
    overlap_id: Identifier | None = None
    source_id: Identifier
    source_locator: Text

    @model_validator(mode='after')
    def reported(self):
        self.metric_definition = normalized_text(self.metric_definition)
        if self.unit not in CURRENCIES | {'shares', 'count'}:
            raise ValueError('unsupported financial unit')
        if self.metric_code == 'CUSTOMER_COUNT':
            if self.unit != 'count':
                raise ValueError('customer count requires count unit')
        elif self.metric_code != 'OTHER' and self.unit not in CURRENCIES:
            raise ValueError('monetary metrics require currency unit')
        if self.period_type == 'DURATION':
            if self.period_start is None or self.period_start > self.period_end:
                raise ValueError('duration needs valid start/end dates')
        elif self.period_start is not None:
            raise ValueError('instant must have null start')
        if self.scope == 'CONSOLIDATED':
            if self.segment_name is not None or self.overlap_id is not None:
                raise ValueError('consolidated metrics cannot name segment or overlap')
        elif not self.segment_name:
            raise ValueError('segment metrics require segment name')
        return self


def _unique(items, field):
    values = [getattr(item, field) for item in items]
    if len(set(values)) != len(values):
        raise ValueError('duplicate record identifiers')


def _issuer(source, entity, financial=False):
    identifiers = {v for v in (source.cik, sec_cik(source.url)) if v}
    if entity.cik and any(v != entity.cik for v in identifiers):
        raise ValueError('source issuer CIK contradicts entity')
    if financial:
        primary = source.source_type.startswith(('ISSUER_', 'SEC_'))
        matching = (entity.cik and entity.cik in identifiers) or (
            normalized_text(source.publisher).casefold() == normalized_text(entity.name).casefold())
        if not primary or not matching:
            raise ValueError('financial source issuer cannot be verified; omit metric and disclose gap')


class CompetitiveResearchInput(StrictModel):
    schema_version: Literal['1.0']
    research_type: Literal['COMPETITIVE_POSITION_PEER_COMPARISON']
    subject: CompetitiveSubject
    scope: CompetitiveScope
    sources: list[CompetitiveSource] = Field(min_length=1)
    peers: list[CompetitivePeer] = Field(min_length=1, max_length=8)
    overlaps: list[CompetitiveOverlap]
    findings: list[CompetitiveFinding]
    metrics: list[CompetitiveMetric]
    limitations: list[Text]

    @model_validator(mode='after')
    def consistency(self):
        entities = [self.subject, *self.peers]
        _unique(entities, 'entity_id')
        for collection in (self.sources, self.overlaps, self.findings, self.metrics):
            _unique(collection, 'id')
        if len(set(self.limitations)) != len(self.limitations):
            raise ValueError('duplicate limitations')
        if not self.limitations and self.scope.coverage_status != 'COMPLETE_WITHIN_DECLARED_SCOPE':
            raise ValueError('incomplete coverage requires explicit limitations')
        for i, first in enumerate(entities):
            for second in entities[i + 1:]:
                for field in ('cik', 'security_id', 'ticker'):
                    a, b = getattr(first, field), getattr(second, field)
                    if a and b and a.casefold() == b.casefold():
                        raise ValueError('duplicate company identity')
                if normalized_text(first.name).casefold() == normalized_text(second.name).casefold():
                    raise ValueError('legal entities must be explicitly differentiated')
        sources = {s.id: s for s in self.sources}
        peers = {p.entity_id: p for p in self.peers}
        entity_map = {e.entity_id: e for e in entities}
        overlaps = {o.id: o for o in self.overlaps}
        for source in self.sources:
            if source.accessed_at > self.scope.researched_as_of:
                raise ValueError('source retrieved after research date')
            if source.published_at and source.published_at > self.scope.researched_as_of:
                raise ValueError('source publication after research date')
        def source_ref(key):
            if key not in sources:
                raise ValueError('invalid run-scoped source reference')
            return sources[key]
        for peer in self.peers:
            _issuer(source_ref(peer.selection_source_id), peer)
            if not any(o.peer_id == peer.entity_id for o in self.overlaps):
                raise ValueError('each peer needs evidenced market overlap')
        for overlap in self.overlaps:
            if overlap.peer_id not in peers:
                raise ValueError('overlap must reference a peer')
            _issuer(source_ref(overlap.subject_source_id), self.subject)
            _issuer(source_ref(overlap.peer_source_id), peers[overlap.peer_id])
        for finding in self.findings:
            if finding.peer_id not in peers:
                raise ValueError('finding must reference peer')
            if finding.overlap_id and (finding.overlap_id not in overlaps or
                                      overlaps[finding.overlap_id].peer_id != finding.peer_id):
                raise ValueError('finding overlap belongs to a different peer')
            source_ref(finding.source_id)
            if len(set(finding.corroborating_source_ids)) != len(finding.corroborating_source_ids):
                raise ValueError('duplicate corroborating sources')
            for key in finding.corroborating_source_ids:
                source_ref(key)
        facts = set()
        for metric in self.metrics:
            if metric.entity_id not in entity_map:
                raise ValueError('metric entity is unknown')
            entity = entity_map[metric.entity_id]
            source = source_ref(metric.source_id)
            _issuer(source, entity, financial=True)
            if metric.period_end > self.scope.researched_as_of:
                raise ValueError('metric ends after research date')
            if source.published_at and metric.period_end > source.published_at:
                raise ValueError('metric ends after source publication')
            if metric.overlap_id:
                overlap = overlaps.get(metric.overlap_id)
                if not overlap or metric.entity_id not in {'subject', overlap.peer_id}:
                    raise ValueError('segment overlap is invalid for entity')
                expected = overlap.subject_segment if metric.entity_id == 'subject' else overlap.peer_segment
                if normalized_text(metric.segment_name) != normalized_text(expected):
                    raise ValueError('metric segment contradicts overlap association')
            key = (metric.entity_id, metric.metric_code, metric.metric_definition,
                   metric.accounting_basis, metric.unit, metric.period_type,
                   metric.period_start, metric.period_end, metric.scope, metric.segment_name,
                   metric.overlap_id)
            if key in facts:
                raise ValueError('duplicate or conflicting financial observation')
            facts.add(key)
        return self
