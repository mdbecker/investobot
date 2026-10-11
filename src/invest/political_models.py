"""Strict political-research interchange and independently reviewed source permissions."""

import os
import re
from datetime import date
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

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


def amount(value):
    if not isinstance(value, str) or not re.fullmatch(r'-?\d+(?:\.\d+)?', value):
        raise ValueError('amount_usd must be a finite plain decimal string')
    result = Decimal(value)
    if not result.is_finite():
        raise ValueError('nonfinite amount')
    return result


Money = Annotated[Decimal, BeforeValidator(amount, json_schema_input_type=str),
                  PlainSerializer(str, return_type=str)]
Text = Annotated[str, Field(min_length=1, max_length=4000)]


def safe_url(value):
    parts = urlsplit(value)
    if parts.scheme not in {'https', 'http'} or not parts.hostname:
        raise ValueError('source URLs require HTTP(S) origin')
    if any(ord(c) < 32 for c in value):
        raise ValueError('unsafe source URL')
    host = parts.hostname.lower()
    if ':' in host:
        host = f'[{host}]'
    if parts.port:
        host += f':{parts.port}'
    locators = {'record_id', 'filing_id', 'transaction_id', 'committee_id',
                'candidate_id', 'accession_number'}
    retained = {}
    for key, locator in parse_qsl(parts.query, keep_blank_values=True):
        if key not in locators:
            continue
        if key in retained or not re.fullmatch(r'[A-Za-z0-9._:-]{1,200}', locator):
            raise ValueError('unsafe or ambiguous public record locator')
        retained[key] = locator
    return urlunsplit((parts.scheme, host, parts.path,
                       urlencode(sorted(retained.items())), ''))


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class Company(StrictModel):
    name: Text
    ticker: Text | None = None
    security_id: Text | None = None


class Scope(StrictModel):
    jurisdiction: Literal['US_FEDERAL']
    period_start: date
    period_end: date
    researched_as_of: date
    coverage_status: Literal['COMPLETE_WITHIN_DECLARED_SCOPE', 'PARTIAL', 'BLOCKED']
    rights_status: Literal['APPROVED', 'PENDING_REVIEW', 'BLOCKED']

    @model_validator(mode='after')
    def dates(self):
        if self.period_start > self.period_end or self.period_end > self.researched_as_of:
            raise ValueError('invalid research date range')
        if self.researched_as_of > date.today():
            raise ValueError('researched_as_of is in the future')
        return self


class Source(StrictModel):
    id: Text
    url: Text
    publisher: Text
    source_type: Text
    published_at: date | None = None
    accessed_at: date
    individual_contributor_data: StrictBool
    rights_basis: Text
    source_locator: Text | None = None

    @field_validator('url')
    @classmethod
    def url_safe(cls, value):
        return safe_url(value)


class Executive(StrictModel):
    id: Text
    full_name: Text
    role: Text
    role_start: date | None = None
    role_end: date | None = None
    role_source_id: Text
    identity_status: Literal['VERIFIED']


class Recipient(StrictModel):
    id: Text
    name: Text
    recipient_type: Literal[
        'CANDIDATE_COMMITTEE', 'PARTY_COMMITTEE', 'PAC', 'JOINT_FUNDRAISER', 'OTHER_COMMITTEE']
    committee_id: Text | None = None
    candidate_id: Text | None = None
    candidate_name: Text | None = None
    recipient_party: Literal['DEMOCRATIC', 'REPUBLICAN', 'OTHER', 'NONPARTISAN', 'UNKNOWN']
    party_basis: Text
    election_cycle: Annotated[int, Field(strict=True, ge=1900, le=2200)] | None = None
    party_source_id: Text


class CorporatePacIdentityEvidence(StrictModel):
    committee_id: Annotated[str, Field(pattern=r'^C\d{8}$')]
    company_source_id: Text
    registration_source_id: Text
    source_locator: Text
    reviewed: StrictBool


class Contribution(StrictModel):
    id: Text
    executive_id: Text
    recipient_id: Text
    date: date
    amount_usd: Money
    transaction_kind: Literal[
        'CONTRIBUTION', 'REFUND', 'REATTRIBUTION', 'REDESIGNATION', 'MEMO', 'OTHER']
    channel: Literal['DIRECT', 'EARMARKED', 'COMMITTEE', 'UNKNOWN']
    source_system: Text
    source_record_id: Text
    underlying_transaction_key: Text | None = None
    identity_status: Literal['VERIFIED']
    countable: StrictBool
    source_ids: list[Text] = Field(min_length=1)
    notes: str = Field(default='', max_length=4000)
    original_contribution_id: Text | None = None
    contributor_category: Literal['EXECUTIVE_PERSONAL', 'EMPLOYEE_PERSONAL', 'CORPORATE_PAC'] | None = None
    corporate_pac_identity_evidence: CorporatePacIdentityEvidence | None = None


