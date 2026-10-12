"""Fixed fictional analytical evidence; no live source, private state or agent input."""

import copy
import hashlib
import json
from datetime import date, timedelta
from decimal import Decimal, localcontext
from pathlib import Path

import duckdb

from invest.models import SecurityInput

DATE = '2026-10-10'
ROOT = Path(__file__).resolve().parents[1]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def provider_file(root, dimensions):
    funds = dimensions['funds']
    size = dimensions['constituents_per_fund']
    payload = {'holdings': {}, 'metadata': {}, 'history': {}, 'quote': {}, 'screen': []}
    for index in range(funds):
        ticker = f'FUND{index:04}'
        weight = (Decimal(100) / size).quantize(Decimal('0.0000000001'))
        payload['holdings'][ticker] = [
            {'asset': f'COMP{row:06}', 'name': f'Fictional company {row}',
             'weightPercentage': str(weight if row < size - 1 else 100 - weight * (size - 1)), 'updated': DATE,
             'assetType': 'STOCK', 'sector': 'Fictional sector'} for row in range(size)]
        payload['metadata'][ticker] = [{'symbol': ticker, 'expenseRatio': '0.1',
            'issuer': 'Fictional sponsor', 'aum': '1000000', 'isEtf': True}]
        history_count = dimensions.get('provider_history_observations', 5)
        if type(history_count) is not int or history_count < 1:
            raise ValueError('Provider history observations must be a positive integer')
        payload['history'][ticker] = [{'date': (date(2026, 10, 9) -
            timedelta(days=history_count - row - 1)).isoformat(), 'adjClose': str(100 + row)}
            for row in range(history_count)]
        payload['quote'][ticker] = [{'symbol': ticker, 'price': '100', 'timestamp': 1791547200}]
        payload['screen'].append({'symbol': ticker, 'companyName': f'Fictional fund {index}',
            'isEtf': True, 'isFund': False, 'marketCap': '1000000', 'price': '100'})
    payload['screen'].extend({'symbol': f'EQUITY{row:04}', 'companyName': f'Fictional equity {row}',
        'isEtf': False, 'isFund': False, 'marketCap': '1000000', 'price': '100'}
        for row in range(funds))
    path = root / 'public-provider.json'
    path.write_text(json.dumps(payload))
    return path, payload


def parquet_file(root, dimensions, security_id):
    path = root / 'observations.parquet'
    count = dimensions['parquet_observations']
    with duckdb.connect(':memory:') as connection:
        connection.execute('CREATE TABLE observations AS SELECT i AS row_id, ?::VARCHAR AS security_id, '
            "DATE '2026-10-01' + (i % 9)::INTEGER AS date, "
            "'100' AS total_return_index, 'USD' AS currency, true AS dividend_adjusted, "
            "DATE '2026-09-01' AS effective_from, DATE '2026-10-10' AS effective_to "
            'FROM range(?) t(i)', [security_id, count])
        connection.execute('COPY observations TO ? (FORMAT PARQUET)', [str(path)])
        vintage_path = root / 'constituent-vintages.parquet'
        connection.execute('CREATE TABLE vintages AS SELECT ?::VARCHAR security_id, '
            "effective_from::DATE effective_from, effective_to::DATE effective_to, "
            "observed_at::DATE observed_at FROM (VALUES "
            "('2026-10-01','2026-10-05','2026-09-30'),"
            "('2026-10-06','2026-10-09','2026-10-05'),"
            "('2026-10-01','2026-10-09','2026-10-20')) "
            'v(effective_from,effective_to,observed_at)', [security_id])
        connection.execute('COPY vintages TO ? (FORMAT PARQUET)', [str(vintage_path)])
    artifact = {'id': 'fictional-observations', 'kind': 'DIVIDEND_ADJUSTED_PRICES',
        'relative_path': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'provider': 'FICTIONAL', 'observed_at': DATE, 'as_of': DATE,
        'data_environment': 'SYNTHETIC', 'coverage': {'rows': count}}
    vintages = {**artifact, 'id': 'fictional-vintage-constituents',
        'kind': 'CONSTITUENT_VINTAGES', 'relative_path': vintage_path.name,
        'sha256': hashlib.sha256(vintage_path.read_bytes()).hexdigest(), 'coverage': {'rows': 3}}
    return {'id': 'fictional-analytics', 'data_environment': 'SYNTHETIC', 'artifacts': [artifact, vintages]}


