"""Authoritative news evidence contract; validation cannot establish source truth."""

import re
from datetime import date
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import field_validator, model_validator

from .earnings_models import Date, EarningsCompany, StrictModel, Text
from .political_models import safe_url

DateStatus = Literal['CONFIRMED', 'ESTIMATED', 'EXPECTED', 'UNKNOWN']


def unique(items, key, description):
    values = [getattr(item, key) for item in items]
    if len(values) != len(set(values)):
        raise ValueError(f'duplicate {description} identifiers')


def dated(value, status):
    if (value is None) != (status == 'UNKNOWN'):
        raise ValueError('unknown dates require UNKNOWN certainty exclusively')


class NewsScope(StrictModel):
    window_start: Date
    window_end: Date
    researched_as_of: Date
    coverage_status: Literal['COMPLETE_WITHIN_DECLARED_SCOPE', 'PARTIAL', 'BLOCKED']
    searched_source_types: list[Text]
    coverage_notes: Text

    @model_validator(mode='after')
    def dates(self):
        if not self.window_start <= self.window_end <= self.researched_as_of <= date.today():
            raise ValueError('research window dates are inconsistent or future')
        if len(self.searched_source_types) != len(set(self.searched_source_types)):
            raise ValueError('duplicate searched source types')
        return self


class NewsSource(StrictModel):
    id: Text
    source_type: Text
    publisher: Text
    url: Text
    published_at: Date | None
    accessed_at: Date
    source_locator: Text

    @field_validator('url')
    @classmethod
    def normalize_url(cls, value):
        return safe_url(value)

    @model_validator(mode='after')
    def dates(self):
        if self.published_at and self.published_at > self.accessed_at:
            raise ValueError('source publication follows retrieval')
        return self


class NewsFact(StrictModel):
    fact_key: Text
    statement: Text
    source_id: Text
    source_locator: Text
    verification_status: Literal['VERIFIED', 'DISPUTED']


class NewsImplication(StrictModel):
    id: Text
    area: Literal['DEMAND', 'REVENUE', 'MARGINS', 'COSTS', 'COMPETITION', 'OPERATIONS',
                  'LIQUIDITY', 'REGULATORY', 'OTHER']
    statement: Text
    assumptions: Text
    uncertainty: Text


class NewsQuestion(StrictModel):
    id: Text
    question: Text
    status: Literal['OPEN', 'ANSWERED', 'CLOSED_WITHOUT_ANSWER']
    answered_fact_key: Text | None = None
    closure_limitation: Text | None = None
    evidence_needed: Text | None = None

    @model_validator(mode='after')
    def closure(self):
        if self.status == 'OPEN' and (self.answered_fact_key or self.closure_limitation):
            raise ValueError('open questions cannot claim closure evidence')
        if self.status == 'ANSWERED' and not (self.answered_fact_key or self.closure_limitation):
            raise ValueError('answered questions require verified fact or closure limitation')
        if self.status == 'CLOSED_WITHOUT_ANSWER':
            if not self.closure_limitation or self.answered_fact_key:
                raise ValueError('closure without answer requires a limitation, not an answer')
        return self


class NewsEvent(StrictModel):
    event_key: Text
    title: Text
    category: Literal['EARNINGS', 'PRODUCT', 'CUSTOMER', 'PARTNERSHIP', 'MERGER_ACQUISITION',
                      'LEADERSHIP', 'REGULATORY', 'LITIGATION', 'CYBERSECURITY', 'CAPITAL_ALLOCATION',
                      'OPERATIONS', 'SUPPLY_CHAIN', 'MACRO_EXPOSURE', 'OTHER']
    event_date: Date | None
    date_status: DateStatus
    event_status: Literal['ANNOUNCED', 'DEVELOPING', 'CONFIRMED', 'RESOLVED', 'RETRACTED', 'UNKNOWN']
    affected_segments: list[Text]
    primary_source_id: Text
    source_ids: list[Text]
    facts: list[NewsFact]
    implications: list[NewsImplication]
    follow_up_questions: list[NewsQuestion]
    status_source_id: Text | None = None
    status_source_locator: Text | None = None

    @model_validator(mode='after')
    def evidence(self):
        dated(self.event_date, self.date_status)
        if len(self.source_ids) != len(set(self.source_ids)):
            raise ValueError('duplicate event source identifiers')
        if self.primary_source_id not in self.source_ids:
            raise ValueError('primary source must belong to event sources')
        if len(self.affected_segments) != len(set(self.affected_segments)):
            raise ValueError('duplicate affected segments')
        unique(self.facts, 'fact_key', 'fact')
        unique(self.implications, 'id', 'implication')
        unique(self.follow_up_questions, 'id', 'question')
        if bool(self.status_source_id) != bool(self.status_source_locator):
            raise ValueError('status evidence requires source and locator together')
        if self.event_status in {'RESOLVED', 'RETRACTED'} and not self.status_source_id:
            raise ValueError('resolved or retracted events require explicit status evidence')
        if self.status_source_id and self.status_source_id not in self.source_ids:
            raise ValueError('status evidence must belong to event sources')
        facts = {fact.fact_key: fact for fact in self.facts}
        for fact in self.facts:
            if fact.source_id not in self.source_ids:
                raise ValueError('fact evidence must belong to event sources')
        for question in self.follow_up_questions:
            if question.answered_fact_key:
                fact = facts.get(question.answered_fact_key)
                if fact is None or fact.verification_status != 'VERIFIED':
                    raise ValueError('question answer requires a verified same-event fact')
        return self