class UnresolvedMatch(StrictModel):
    executive_id: Text
    reason: Text
    potential_record_count: Annotated[int, Field(strict=True, ge=0)]
    notes: str = Field(default='', max_length=4000)


class PoliticalResearchInput(StrictModel):
    schema_version: Literal['1.0']
    research_type: Literal['EXECUTIVE_POLITICAL_CONTRIBUTIONS',
                           'EMPLOYEE_POLITICAL_CONTRIBUTIONS',
                           'CORPORATE_PAC_POLITICAL_CONTRIBUTIONS']
    company: Company
    scope: Scope
    sources: list[Source]
    executives: list[Executive]
    recipients: list[Recipient]
    contributions: list[Contribution]
    unresolved_matches: list[UnresolvedMatch]
    limitations: list[Text]

    @model_validator(mode='after')
    def consistency(self):
        collections = [self.sources, self.executives, self.recipients, self.contributions]
        for records in collections:
            if len({r.id for r in records}) != len(records):
                raise ValueError('duplicate research identifiers')
        sources = {s.id: s for s in self.sources}
        executives = {e.id: e for e in self.executives}
        recipients = {r.id: r for r in self.recipients}
        contributions = {c.id: c for c in self.contributions}
        if len({s.url for s in self.sources}) != len(self.sources):
            raise ValueError('duplicate sanitized source URLs')
        if len({e.full_name.casefold() for e in self.executives}) != len(self.executives):
            raise ValueError('same-name executive collision requires resolution')
        for source in self.sources:
            if source.accessed_at > self.scope.researched_as_of:
                raise ValueError('source access date exceeds research date')
            if source.published_at and source.published_at > source.accessed_at:
                raise ValueError('source publication exceeds access date')
        for executive in self.executives:
            if executive.role_source_id not in sources:
                raise ValueError('missing executive role evidence')
            if executive.role_start and executive.role_end:
                if executive.role_start > executive.role_end:
                    raise ValueError('invalid executive role dates')
            if (executive.role_start and executive.role_start > self.scope.period_end) or (
                executive.role_end and executive.role_end < self.scope.period_start
            ):
                raise ValueError('executive role does not overlap research scope')
        for recipient in self.recipients:
            if recipient.party_source_id not in sources:
                raise ValueError('missing recipient affiliation evidence')
            if recipient.recipient_party != 'UNKNOWN' and recipient.party_basis.upper() == 'UNKNOWN':
                raise ValueError('recipient party requires documented basis')
            if recipient.recipient_type == 'CANDIDATE_COMMITTEE':
                if not all([recipient.committee_id, recipient.candidate_id,
                            recipient.candidate_name, recipient.election_cycle]):
                    raise ValueError('candidate committee requires verified relationship metadata')
            elif recipient.candidate_id or recipient.candidate_name:
                raise ValueError('noncandidate recipients cannot be attributed to a candidate')
        records, counted = set(), set()
        refund_totals = {}
        for contribution in self.contributions:
            expected_category = {
                'EXECUTIVE_POLITICAL_CONTRIBUTIONS': 'EXECUTIVE_PERSONAL',
                'EMPLOYEE_POLITICAL_CONTRIBUTIONS': 'EMPLOYEE_PERSONAL',
                'CORPORATE_PAC_POLITICAL_CONTRIBUTIONS': 'CORPORATE_PAC',
            }[self.research_type]
            category = contribution.contributor_category
            if category != expected_category and not (
                    category is None and expected_category == 'EXECUTIVE_PERSONAL'):
                raise ValueError('contributor category contradicts political research type')
            pac = contribution.corporate_pac_identity_evidence
            if expected_category != 'CORPORATE_PAC' and pac is not None:
                raise ValueError('personal contribution cannot carry corporate PAC linkage')
            if contribution.executive_id not in executives or contribution.recipient_id not in recipients:
                raise ValueError('invalid contribution cross-reference')
            if any(s not in sources for s in contribution.source_ids):
                raise ValueError('invalid contribution source reference')
            if len(set(contribution.source_ids)) != len(contribution.source_ids):
                raise ValueError('duplicate evidence reference')
            role_source = executives[contribution.executive_id].role_source_id
            if expected_category == 'CORPORATE_PAC':
                if not pac or not pac.reviewed:
                    raise ValueError('corporate PAC identity requires independently reviewed linkage')
                if (pac.company_source_id != role_source or
                        pac.registration_source_id == pac.company_source_id or
                        {pac.company_source_id, pac.registration_source_id} - set(contribution.source_ids)):
                    raise ValueError('corporate PAC linkage requires distinct cited company and registration evidence')
                if sources[pac.company_source_id].source_type != 'CORPORATE_PAC_REGISTRATION':
                    raise ValueError('corporate PAC company evidence requires original registration')
            identity_types = {
                'INDEPENDENT_DISCLOSURE', 'CONTRIBUTION_RECORD', 'IDENTITY_CORROBORATION',
                'EXECUTIVE_STATEMENT', 'PERMITTED_DISCLOSURE',
            }
            if not any(s != role_source and sources[s].source_type in identity_types
                       for s in contribution.source_ids):
                raise ValueError('role evidence alone cannot verify contributor identity')
            if not self.scope.period_start <= contribution.date <= self.scope.period_end:
                raise ValueError('contribution outside research period')
            executive = executives[contribution.executive_id]
            if (executive.role_start and contribution.date < executive.role_start) or (
                executive.role_end and contribution.date > executive.role_end
            ):
                raise ValueError('transaction date outside verified executive role')
            key = (contribution.source_system, contribution.source_record_id)
            if key in records:
                raise ValueError('duplicate source transaction')
            records.add(key)
            if contribution.countable:
                if not contribution.underlying_transaction_key:
                    raise ValueError('countable transaction needs underlying identity')
                if contribution.underlying_transaction_key in counted:
                    raise ValueError('underlying transaction counted twice')
                counted.add(contribution.underlying_transaction_key)
                if contribution.transaction_kind == 'CONTRIBUTION':
                    if contribution.amount_usd <= 0 or contribution.original_contribution_id:
                        raise ValueError('countable contribution must be positive and original')
                elif contribution.transaction_kind == 'REFUND':
                    original = contributions.get(contribution.original_contribution_id)
                    if not original or not original.countable or original.transaction_kind != 'CONTRIBUTION':
                        raise ValueError('countable refund requires original counted contribution')
                    if (contribution.amount_usd >= 0 or contribution.date < original.date or
                        contribution.executive_id != original.executive_id or
                        contribution.recipient_id != original.recipient_id):
                        raise ValueError('refund must match original executive and recipient')
                    # Precision includes all coefficient digits and fractional places, plus
                    # carry digits for the maximum possible number of refund additions.
                    decimals = [c.amount_usd for c in self.contributions]
                    precision = max(len(v.as_tuple().digits) + abs(v.as_tuple().exponent)
                                    for v in decimals) + len(str(len(decimals))) + 2
                    with localcontext() as context:
                        context.prec = max(28, precision)
                        refund_totals[original.id] = (
                            refund_totals.get(original.id, Decimal(0)) - contribution.amount_usd
                        )
                    if refund_totals[original.id] > original.amount_usd:
                        raise ValueError('refund exceeds original contribution')
                else:
                    raise ValueError('adjustments and memo records must not affect totals')
        for match in self.unresolved_matches:
            if match.executive_id not in executives:
                raise ValueError('invalid unresolved executive reference')
        return self


