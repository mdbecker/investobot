"""Immutable research-only imports; reported insiders are never household positions."""

import json
from datetime import datetime, timezone

from invest.insider_models import InsiderResearchInput
from invest.research_identity import verify_company
from invest.research_skills import SUPPORTED_SKILLS
from invest.research_storage import canonical_json_hash, decimal_text, insert_record

DDL = [
    """CREATE TABLE research_insider_people (
        run_id TEXT NOT NULL, person_id TEXT NOT NULL, name TEXT NOT NULL,
        reporting_owner_type TEXT NOT NULL CHECK(reporting_owner_type IN ('INDIVIDUAL','ENTITY')),
        reporting_owner_cik TEXT, roles_json TEXT NOT NULL, identity_source_id TEXT NOT NULL,
        PRIMARY KEY(run_id,person_id),
        FOREIGN KEY(run_id) REFERENCES research_runs(id),
        FOREIGN KEY(run_id,identity_source_id) REFERENCES research_sources(run_id,source_id))""",
    """CREATE TABLE research_insider_compensation (
        run_id TEXT NOT NULL, compensation_id TEXT NOT NULL, person_id TEXT NOT NULL,
        fiscal_year INTEGER, compensation_type TEXT NOT NULL CHECK(compensation_type IN
          ('SALARY','BONUS','NON_EQUITY_INCENTIVE','STOCK_AWARD','OPTION_AWARD',
           'OTHER_COMPENSATION','SUMMARY_COMPENSATION_TOTAL','VESTING_TERMS',
           'PERFORMANCE_CONDITIONS','SEVERANCE','CHANGE_IN_CONTROL','CLAWBACK','OTHER')),
        value_text TEXT, currency TEXT, value_basis TEXT NOT NULL CHECK(value_basis IN
          ('REPORTED_ANNUAL_AMOUNT','GRANT_DATE_FAIR_VALUE','UNQUANTIFIED_TERMS')),
        terms TEXT NOT NULL, source_id TEXT NOT NULL, source_locator TEXT NOT NULL,
        PRIMARY KEY(run_id,compensation_id),
        FOREIGN KEY(run_id,person_id) REFERENCES research_insider_people(run_id,person_id),
        FOREIGN KEY(run_id,source_id) REFERENCES research_sources(run_id,source_id),
        CHECK((value_basis='UNQUANTIFIED_TERMS' AND value_text IS NULL AND currency IS NULL)
          OR (value_basis<>'UNQUANTIFIED_TERMS' AND value_text IS NOT NULL AND currency IS NOT NULL)))""",
    """CREATE TABLE research_insider_transactions (
        run_id TEXT NOT NULL, transaction_id TEXT NOT NULL, person_id TEXT NOT NULL,
        source_id TEXT NOT NULL, source_row_id TEXT NOT NULL, transaction_date TEXT NOT NULL,
        table_type TEXT NOT NULL CHECK(table_type IN ('NON_DERIVATIVE','DERIVATIVE')),
        security_title TEXT NOT NULL, transaction_code TEXT NOT NULL,
        acquired_disposed TEXT NOT NULL CHECK(acquired_disposed IN ('A','D')),
        quantity_text TEXT NOT NULL CHECK(quantity_text<>'' AND quantity_text NOT GLOB '*[^0-9.]*'),
        price_text TEXT, price_currency TEXT,
        ownership_form TEXT NOT NULL CHECK(ownership_form IN ('DIRECT','INDIRECT')),
        indirect_nature TEXT, purchase_venue TEXT NOT NULL CHECK(purchase_venue IN
          ('OPEN_MARKET','PRIVATE','UNKNOWN')),
        rule_10b5_1_status TEXT NOT NULL CHECK(rule_10b5_1_status IN
          ('REPORTED_YES','REPORTED_NO','NOT_DISCLOSED')),
        review_status TEXT NOT NULL CHECK(review_status IN ('VERIFIED','UNRESOLVED')),
        purchase_venue_locator TEXT, supersedes_id TEXT, duplicate_of_id TEXT, notes TEXT NOT NULL,
        PRIMARY KEY(run_id,transaction_id), UNIQUE(run_id,source_id,source_row_id),
        FOREIGN KEY(run_id,person_id) REFERENCES research_insider_people(run_id,person_id),
        FOREIGN KEY(run_id,source_id) REFERENCES research_sources(run_id,source_id),
        FOREIGN KEY(run_id,supersedes_id) REFERENCES research_insider_transactions(run_id,transaction_id)
          DEFERRABLE INITIALLY DEFERRED,
        FOREIGN KEY(run_id,duplicate_of_id) REFERENCES research_insider_transactions(run_id,transaction_id)
          DEFERRABLE INITIALLY DEFERRED,
        CHECK(supersedes_id IS NULL OR duplicate_of_id IS NULL),
        CHECK((price_text IS NULL AND price_currency IS NULL)
           OR (price_text IS NOT NULL AND price_currency IS NOT NULL)),
        CHECK(price_text IS NULL OR (price_text<>'' AND price_text NOT GLOB '*[^0-9.]*')))""",
    """CREATE TABLE research_insider_ownership (
        run_id TEXT NOT NULL, holding_id TEXT NOT NULL, person_id TEXT NOT NULL,
        source_id TEXT NOT NULL, source_row_id TEXT NOT NULL, as_of_date TEXT NOT NULL,
        table_type TEXT NOT NULL CHECK(table_type IN ('NON_DERIVATIVE','DERIVATIVE')),
        security_title TEXT NOT NULL,
        quantity_text TEXT NOT NULL CHECK(quantity_text<>'' AND quantity_text NOT GLOB '*[^0-9.]*'),
        ownership_form TEXT NOT NULL CHECK(ownership_form IN ('DIRECT','INDIRECT')),
        indirect_nature TEXT, notes TEXT NOT NULL,
        PRIMARY KEY(run_id,holding_id), UNIQUE(run_id,source_id,source_row_id),
        FOREIGN KEY(run_id,person_id) REFERENCES research_insider_people(run_id,person_id),
        FOREIGN KEY(run_id,source_id) REFERENCES research_sources(run_id,source_id))""",
    """CREATE INDEX research_insider_transaction_person_idx
       ON research_insider_transactions(run_id,person_id,transaction_date)""",
]