def corpus(dimensions, *, start=0, count=None):
    size = dimensions['research_chunks'] if count is None else count
    width = dimensions['vector_dimensions']
    vector = [1.0] + [0.0] * (width - 1)
    rows = []
    for index in range(start, start + size):
        text = f'Fictional permitted original issuer evidence passage {index:06d}.'
        rows.append({'chunk_id': f'chunk-{index:08}', 'document_id': f'document-{index:08}',
            'issuer_id': f'issuer-{index % 2}', 'text': text,
            'source_url': f'https://example.invalid/evidence/{index}', 'source_date': DATE,
            'permission': 'PERMITTED', 'license': 'Independently reviewed fictional indexing rights',
            'data_environment': 'SYNTHETIC', 'offset_start': 0, 'offset_end': len(text),
            'content_hash': hashlib.sha256(text.encode()).hexdigest(),
            'model_id': 'fictional-384-unit-v1', 'vector': vector})
    return rows


def daily_history(securities, years):
    first, last = date(2026 - years, 10, 10), date(2026, 10, 9)
    days = []
    while first <= last:
        if first.weekday() < 5:
            days.append(first.isoformat())
        first += timedelta(days=1)
    series = {sid: [{'date': day, 'total_return_index': str(100000 + index),
                     'dividend_adjusted': True, 'data_environment': 'SYNTHETIC',
                     'source': 'Explicit fictional weekday total-return calendar', 'currency': 'USD'}
                    for index, day in enumerate(days)] for sid in securities}
    return {'manifest_id': 'fictional-ten-year-total-return', 'data_environment': 'SYNTHETIC',
            'currency': 'USD', 'sessions': days, 'series': series}, days


def register_issuer(ledger, *, ticker='FAKE', cik='0000000001', name='Fictional company'):
    return register_security(ledger, 'fictional-issuer-' + cik, {'ticker': ticker, 'name': name, 'asset_type': 'STOCK',
        'currency': 'USD', 'source': 'Reviewed fictional original issuer registration',
        'cik': cik, 'issuer_id': cik, 'data_environment': 'SYNTHETIC',
        'issuer_identity_evidence': {'cik': cik, 'reviewed': True,
            'source': 'Reviewed fictional original issuer registration',
            'source_locator': f'https://example.invalid/issuer/{cik}'}})


def register_security(ledger, identity, payload):
    record = SecurityInput.model_validate(payload).model_dump(mode='json', exclude_none=True)
    record['id'] = identity
    ledger.put('securities', identity, record)
    return record


def earnings_package():
    return {'schema_version': '1.0', 'research_type': 'EARNINGS_FINANCIAL_STATEMENTS', 'company': {'name': 'Fictional Technology Corporation', 'ticker': 'FAKE', 'cik': '0000000001', 'security_id': None}, 'reporting_period': {'fiscal_year': 2026, 'fiscal_period': 'Q2', 'period_end': '2026-06-30'}, 'researched_as_of': '2026-10-10', 'coverage_status': 'PARTIAL', 'sources': [{'id': 'filing', 'source_type': 'SEC_10_Q', 'url': 'https://example.invalid/filing?record_id=public&api_key=secret', 'accession_number': 'SYNTHETIC-ACCESSION', 'filed_at': '2026-08-01', 'accessed_at': '2026-10-10', 'publisher': 'Fictional Corporation'}], 'metrics': [{'id': 'revenue', 'metric_code': 'REVENUE', 'metric_label': 'Consolidated revenue', 'value': '1250000000.00', 'unit': 'USD', 'accounting_basis': 'GAAP', 'measurement_type': 'REPORTED', 'period_type': 'DURATION', 'period_start': '2026-04-01', 'period_end': '2026-06-30', 'fiscal_year': 2026, 'fiscal_period': 'Q2', 'scope': 'CONSOLIDATED', 'segment_name': None, 'source_id': 'filing', 'source_locator': 'Financial statements; consolidated revenue', 'xbrl_taxonomy': None, 'xbrl_concept': None}], 'guidance': [], 'findings': [], 'limitations': ['Synthetic partial example']}

def political_package():
    source = {'id': 'role', 'url': 'https://company.example/leadership', 'publisher': 'Fictional Corporation', 'source_type': 'EXECUTIVE_BIOGRAPHY', 'published_at': None, 'accessed_at': '2026-10-09', 'individual_contributor_data': False, 'rights_basis': 'Public biography'}
    disclosure = {**source, 'id': 'record', 'url': 'https://records.example/statement', 'source_type': 'INDEPENDENT_DISCLOSURE', 'individual_contributor_data': True, 'rights_basis': 'Agent says allowed'}
    return {'schema_version': '1.0', 'research_type': 'EXECUTIVE_POLITICAL_CONTRIBUTIONS', 'company': {'name': 'Fictional Corporation', 'ticker': 'FAKE', 'security_id': None}, 'scope': {'jurisdiction': 'US_FEDERAL', 'period_start': '2024-01-01', 'period_end': '2026-10-09', 'researched_as_of': '2026-10-09', 'coverage_status': 'PARTIAL', 'rights_status': 'APPROVED'}, 'sources': [source, disclosure], 'executives': [{'id': 'exec', 'full_name': 'Fictional Officer', 'role': 'CEO', 'role_start': None, 'role_end': None, 'role_source_id': 'role', 'identity_status': 'VERIFIED'}], 'recipients': [{'id': 'pac', 'name': 'Fictional Committee', 'recipient_type': 'PAC', 'committee_id': None, 'candidate_id': None, 'candidate_name': None, 'recipient_party': 'UNKNOWN', 'party_basis': 'UNKNOWN', 'election_cycle': 2026, 'party_source_id': 'record'}], 'contributions': [{'id': 'gift', 'executive_id': 'exec', 'recipient_id': 'pac', 'date': '2026-01-15', 'amount_usd': '1000.00', 'transaction_kind': 'CONTRIBUTION', 'channel': 'DIRECT', 'source_system': 'SYNTHETIC', 'source_record_id': 'r1', 'underlying_transaction_key': 'underlying-1', 'identity_status': 'VERIFIED', 'countable': True, 'source_ids': ['role', 'record'], 'notes': 'Synthetic evidence'}], 'unresolved_matches': [], 'limitations': ['Synthetic partial research']}