class PolicySource(StrictModel):
    origin: Text
    allow_individual_contributor_data: StrictBool
    fec_derived: StrictBool
    allow_fec_derived: StrictBool


class ReviewedPolicy(StrictModel):
    intended_use: Literal['INVESTMENT_RESEARCH']
    review_reference: Text
    sources: list[PolicySource]


def enforce_policy(model, policy_path=None):
    """Deny personal contribution uses unless an independent local policy permits them."""
    personal = {s.id for s in model.sources if s.individual_contributor_data}
    personal.update(s for c in model.contributions for s in c.source_ids
                    if s != next(e.role_source_id for e in model.executives if e.id == c.executive_id))
    if not personal and not model.contributions:
        return
    if model.scope.rights_status != 'APPROVED':
        raise ValueError('personal contribution source rights are not approved')
    path = policy_path or os.environ.get('INVEST_RESEARCH_POLICY')
    if not path:
        raise ValueError('personal contributor records require independently reviewed source policy')
    policy = ReviewedPolicy.model_validate_json(Path(path).read_text())
    origins = {}
    for rule in policy.sources:
        parsed = urlsplit(rule.origin)
        if safe_url(rule.origin).rstrip('/') != urlunsplit((parsed.scheme, parsed.netloc, '', '', '')):
            raise ValueError('reviewed source policy requires exact origins')
        if rule.origin.rstrip('/') in origins:
            raise ValueError('duplicate reviewed source origin')
        origins[rule.origin.rstrip('/')] = rule
    fec_sources = {sid for c in model.contributions if 'FEC' in c.source_system.upper()
                   for sid in c.source_ids}
    for source in model.sources:
        if source.id not in personal:
            continue
        parts = urlsplit(source.url)
        rule = origins.get(urlunsplit((parts.scheme, parts.netloc, '', '', '')))
        if not rule or not rule.allow_individual_contributor_data:
            raise ValueError('personal contributor source is not permitted by reviewed policy')
        fec = parts.hostname == 'fec.gov' or parts.hostname.endswith('.fec.gov')
        if (fec or source.id in fec_sources or rule.fec_derived) and not rule.allow_fec_derived:
            raise ValueError('FEC-derived contributor use requires explicit independent review')


def load_research(path, policy_path=None):
    model = PoliticalResearchInput.model_validate_json(Path(path).read_text())
    enforce_policy(model, policy_path=policy_path)
    return model