def create_tables(connection):
    for statement in DDL:
        connection.execute(statement)


def canonical_package(payload):
    model = InsiderResearchInput.model_validate(payload)
    data = model.model_dump(mode='json')
    for name in ('sources', 'people', 'compensation', 'transactions', 'ownership'):
        data[name].sort(key=lambda item: item['id'])
    data['limitations'].sort()
    for source in data['sources']:
        source['reporting_owner_ciks'].sort()
    for person in data['people']:
        person['roles'].sort(key=lambda role: json.dumps(role, sort_keys=True))
    for item in data['compensation']:
        item['value'] = decimal_text(item['value'])
    for item in data['transactions']:
        for key in ('quantity', 'price_per_unit'):
            item[key] = decimal_text(item[key])
    for item in data['ownership']:
        item['reported_quantity'] = decimal_text(item['reported_quantity'])
    name = 'investobot-management-insiders'
    entry = SUPPORTED_SKILLS[name]
    identity = dict(skill_name=name, skill_version=entry['skill_version'],
                    schema_version=entry['schema_version'], research_type=data['research_type'])
    package, run_id = canonical_json_hash(data, identity)
    return data, package, run_id, identity


def validation_warnings(data):
    warnings = list(data['limitations'])
    if data['scope']['coverage_status'] != 'COMPLETE_WITHIN_DECLARED_SCOPE':
        warnings.append('Incomplete filing and compensation coverage; missing disclosure is unknown.')
    warnings.append('Human review must verify original filings, issuer and reporting-owner identity; '
                    'structural validation cannot establish source truth or insider intent.')
    if not data['company'].get('cik'):
        warnings.append('Issuer CIK unknown; Section 16 transactions and ownership are unavailable.')
    if not data['transactions']:
        warnings.append('No reported transactions supplied; this does not establish absence of activity.')
    if not data['compensation']:
        warnings.append('Compensation disclosure unavailable in this package.')
    for row in data['transactions']:
        if row['review_status'] == 'UNRESOLVED':
            warnings.append(f"Unresolved transaction {row['id']} excluded: {row['notes']}")
        if row['price_per_unit'] is None:
            warnings.append(f"Price unknown for {row['id']}; gross line value unavailable.")
        if row['rule_10b5_1_status'] == 'NOT_DISCLOSED':
            warnings.append(f"Rule 10b5-1 status not disclosed for {row['id']}.")
        if row['transaction_code'] == 'P' and row['purchase_venue'] == 'UNKNOWN':
            warnings.append(f"Purchase venue unknown for {row['id']}; P alone does not prove open market.")
    for row in [*data['transactions'], *data['ownership']]:
        if row['ownership_form'] == 'INDIRECT' and not row['indirect_ownership_nature']:
            warnings.append(f"Indirect ownership nature not disclosed for {row['id']}.")
    return list(dict.fromkeys(warnings))


