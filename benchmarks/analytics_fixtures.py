"""Fixed fictional analytical evidence; no live source, private state or agent input."""

import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

import duckdb

from invest.models import SecurityInput

DATE = '2026-10-10'
ROOT = Path(__file__).resolve().parents[1]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


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