def rights_policy():
    return {'intended_use': 'INVESTMENT_RESEARCH', 'review_reference': 'Synthetic review', 'sources': [{'origin': 'https://records.example', 'allow_individual_contributor_data': True, 'fec_derived': False, 'allow_fec_derived': False}]}

def news_package(*, cik, name, researched_as_of, window_start, event_date):
    """Original fictional primary-source evidence accepted by the strict news model."""
    return {'schema_version': '1.0', 'research_type': 'NEWS_CATALYSTS_THESIS_CHANGES', 'company': {'name': name, 'ticker': None, 'cik': cik, 'security_id': None}, 'scope': {'window_start': window_start, 'window_end': researched_as_of, 'researched_as_of': researched_as_of, 'coverage_status': 'COMPLETE_WITHIN_DECLARED_SCOPE', 'searched_source_types': ['ISSUER_RELEASE'], 'coverage_notes': 'Complete only within the declared fictional release scope.'}, 'sources': [{'id': 'fictional-release', 'source_type': 'ISSUER_RELEASE', 'publisher': name, 'url': f'https://example.invalid/{cik}/release', 'published_at': event_date, 'accessed_at': researched_as_of, 'source_locator': 'Opening paragraph'}], 'events': [{'event_key': 'fictional-factory-opened-' + cik, 'title': 'Fictional factory opened', 'category': 'OPERATIONS', 'event_date': event_date, 'date_status': 'CONFIRMED', 'event_status': 'CONFIRMED', 'affected_segments': [], 'primary_source_id': 'fictional-release', 'source_ids': ['fictional-release'], 'facts': [{'fact_key': 'opened', 'statement': 'The fictional factory opened.', 'source_id': 'fictional-release', 'source_locator': 'Opening paragraph', 'verification_status': 'VERIFIED'}], 'implications': [], 'follow_up_questions': []}], 'catalysts': [], 'theses': [], 'limitations': ['Entirely fictional offline evidence.']}