def import_research(ledger, payload, yes=False):
    data, package, run_id, identity = canonical_package(payload)
    verify_company(ledger, data['company'])
    warnings = validation_warnings(data)
    counts = {f'{name}_count': len(data[key]) for name, key in
              [('person', 'people'), ('compensation', 'compensation'),
               ('transaction', 'transactions'), ('ownership', 'ownership'), ('source', 'sources')]}
    compact = dict(counts, scope=data['scope'], limitations=data['limitations'], warnings=warnings)
    exists = ledger.connection.execute('SELECT 1 FROM research_runs WHERE id=?', (run_id,)).fetchone()
    result = dict(status='UNCHANGED' if exists else 'PREVIEW', committed=False,
                  run_id=run_id, research_run_id=run_id, mutation_scope='research',
                  **counts, coverage_status=data['scope']['coverage_status'], warnings=warnings)
    if not yes or exists:
        return result
    company = data['company']
    run = dict(id=run_id, **identity, company_name=company['name'], ticker=company['ticker'],
               security_id=company['security_id'], cik=company['cik'], fiscal_year=None,
               fiscal_period=None, period_end=None, researched_as_of=data['scope']['researched_as_of'],
               imported_at=datetime.now(timezone.utc).isoformat(),
               coverage_status=data['scope']['coverage_status'], summary_json=json.dumps(compact),
               package_json=package)
    with ledger.connection:
        insert_record(ledger.connection, 'research_runs', run)
        for source in data['sources']:
            row = dict(source, run_id=run_id, source_id=source['id'], is_restatement=False)
            row.pop('id')
            row.pop('reporting_owner_ciks')
            insert_record(ledger.connection, 'research_sources', row)
        for person in data['people']:
            row = dict(person, run_id=run_id, person_id=person['id'],
                       roles_json=json.dumps(person['roles']))
            row.pop('id')
            row.pop('roles')
            insert_record(ledger.connection, 'research_insider_people', row)
        for item in data['compensation']:
            row = dict(item, run_id=run_id, compensation_id=item['id'], value_text=item['value'])
            row.pop('id')
            row.pop('value')
            insert_record(ledger.connection, 'research_insider_compensation', row)
        for item in data['transactions']:
            row = dict(item, run_id=run_id, transaction_id=item['id'], quantity_text=item['quantity'],
                       price_text=item['price_per_unit'], indirect_nature=item['indirect_ownership_nature'])
            for key in ('id', 'quantity', 'price_per_unit', 'indirect_ownership_nature'):
                row.pop(key)
            insert_record(ledger.connection, 'research_insider_transactions', row)
        for item in data['ownership']:
            row = dict(item, run_id=run_id, holding_id=item['id'], quantity_text=item['reported_quantity'],
                       indirect_nature=item['indirect_ownership_nature'])
            for key in ('id', 'reported_quantity', 'indirect_ownership_nature'):
                row.pop(key)
            insert_record(ledger.connection, 'research_insider_ownership', row)
    return dict(result, status='IMPORTED', committed=True)
