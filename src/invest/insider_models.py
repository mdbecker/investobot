"""Strict as-filed management evidence; validation cannot establish source truth."""

import re
from datetime import date, datetime
from typing import Annotated, Literal
from urllib.parse import parse_qs, urlsplit

from pydantic import (
    BeforeValidator,
    ConfigDict,
    Field,
    StrictBool,
    field_serializer,
    field_validator,
    model_validator,
)

from invest.competitive_models import Identifier
from invest.earnings_models import (
    CIK,
    CURRENCIES,
    EarningsCompany,
    FinancialDecimal,
    StrictModel,
    Text,
    Year,
    iso_date,
)
from invest.political_models import safe_url


def parsed_date(value):
    value = iso_date(value)
    return date.fromisoformat(value) if isinstance(value, str) else value


Date = Annotated[date, BeforeValidator(parsed_date)]
TableType = Literal['NON_DERIVATIVE', 'DERIVATIVE']
OwnershipForm = Literal['DIRECT', 'INDIRECT']
SourceType = Literal['3', '3/A', '4', '4/A', '5', '5/A', 'DEF 14A', '8-K', '10-K',
                     'ISSUER_DISCLOSURE', 'ISSUER_RELEASE', 'ISSUER_REPORT',
                     'ISSUER_AGREEMENT', 'ISSUER_LEADERSHIP']
SECTION16 = {'3', '3/A', '4', '4/A', '5', '5/A'}
SEC_FORMS = SECTION16 | {'DEF 14A', '8-K', '10-K'}
ACCESSION = r'\d{10}-\d{2}-\d{6}'


class InsiderModel(StrictModel):
    model_config = ConfigDict(extra='forbid', strict=True, str_strip_whitespace=True)


class InsiderCompany(EarningsCompany):
    model_config = InsiderModel.model_config


class InsiderScope(InsiderModel):
    period_start: Date
    period_end: Date
    researched_as_of: Date
    coverage_status: Literal['COMPLETE_WITHIN_DECLARED_SCOPE', 'PARTIAL', 'BLOCKED']
    coverage_notes: Text

    @model_validator(mode='after')
    def dates(self):
        if not self.period_start <= self.period_end <= self.researched_as_of <= date.today():
            raise ValueError('invalid research date range or future cutoff')
        return self


class InsiderSource(InsiderModel):
    id: Identifier
    source_type: SourceType
    publisher: Text
    url: Text
    cik: CIK = None
    reporting_owner_ciks: list[CIK]
    accession_number: Text | None = None
    filed_at: Date | None = None
    accepted_at: datetime | None = None
    accessed_at: Date
    source_locator: Text
    is_amendment: StrictBool
    original_accession_number: Text | None = None

    @field_validator('url')
    @classmethod
    def normalized_url(cls, value):
        return safe_url(value)

    @field_validator('accepted_at', mode='before')
    @classmethod
    def timestamp(cls, value):
        if value is None or isinstance(value, datetime):
            return value
        if not isinstance(value, str) or 'T' not in value:
            raise ValueError('acceptance requires an ISO timestamp')
        return datetime.fromisoformat(value.replace('Z', '+00:00'))

    @model_validator(mode='after')
    def provenance(self):
        if None in self.reporting_owner_ciks or len(set(self.reporting_owner_ciks)) != len(self.reporting_owner_ciks):
            raise ValueError('reporting owner CIKs must be known and unique')
        for accession in (self.accession_number, self.original_accession_number):
            if accession and not re.fullmatch(ACCESSION, accession):
                raise ValueError('invalid SEC accession number')
        if self.filed_at and self.filed_at > self.accessed_at:
            raise ValueError('source filed after retrieval')
        if self.accepted_at:
            if self.accepted_at.tzinfo is None:
                raise ValueError('acceptance timestamp requires timezone')
            if self.accepted_at.date() > self.accessed_at or (self.filed_at and self.accepted_at.date() < self.filed_at):
                raise ValueError('invalid filing acceptance date')
        if self.is_amendment != self.source_type.endswith('/A'):
            raise ValueError('amendment flag must match form type')
        if self.is_amendment:
            if not self.original_accession_number or self.original_accession_number == self.accession_number:
                raise ValueError('amendment requires distinct original accession')
        elif self.original_accession_number is not None:
            raise ValueError('original accession only applies to amendments')
        if self.source_type in SEC_FORMS:
            parts = urlsplit(self.url)
            if not (parts.hostname == 'sec.gov' or parts.hostname.endswith('.sec.gov')):
                raise ValueError('SEC filing evidence requires original SEC URL')
            if not self.accession_number or not self.filed_at or not self.cik:
                raise ValueError('SEC filing requires accession, filed date and issuer CIK')
            archive = re.search(r'/Archives/edgar/data/(\d+)/(\d{18})/', parts.path, re.I)
            if not archive or archive[2] != self.accession_number.replace('-', ''):
                raise ValueError('SEC archive accession contradicts source')
            # Section 16 archive paths may identify a reporting owner, not issuer.
            allowed = {self.cik, *self.reporting_owner_ciks} if self.source_type in SECTION16 else {self.cik}
            if archive[1].zfill(10) not in allowed:
                raise ValueError('SEC archive CIK contradicts issuer and reporting owners')
            query_accessions = parse_qs(parts.query).get('accession_number', [])
            if any(a != self.accession_number for a in query_accessions):
                raise ValueError('URL accession locator contradicts source')
            if any(a != self.accession_number for a in re.findall(ACCESSION, self.source_locator)):
                raise ValueError('source locator accession contradicts source')
        return self