def specialty_template(kind):
    templates = {'competitive': {'schema_version': '1.0', 'research_type': 'COMPETITIVE_POSITION_PEER_COMPARISON', 'subject': {'entity_id': 'subject', 'name': 'Fictional Cloud A', 'ticker': 'FICA', 'cik': None, 'security_id': None}, 'scope': {'market_focus': 'Enterprise workflow software', 'geography': 'United States', 'researched_as_of': '2026-10-10', 'coverage_status': 'PARTIAL', 'coverage_notes': 'Fictional product releases and annual disclosures only.'}, 'sources': [{'id': 'a-release', 'source_type': 'ISSUER_RELEASE', 'publisher': 'Fictional Cloud A', 'url': 'https://example.invalid/a', 'published_at': '2026-09-15', 'accessed_at': '2026-10-10', 'source_locator': 'Products', 'accession_number': None, 'cik': None}, {'id': 'b-release', 'source_type': 'ISSUER_RELEASE', 'publisher': 'Fictional Cloud B', 'url': 'https://example.invalid/b', 'published_at': '2026-09-16', 'accessed_at': '2026-10-10', 'source_locator': 'Solutions', 'accession_number': None, 'cik': None}, {'id': 'a-financials', 'source_type': 'ISSUER_REPORT', 'publisher': 'Fictional Cloud A', 'url': 'https://example.invalid/a-results', 'published_at': '2026-08-01', 'accessed_at': '2026-10-10', 'source_locator': 'Income statement', 'accession_number': None, 'cik': None}, {'id': 'b-financials', 'source_type': 'ISSUER_REPORT', 'publisher': 'Fictional Cloud B', 'url': 'https://example.invalid/b-results', 'published_at': '2026-08-02', 'accessed_at': '2026-10-10', 'source_locator': 'Income statement', 'accession_number': None, 'cik': None}], 'peers': [{'entity_id': 'peer-b', 'name': 'Fictional Cloud B', 'ticker': 'FICB', 'cik': None, 'security_id': None, 'relationship': 'DIRECT_COMPETITOR', 'rationale': 'Offers competing workflow products to enterprise customers.', 'selection_source_id': 'b-release'}], 'overlaps': [{'id': 'enterprise-workflow', 'peer_id': 'peer-b', 'market': 'Enterprise workflow software', 'geography': 'United States', 'subject_segment': 'Cloud Applications', 'peer_segment': 'Enterprise Services', 'overlap_type': 'DIRECT', 'description': 'Both offer workflow automation to U.S. enterprises.', 'subject_source_id': 'a-release', 'peer_source_id': 'b-release', 'uncertainty': 'Product compatibility and customer win rates are not known.'}], 'findings': [{'id': 'integration', 'peer_id': 'peer-b', 'overlap_id': 'enterprise-workflow', 'kind': 'SUBJECT_ADVANTAGE', 'factual_basis': "Fictional A discloses a native integration absent from B's cited product catalog.", 'interpretation': 'May reduce deployment friction for some customers.', 'assumptions': 'Customers use the integrated platform.', 'uncertainty': "Absence from B's catalog does not prove B lacks an equivalent capability.", 'source_id': 'a-release', 'source_locator': 'Integrations', 'corroborating_source_ids': ['b-release']}], 'metrics': [{'id': 'a-revenue', 'entity_id': 'subject', 'metric_code': 'REVENUE', 'metric_definition': 'Consolidated revenue', 'value': '120000000.00', 'unit': 'USD', 'accounting_basis': 'GAAP', 'period_type': 'DURATION', 'period_start': '2026-01-01', 'period_end': '2026-06-30', 'scope': 'CONSOLIDATED', 'segment_name': None, 'overlap_id': None, 'source_id': 'a-financials', 'source_locator': 'Revenue'}, {'id': 'b-revenue', 'entity_id': 'peer-b', 'metric_code': 'REVENUE', 'metric_definition': 'Consolidated revenue', 'value': '100000000.00', 'unit': 'USD', 'accounting_basis': 'GAAP', 'period_type': 'DURATION', 'period_start': '2026-01-01', 'period_end': '2026-06-30', 'scope': 'CONSOLIDATED', 'segment_name': None, 'overlap_id': None, 'source_id': 'b-financials', 'source_locator': 'Revenue'}], 'limitations': ['All companies and disclosures are fictional.', 'No independently verified pricing or market-share figures.']}, 'insiders': {'schema_version': '1.1', 'research_type': 'MANAGEMENT_INSIDER_ACTIVITY', 'company': {'name': 'Fictional Systems Inc.', 'ticker': 'FCSI', 'cik': '0000000001', 'security_id': None}, 'scope': {'period_start': '2026-01-01', 'period_end': '2026-10-09', 'researched_as_of': '2026-10-10', 'coverage_status': 'PARTIAL', 'coverage_notes': 'Fictional offline sample, not exhaustive.'}, 'sources': [{'id': 'proxy', 'source_type': 'DEF 14A', 'publisher': 'SEC', 'url': 'https://www.sec.gov/Archives/edgar/data/1/000000000126000001/filing.xml', 'cik': '0000000001', 'reporting_owner_ciks': ['0000000002', '0000000003'], 'accession_number': '0000000001-26-000001', 'filed_at': '2026-04-01', 'accepted_at': '2026-04-01T12:00:00Z', 'accessed_at': '2026-10-10', 'source_locator': 'Fictional table rows and footnotes', 'is_amendment': False, 'original_accession_number': None}, {'id': 'f3', 'source_type': '3', 'publisher': 'SEC', 'url': 'https://www.sec.gov/Archives/edgar/data/1/000000000126000002/filing.xml', 'cik': '0000000001', 'reporting_owner_ciks': ['0000000002', '0000000003'], 'accession_number': '0000000001-26-000002', 'filed_at': '2026-04-02', 'accepted_at': '2026-04-02T12:00:00Z', 'accessed_at': '2026-10-10', 'source_locator': 'Fictional table rows and footnotes', 'is_amendment': False, 'original_accession_number': None}, {'id': 'f4', 'source_type': '4', 'publisher': 'SEC', 'url': 'https://www.sec.gov/Archives/edgar/data/1/000000000126000003/filing.xml', 'cik': '0000000001', 'reporting_owner_ciks': ['0000000002', '0000000003'], 'accession_number': '0000000001-26-000003', 'filed_at': '2026-05-05', 'accepted_at': '2026-05-05T12:00:00Z', 'accessed_at': '2026-10-10', 'source_locator': 'Fictional table rows and footnotes', 'is_amendment': False, 'original_accession_number': None}, {'id': 'amend', 'source_type': '4/A', 'publisher': 'SEC', 'url': 'https://www.sec.gov/Archives/edgar/data/1/000000000126000004/filing.xml', 'cik': '0000000001', 'reporting_owner_ciks': ['0000000002', '0000000003'], 'accession_number': '0000000001-26-000004', 'filed_at': '2026-05-06', 'accepted_at': '2026-05-06T12:00:00Z', 'accessed_at': '2026-10-10', 'source_locator': 'Fictional table rows and footnotes', 'is_amendment': True, 'original_accession_number': '0000000001-26-000003'}, {'id': 'f5', 'source_type': '5', 'publisher': 'SEC', 'url': 'https://www.sec.gov/Archives/edgar/data/1/000000000126000005/filing.xml', 'cik': '0000000001', 'reporting_owner_ciks': ['0000000002', '0000000003'], 'accession_number': '0000000001-26-000005', 'filed_at': '2026-05-07', 'accepted_at': '2026-05-07T12:00:00Z', 'accessed_at': '2026-10-10', 'source_locator': 'Fictional table rows and footnotes', 'is_amendment': False, 'original_accession_number': None}], 'people': [{'id': 'p1', 'name': 'Fictional Alex Example', 'reporting_owner_type': 'INDIVIDUAL', 'reporting_owner_cik': '0000000002', 'identity_source_id': 'proxy', 'roles': [{'role_type': 'OFFICER', 'title': 'Former Chief Executive', 'start_date': '2020-01-01', 'end_date': '2026-06-01', 'source_id': 'proxy'}]}, {'id': 'p2', 'name': 'Fictional Holdings LLC', 'reporting_owner_type': 'ENTITY', 'reporting_owner_cik': '0000000003', 'identity_source_id': 'f3', 'roles': [{'role_type': 'TEN_PERCENT_OWNER', 'title': 'Ten percent beneficial owner', 'start_date': None, 'end_date': None, 'source_id': 'f3'}]}], 'compensation': [{'id': 'salary', 'person_id': 'p1', 'fiscal_year': 2025, 'compensation_type': 'SALARY', 'value': '100000', 'currency': 'USD', 'value_basis': 'REPORTED_ANNUAL_AMOUNT', 'terms': 'Fictional reported proxy disclosure.', 'source_id': 'proxy', 'source_locator': 'Summary compensation table, fiscal 2025'}, {'id': 'stock', 'person_id': 'p1', 'fiscal_year': 2025, 'compensation_type': 'STOCK_AWARD', 'value': '200000', 'currency': 'USD', 'value_basis': 'GRANT_DATE_FAIR_VALUE', 'terms': 'Fictional reported proxy disclosure.', 'source_id': 'proxy', 'source_locator': 'Summary compensation table, fiscal 2025'}, {'id': 'total', 'person_id': 'p1', 'fiscal_year': 2025, 'compensation_type': 'SUMMARY_COMPENSATION_TOTAL', 'value': '300000', 'currency': 'USD', 'value_basis': 'REPORTED_ANNUAL_AMOUNT', 'terms': 'Fictional reported proxy disclosure.', 'source_id': 'proxy', 'source_locator': 'Summary compensation table, fiscal 2025'}], 'transactions': [{'id': 'purchase', 'person_id': 'p1', 'source_id': 'f4', 'source_row_id': 'purchase', 'transaction_date': '2026-05-01', 'table_type': 'NON_DERIVATIVE', 'security_title': 'Common Stock', 'transaction_code': 'P', 'acquired_disposed': 'A', 'quantity': '100', 'price_per_unit': '40.00', 'price_currency': 'USD', 'ownership_form': 'DIRECT', 'indirect_ownership_nature': None, 'purchase_venue': 'UNKNOWN', 'purchase_venue_locator': None, 'rule_10b5_1_status': 'NOT_DISCLOSED', 'review_status': 'VERIFIED', 'supersedes_id': None, 'duplicate_of_id': None, 'notes': 'Entirely fictional filing observation.'}, {'id': 'exercise', 'person_id': 'p1', 'source_id': 'f4', 'source_row_id': 'exercise', 'transaction_date': '2026-05-01', 'table_type': 'DERIVATIVE', 'security_title': 'Employee Stock Option', 'transaction_code': 'M', 'acquired_disposed': 'D', 'quantity': '200', 'price_per_unit': None, 'price_currency': None, 'ownership_form': 'DIRECT', 'indirect_ownership_nature': None, 'purchase_venue': 'UNKNOWN', 'purchase_venue_locator': None, 'rule_10b5_1_status': 'NOT_DISCLOSED', 'review_status': 'VERIFIED', 'supersedes_id': None, 'duplicate_of_id': None, 'notes': 'Entirely fictional filing observation.'}, {'id': 'grant', 'person_id': 'p1', 'source_id': 'f4', 'source_row_id': 'grant', 'transaction_date': '2026-05-01', 'table_type': 'NON_DERIVATIVE', 'security_title': 'Common Stock', 'transaction_code': 'A', 'acquired_disposed': 'A', 'quantity': '50', 'price_per_unit': None, 'price_currency': None, 'ownership_form': 'DIRECT', 'indirect_ownership_nature': None, 'purchase_venue': 'UNKNOWN', 'purchase_venue_locator': None, 'rule_10b5_1_status': 'NOT_DISCLOSED', 'review_status': 'VERIFIED', 'supersedes_id': None, 'duplicate_of_id': None, 'notes': 'Entirely fictional filing observation.'}, {'id': 'withholding', 'person_id': 'p1', 'source_id': 'f4', 'source_row_id': 'withholding', 'transaction_date': '2026-05-01', 'table_type': 'NON_DERIVATIVE', 'security_title': 'Common Stock', 'transaction_code': 'F', 'acquired_disposed': 'D', 'quantity': '10', 'price_per_unit': None, 'price_currency': None, 'ownership_form': 'DIRECT', 'indirect_ownership_nature': None, 'purchase_venue': 'UNKNOWN', 'purchase_venue_locator': None, 'rule_10b5_1_status': 'NOT_DISCLOSED', 'review_status': 'VERIFIED', 'supersedes_id': None, 'duplicate_of_id': None, 'notes': 'Entirely fictional filing observation.'}, {'id': 'gift', 'person_id': 'p1', 'source_id': 'f4', 'source_row_id': 'gift', 'transaction_date': '2026-05-01', 'table_type': 'NON_DERIVATIVE', 'security_title': 'Common Stock', 'transaction_code': 'G', 'acquired_disposed': 'D', 'quantity': '5', 'price_per_unit': None, 'price_currency': None, 'ownership_form': 'DIRECT', 'indirect_ownership_nature': None, 'purchase_venue': 'UNKNOWN', 'purchase_venue_locator': None, 'rule_10b5_1_status': 'NOT_DISCLOSED', 'review_status': 'VERIFIED', 'supersedes_id': None, 'duplicate_of_id': None, 'notes': 'Entirely fictional filing observation.'}, {'id': 'other', 'person_id': 'p1', 'source_id': 'f4', 'source_row_id': 'other', 'transaction_date': '2026-05-01', 'table_type': 'NON_DERIVATIVE', 'security_title': 'Common Stock', 'transaction_code': 'J', 'acquired_disposed': 'D', 'quantity': '3', 'price_per_unit': None, 'price_currency': None, 'ownership_form': 'DIRECT', 'indirect_ownership_nature': None, 'purchase_venue': 'UNKNOWN', 'purchase_venue_locator': None, 'rule_10b5_1_status': 'NOT_DISCLOSED', 'review_status': 'VERIFIED', 'supersedes_id': None, 'duplicate_of_id': None, 'notes': 'Entirely fictional filing observation.'}, {'id': 'sale', 'person_id': 'p1', 'source_id': 'f4', 'source_row_id': 'sale', 'transaction_date': '2026-05-01', 'table_type': 'NON_DERIVATIVE', 'security_title': 'Common Stock', 'transaction_code': 'S', 'acquired_disposed': 'D', 'quantity': '100', 'price_per_unit': '40.00', 'price_currency': 'USD', 'ownership_form': 'DIRECT', 'indirect_ownership_nature': None, 'purchase_venue': 'UNKNOWN', 'purchase_venue_locator': None, 'rule_10b5_1_status': 'NOT_DISCLOSED', 'review_status': 'VERIFIED', 'supersedes_id': None, 'duplicate_of_id': None, 'notes': 'Entirely fictional filing observation.'}, {'id': 'corrected-sale', 'person_id': 'p1', 'source_id': 'amend', 'source_row_id': 'corrected-sale', 'transaction_date': '2026-05-01', 'table_type': 'NON_DERIVATIVE', 'security_title': 'Common Stock', 'transaction_code': 'S', 'acquired_disposed': 'D', 'quantity': '120', 'price_per_unit': '40.00', 'price_currency': 'USD', 'ownership_form': 'DIRECT', 'indirect_ownership_nature': None, 'purchase_venue': 'UNKNOWN', 'purchase_venue_locator': None, 'rule_10b5_1_status': 'NOT_DISCLOSED', 'review_status': 'VERIFIED', 'supersedes_id': 'sale', 'duplicate_of_id': None, 'notes': 'Entirely fictional filing observation.'}, {'id': 'duplicate-sale', 'person_id': 'p1', 'source_id': 'f5', 'source_row_id': 'duplicate-sale', 'transaction_date': '2026-05-01', 'table_type': 'NON_DERIVATIVE', 'security_title': 'Common Stock', 'transaction_code': 'S', 'acquired_disposed': 'D', 'quantity': '120', 'price_per_unit': '40.00', 'price_currency': 'USD', 'ownership_form': 'DIRECT', 'indirect_ownership_nature': None, 'purchase_venue': 'UNKNOWN', 'purchase_venue_locator': None, 'rule_10b5_1_status': 'NOT_DISCLOSED', 'review_status': 'VERIFIED', 'supersedes_id': None, 'duplicate_of_id': 'corrected-sale', 'notes': 'Entirely fictional filing observation.'}, {'id': 'unresolved', 'person_id': 'p1', 'source_id': 'f5', 'source_row_id': 'unresolved', 'transaction_date': '2026-05-01', 'table_type': 'NON_DERIVATIVE', 'security_title': 'Common Stock', 'transaction_code': 'S', 'acquired_disposed': 'D', 'quantity': '999', 'price_per_unit': '40.00', 'price_currency': 'USD', 'ownership_form': 'DIRECT', 'indirect_ownership_nature': None, 'purchase_venue': 'UNKNOWN', 'purchase_venue_locator': None, 'rule_10b5_1_status': 'NOT_DISCLOSED', 'review_status': 'UNRESOLVED', 'supersedes_id': None, 'duplicate_of_id': None, 'notes': 'Possible duplicate, original event is not established.'}], 'ownership': [{'id': 'initial', 'person_id': 'p1', 'source_id': 'f3', 'source_row_id': 'initial', 'as_of_date': '2026-04-01', 'table_type': 'NON_DERIVATIVE', 'security_title': 'Common Stock', 'reported_quantity': '100', 'ownership_form': 'DIRECT', 'indirect_ownership_nature': None, 'notes': 'Fictional as-filed holding, not reconstructed.'}, {'id': 'later', 'person_id': 'p1', 'source_id': 'f4', 'source_row_id': 'later', 'as_of_date': '2026-05-01', 'table_type': 'NON_DERIVATIVE', 'security_title': 'Common Stock', 'reported_quantity': '125', 'ownership_form': 'DIRECT', 'indirect_ownership_nature': None, 'notes': 'Fictional as-filed holding, not reconstructed.'}], 'limitations': ['Partial fictional coverage; unknown venue and historical trading-plan status.']}, 'fund-diligence': {'schema_version': '1.0', 'research_type': 'ETF_MUTUAL_FUND_DILIGENCE', 'fund': {'name': 'Fictional Broad Index ETF', 'ticker': 'FAKE', 'exchange': 'NYSE Arca', 'isin': None, 'registrant_cik': '0000000123', 'series_id': 'S000000123', 'class_id': 'C000000123', 'class_name': 'ETF Shares', 'adviser': 'Fictional Adviser', 'security_id': None, 'fund_type': 'ETF', 'strategy_type': 'INDEX'}, 'scope': {'researched_as_of': '2026-10-10', 'coverage_status': 'PARTIAL', 'coverage_notes': 'Only the latest fictional prospectus and a top-holdings list were reviewed.'}, 'sources': [{'id': 'sec-identity', 'source_type': 'SEC_EDGAR', 'publisher': 'SEC EDGAR (fictional fixture)', 'url': 'https://www.sec.gov/Archives/edgar/data/123/000000012326000001/fictional.htm', 'published_at': '2026-09-20', 'filed_at': '2026-09-20', 'accessed_at': '2026-10-10', 'source_locator': 'Mock SEC filing: series S000000123 / class C000000123', 'accession_number': '0000000123-26-000001', 'registrant_cik': '0000000123', 'series_id': 'S000000123', 'class_id': 'C000000123'}, {'id': 'prospectus', 'source_type': 'PROSPECTUS', 'publisher': 'Fictional Fund', 'url': 'https://example.invalid/fake-prospectus', 'published_at': '2026-09-20', 'filed_at': None, 'accessed_at': '2026-10-10', 'source_locator': 'Series/class identifiers; fees and investment approach', 'accession_number': None, 'registrant_cik': '0000000123', 'series_id': 'S000000123', 'class_id': 'C000000123'}, {'id': 'holdings-page', 'source_type': 'SPONSOR_HOLDINGS', 'publisher': 'Fictional Fund', 'url': 'https://example.invalid/fake-holdings', 'published_at': '2026-10-08', 'filed_at': None, 'accessed_at': '2026-10-10', 'source_locator': 'Top holdings as of 2026-10-07', 'accession_number': None, 'registrant_cik': '0000000123', 'series_id': 'S000000123', 'class_id': None}], 'methodology': {'objective': 'Track a fictional broad index before fees.', 'index_name': 'Fictional Market Index', 'index_provider': 'Fictional Index Co.', 'benchmark_name': 'Fictional Market Index', 'selection_rules': None, 'weighting_method': 'Market-cap weighted', 'rebalance_policy': None, 'reconstitution_policy': None, 'replication_method': 'Sampling', 'active_approach': None, 'source_ids': ['prospectus'], 'uncertainty': 'Detailed constituent eligibility and rebalance rules were not available.'}, 'holdings_snapshot': {'as_of_date': '2026-10-07', 'coverage': 'TOP_N', 'source_id': 'holdings-page', 'holdings_count_reported': 2, 'notes': 'Only two top holdings supplied; not a full portfolio.'}, 'holdings': [{'id': 'holding-a', 'name': 'Fictional Stock A', 'security_identifier': None, 'asset_class': 'EQUITY', 'weight_pct': '6', 'source_id': 'holdings-page', 'source_locator': 'Holding A'}, {'id': 'holding-b', 'name': 'Fictional Stock B', 'security_identifier': None, 'asset_class': 'EQUITY', 'weight_pct': '4', 'source_id': 'holdings-page', 'source_locator': 'Holding B'}], 'metrics': [{'id': 'net-expense', 'code': 'NET_EXPENSE_RATIO', 'value': '0.15', 'unit': 'PCT', 'scope': 'CLASS', 'period_start': None, 'period_end': None, 'observed_as_of': '2026-09-20', 'waiver_end_date': None, 'source_id': 'prospectus', 'source_locator': 'Fees and expenses', 'notes': 'Reported prospectus net annual operating expenses.'}], 'findings': [{'id': 'fee-note', 'category': 'FEES', 'fact': 'The fictional share class reports a 0.15% net expense ratio.', 'interpretation': None, 'uncertainty': 'No brokerage spread or commission estimate is provided.', 'source_ids': ['prospectus'], 'source_locator': 'Fee table'}], 'limitations': ['Entirely fictional evidence.', 'Only two top holdings; full concentration is unknown.', 'Portfolio turnover, spreads, distribution history and full index rules were not supplied.']}}
    return templates[kind]