class NewsCatalyst(StrictModel):
    catalyst_id: Text
    title: Text
    related_event_key: Text | None = None
    scheduled_date: Date | None
    date_status: DateStatus
    status: Literal['EXPECTED', 'SCHEDULED', 'DELAYED', 'OCCURRED', 'CANCELLED', 'UNKNOWN']
    source_id: Text
    source_locator: Text
    qualifiers: Text

    @model_validator(mode='after')
    def dates(self):
        dated(self.scheduled_date, self.date_status)
        if self.status == 'SCHEDULED' and self.scheduled_date is None:
            raise ValueError('scheduled catalysts require a known date')
        return self


class NewsThesis(StrictModel):
    thesis_id: Text
    statement: Text
    assessment: Literal['SUPPORTED', 'CHALLENGED', 'MIXED', 'INSUFFICIENT_EVIDENCE']
    rationale: Text
    related_event_keys: list[Text]
    uncertainty: Text


class NewsResearchInput(StrictModel):
    schema_version: Literal['1.0']
    research_type: Literal['NEWS_CATALYSTS_THESIS_CHANGES']
    company: EarningsCompany
    scope: NewsScope
    sources: list[NewsSource]
    theses: list[NewsThesis]
    events: list[NewsEvent]
    catalysts: list[NewsCatalyst]
    limitations: list[Text]

    @model_validator(mode='after')
    def consistency(self):
        unique(self.sources, 'id', 'source')
        unique(self.events, 'event_key', 'event')
        unique(self.catalysts, 'catalyst_id', 'catalyst')
        unique(self.theses, 'thesis_id', 'thesis')
        sources = {source.id: source for source in self.sources}
        events = {event.event_key for event in self.events}
        for source in self.sources:
            if source.accessed_at > self.scope.researched_as_of:
                raise ValueError('source retrieval follows research date')
            parts = urlsplit(source.url)
            if parts.hostname == 'sec.gov' or parts.hostname.endswith('.sec.gov'):
                match = re.search(r'/Archives/edgar/data/(\d+)/', parts.path, re.IGNORECASE)
                if not match:
                    match = re.search(r'/(?:api/xbrl/companyfacts|submissions)/CIK(\d+)\.json$',
                                      parts.path, re.IGNORECASE)
                if match and self.company.cik and match[1].zfill(10) != self.company.cik:
                    raise ValueError('SEC source CIK contradicts company identity')
        for event in self.events:
            if any(source_id not in sources for source_id in event.source_ids):
                raise ValueError('invalid event source reference')
            if event.event_date and event.event_date > self.scope.researched_as_of:
                raise ValueError('event occurrence follows research date; use a catalyst')
        for catalyst in self.catalysts:
            if catalyst.source_id not in sources:
                raise ValueError('invalid catalyst source reference')
            if catalyst.related_event_key and catalyst.related_event_key not in events:
                raise ValueError('invalid catalyst event reference')
            if catalyst.status == 'OCCURRED':
                if catalyst.scheduled_date and catalyst.scheduled_date > self.scope.researched_as_of:
                    raise ValueError('occurred catalyst date cannot be future')
                if catalyst.date_status in {'ESTIMATED', 'EXPECTED'}:
                    raise ValueError('occurred catalyst cannot assert an expected occurrence date')
        for thesis in self.theses:
            if len(thesis.related_event_keys) != len(set(thesis.related_event_keys)):
                raise ValueError('duplicate thesis event identifiers')
            if any(key not in events for key in thesis.related_event_keys):
                raise ValueError('invalid thesis event reference')
        return self


def load_news(path):
    return NewsResearchInput.model_validate_json(Path(path).read_text())