class InsiderRole(InsiderModel):
    role_type: Literal['OFFICER', 'DIRECTOR', 'TEN_PERCENT_OWNER']
    title: Text
    start_date: Date | None = None
    end_date: Date | None = None
    source_id: Identifier

    @model_validator(mode='after')
    def tenure(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError('role end precedes start')
        return self


class InsiderPerson(InsiderModel):
    id: Identifier
    name: Text
    reporting_owner_type: Literal['INDIVIDUAL', 'ENTITY']
    reporting_owner_cik: CIK = None
    identity_source_id: Identifier
    roles: list[InsiderRole] = Field(min_length=1)

    @model_validator(mode='after')
    def person(self):
        if self.reporting_owner_type == 'ENTITY' and any(r.role_type != 'TEN_PERCENT_OWNER' for r in self.roles):
            raise ValueError('entity holders cannot be human officers or directors')
        return self


class InsiderCompensation(InsiderModel):
    id: Identifier
    person_id: Identifier
    fiscal_year: Year | None = None
    compensation_type: Literal['SALARY', 'BONUS', 'NON_EQUITY_INCENTIVE', 'STOCK_AWARD',
                               'OPTION_AWARD', 'OTHER_COMPENSATION', 'SUMMARY_COMPENSATION_TOTAL',
                               'VESTING_TERMS', 'PERFORMANCE_CONDITIONS', 'SEVERANCE',
                               'CHANGE_IN_CONTROL', 'CLAWBACK', 'OTHER']
    value: FinancialDecimal | None = None
    currency: Text | None = None
    value_basis: Literal['REPORTED_ANNUAL_AMOUNT', 'GRANT_DATE_FAIR_VALUE', 'UNQUANTIFIED_TERMS']
    terms: Text
    source_id: Identifier
    source_locator: Text

    @field_serializer('value')
    def plain_value(self, value):
        return format(value, 'f') if value is not None else None

    @model_validator(mode='after')
    def reported(self):
        if self.compensation_type in {'VESTING_TERMS', 'PERFORMANCE_CONDITIONS', 'CLAWBACK'} and self.value_basis != 'UNQUANTIFIED_TERMS':
            raise ValueError('vesting/performance/clawback terms require unquantified terms basis')
        if self.value_basis == 'UNQUANTIFIED_TERMS':
            if self.value is not None or self.currency is not None:
                raise ValueError('unquantified terms cannot contain value or currency')
        elif self.value is None or self.value < 0 or self.currency not in CURRENCIES:
            raise ValueError('reported compensation requires nonnegative value and currency')
        if self.value is not None and self.compensation_type in {'STOCK_AWARD', 'OPTION_AWARD'} and self.value_basis != 'GRANT_DATE_FAIR_VALUE':
            raise ValueError('stock/option awards require grant-date fair value basis')
        return self


class InsiderTransaction(InsiderModel):
    id: Identifier
    person_id: Identifier
    source_id: Identifier
    source_row_id: Identifier
    transaction_date: Date
    table_type: TableType
    security_title: Text
    transaction_code: Annotated[str, Field(pattern=r'^[A-Z][A-Z0-9/+\-]{0,7}$')]
    acquired_disposed: Literal['A', 'D']
    quantity: FinancialDecimal
    price_per_unit: FinancialDecimal | None = None
    price_currency: Text | None = None
    ownership_form: OwnershipForm
    indirect_ownership_nature: Text | None = None
    purchase_venue: Literal['OPEN_MARKET', 'PRIVATE', 'UNKNOWN']
    purchase_venue_locator: Text | None = None
    rule_10b5_1_status: Literal['REPORTED_YES', 'REPORTED_NO', 'NOT_DISCLOSED']
    review_status: Literal['VERIFIED', 'UNRESOLVED']
    supersedes_id: Identifier | None = None
    duplicate_of_id: Identifier | None = None
    notes: str = Field(max_length=4000)

    @field_serializer('quantity', 'price_per_unit')
    def plain_value(self, value):
        return format(value, 'f') if value is not None else None

    @model_validator(mode='after')
    def reported(self):
        if self.quantity <= 0:
            raise ValueError('transaction quantity must be positive')
        if self.price_per_unit is None:
            if self.price_currency is not None:
                raise ValueError('missing price requires null currency')
        elif self.price_per_unit < 0 or self.price_currency not in CURRENCIES:
            raise ValueError('reported price requires nonnegative value and currency')
        if self.purchase_venue == 'UNKNOWN':
            if self.purchase_venue_locator is not None:
                raise ValueError('unknown venue requires null locator')
        elif self.transaction_code != 'P' or not self.purchase_venue_locator:
            raise ValueError('purchase venue requires P code and explicit cited statement')
        if self.review_status == 'UNRESOLVED' and not self.notes.strip():
            raise ValueError('unresolved transaction requires explanatory note')
        if self.supersedes_id and self.duplicate_of_id:
            raise ValueError('cannot combine supersedes and duplicate links')
        if self.ownership_form == 'DIRECT' and self.indirect_ownership_nature is not None:
            raise ValueError('direct ownership cannot have indirect nature')
        return self


class InsiderOwnership(InsiderModel):
    id: Identifier
    person_id: Identifier
    source_id: Identifier
    source_row_id: Identifier
    as_of_date: Date
    table_type: TableType
    security_title: Text
    reported_quantity: FinancialDecimal
    ownership_form: OwnershipForm
    indirect_ownership_nature: Text | None = None
    notes: str = Field(max_length=4000)

    @field_serializer('reported_quantity')
    def plain_value(self, value):
        return format(value, 'f')

    @model_validator(mode='after')
    def reported(self):
        if self.reported_quantity < 0:
            raise ValueError('reported ownership cannot be negative')
        if self.ownership_form == 'DIRECT' and self.indirect_ownership_nature is not None:
            raise ValueError('direct ownership cannot have indirect nature')
        return self


class InsiderResearchInput(InsiderModel):
    schema_version: Literal['1.0']
    research_type: Literal['MANAGEMENT_INSIDER_ACTIVITY']
    company: InsiderCompany
    scope: InsiderScope
    sources: list[InsiderSource]
    people: list[InsiderPerson]
    compensation: list[InsiderCompensation]
    transactions: list[InsiderTransaction]
    ownership: list[InsiderOwnership]
    limitations: list[Text]

    @model_validator(mode='after')
    def evidence(self):
        for collection in (self.sources, self.people, self.compensation, self.transactions, self.ownership):
            if len({r.id for r in collection}) != len(collection):
                raise ValueError('duplicate run-scoped record ID')
        owners = [p.reporting_owner_cik for p in self.people if p.reporting_owner_cik]
        if len(set(owners)) != len(owners):
            raise ValueError('duplicate reporting owner CIK')
        accessions = [s.accession_number for s in self.sources if s.accession_number]
        if len(set(accessions)) != len(accessions):
            raise ValueError('duplicate filing accession under different source IDs')
        if self.scope.coverage_status != 'COMPLETE_WITHIN_DECLARED_SCOPE' and not self.limitations:
            raise ValueError('incomplete coverage requires limitations')
        sources = {s.id: s for s in self.sources}
        people = {p.id: p for p in self.people}
        transactions = {t.id: t for t in self.transactions}

        def source_ref(key):
            if key not in sources:
                raise ValueError('unknown same-run source')
            return sources[key]

        def person_ref(key):
            if key not in people:
                raise ValueError('unknown same-run person')
            return people[key]

        def issuer_ref(source):
            matching_cik = self.company.cik and source.cik == self.company.cik
            matching_name = (' '.join(source.publisher.split()).casefold() ==
                             ' '.join(self.company.name.split()).casefold())
            if not matching_cik and not matching_name:
                raise ValueError('primary source issuer attribution cannot be verified')

        def owner_ref(row, forms):
            person, source = person_ref(row.person_id), source_ref(row.source_id)
            if source.source_type not in forms:
                raise ValueError('row requires applicable original SEC ownership/transaction form')
            if not self.company.cik or source.cik != self.company.cik:
                raise ValueError('filing issuer CIK is unverified or contradicts company')
            if not person.reporting_owner_cik or person.reporting_owner_cik not in source.reporting_owner_ciks:
                raise ValueError('filing reporting owner does not match verified person CIK')
            return source

        for source in self.sources:
            if source.cik and self.company.cik and source.cik != self.company.cik:
                raise ValueError('source issuer CIK contradicts company')
            issuer_ref(source)
            if source.accessed_at > self.scope.researched_as_of or (source.filed_at and source.filed_at > self.scope.researched_as_of) or (source.accepted_at and source.accepted_at.date() > self.scope.researched_as_of):
                raise ValueError('source dates exceed research cutoff')
        for person in self.people:
            identity = source_ref(person.identity_source_id)
            if person.reporting_owner_cik and person.reporting_owner_cik not in identity.reporting_owner_ciks:
                raise ValueError('identity source does not verify reporting owner CIK')
            for role in person.roles:
                source = source_ref(role.source_id)
                if any(d and d > self.scope.researched_as_of for d in (role.start_date, role.end_date)):
                    if source.source_type != 'ISSUER_AGREEMENT' or not re.search(r'\b(expected|scheduled)\b', source.source_locator, re.I):
                        raise ValueError('future tenure requires explicitly expected issuer agreement evidence')
        for item in self.compensation:
            person = person_ref(item.person_id)
            source = source_ref(item.source_id)
            if person.reporting_owner_type != 'INDIVIDUAL':
                raise ValueError('executive compensation requires an individual')
            if source.source_type in SECTION16:
                raise ValueError('compensation requires proxy or issuer disclosure')
        for collection in (self.transactions, self.ownership):
            row_keys = [(r.source_id, r.source_row_id) for r in collection]
            if len(set(row_keys)) != len(row_keys):
                raise ValueError('duplicate row in a filing')
            for row in collection:
                if row.ownership_form == 'INDIRECT' and not row.indirect_ownership_nature:
                    if not any('indirect' in limitation.casefold() for limitation in self.limitations):
                        raise ValueError('undisclosed indirect nature requires explicit indirect ownership limitation')
        replaced = set()
        for row in self.transactions:
            source = owner_ref(row, {'4', '4/A', '5', '5/A'})
            if not self.scope.period_start <= row.transaction_date <= self.scope.period_end:
                raise ValueError('transaction date outside requested period')
            if row.transaction_date > source.filed_at:
                raise ValueError('transaction date follows filing')
            link = row.supersedes_id or row.duplicate_of_id
            if source.is_amendment and not row.supersedes_id and row.review_status == 'VERIFIED':
                raise ValueError('verified amendment row requires original transaction link')
            if link:
                target = transactions.get(link)
                if target is None or target.id == row.id:
                    raise ValueError('unknown or self-linked same-run transaction')
                identity_fields = ('person_id', 'table_type', 'security_title', 'ownership_form',
                                   'indirect_ownership_nature', 'acquired_disposed', 'transaction_date',
                                   'transaction_code')
                if any(getattr(row, f) != getattr(target, f) for f in identity_fields):
                    raise ValueError('linked transactions describe different event identities')
                if row.supersedes_id:
                    target_source = sources[target.source_id]
                    if not source.is_amendment or source.original_accession_number != target_source.accession_number:
                        raise ValueError('correction requires amendment and original accession linkage')
                    if target.duplicate_of_id:
                        raise ValueError('correction must link original economic row, not an excluded duplicate')
                    if source.source_type.removesuffix('/A') != target_source.source_type.removesuffix('/A'):
                        raise ValueError('amendment form must match original filing form')
                    if source.filed_at < target_source.filed_at or target.id in replaced:
                        raise ValueError('ambiguous branched or earlier correction')
                    replaced.add(target.id)
                elif any(getattr(row, f) != getattr(target, f) for f in ('quantity', 'price_per_unit', 'price_currency')):
                    raise ValueError('duplicate economic event values disagree')
                seen = {row.id}
                current = target
                while current:
                    if current.id in seen:
                        raise ValueError('cycle in transaction links')
                    seen.add(current.id)
                    next_id = current.supersedes_id or current.duplicate_of_id
                    current = transactions.get(next_id) if next_id else None
        for row in self.ownership:
            source = owner_ref(row, SECTION16)
            if row.as_of_date > self.scope.researched_as_of or row.as_of_date > source.filed_at:
                raise ValueError('ownership observation follows filing or cutoff')
        return self