def research_payload(payload, specialty, scale):
    """Expand distinct fictional evidence within each native specialty's legal bounds.

    Scaling keeps dates, issuer identities and reviewed rights unchanged. New row
    identifiers and original-source locators distinguish fictional observations;
    insider correction/duplicate links remain within their original cloned group.
    Fund weights retain exact aggregate coverage rather than repeating its total.
    """
    if type(scale) is not int or scale < 1:
        raise ValueError('Research evidence scale must be a positive integer')
    fields = {'news': 'events', 'earnings': 'metrics', 'political': 'contributions',
              'competitive': 'metrics', 'insiders': 'transactions', 'fund-diligence': 'holdings'}
    if specialty not in fields:
        raise ValueError('Unsupported research specialty')
    result = copy.deepcopy(payload)
    field = fields[specialty]
    original = payload[field]
    if specialty == 'fund-diligence' and len(original) * scale > 100:
        raise ValueError('Fund research TOP_N evidence exceeds 100 holdings')
    if scale == 1:
        return result
    rows = []
    for group in range(scale):
        suffix = f'-fictional-evidence-{group:04}'
        for source in original:
            row = copy.deepcopy(source)
            if specialty == 'news':
                row['event_key'] += suffix
                row['title'] += f' (fictional observation {group})'
                for fact in row['facts']:
                    fact['fact_key'] += suffix
                    fact['statement'] += f' Fictional original observation {group}.'
                    fact['source_locator'] += f'; fictional observation {group}'
            else:
                row['id'] += suffix
            if specialty == 'earnings':
                row.update(scope='SEGMENT', segment_name=f'Fictional segment {group}')
                row['source_locator'] += f'; fictional segment {group}'
            elif specialty == 'political':
                for key in ('source_record_id', 'underlying_transaction_key'):
                    row[key] += suffix
                row['notes'] += f' Distinct fictional source record {group}.'
            elif specialty == 'competitive':
                row['metric_definition'] += f'; fictional comparable measure {group}'
                row['source_locator'] += f'; fictional comparable measure {group}'
            elif specialty == 'insiders':
                row['source_row_id'] += suffix
                for key in ('supersedes_id', 'duplicate_of_id'):
                    if row.get(key):
                        row[key] += suffix
                row['notes'] += f' Distinct fictional filing row group {group}.'
            elif specialty == 'fund-diligence':
                row['name'] += f' (fictional holding {group})'
                row['source_locator'] += f'; fictional holding {group}'
                with localcontext() as context:
                    context.prec = 80
                    weight = Decimal(source['weight_pct'])
                    piece = weight / Decimal(scale)
                    row['weight_pct'] = format(piece if group < scale-1 else
                        weight - piece * (scale-1), 'f')
            rows.append(row)
    if specialty == 'fund-diligence':
        rows.sort(key=lambda row: Decimal(row['weight_pct']), reverse=True)
        result['holdings_snapshot']['holdings_count_reported'] = len(rows)
    result[field] = rows
    return result
