"""Permission-gated immutable corpus with rebuildable FTS5 and sqlite-vec indexes."""

import hashlib
import json
import math
import os
import re
import struct
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from invest.db import connect
from invest.models import DomainError
from invest.political_models import safe_url

PRIVATE_KINDS = {'BROKER_ACCOUNT_HTML', 'BROKER_STATEMENT', 'NAMED_PERSONAL_CONTRIBUTION',
                 'PERSONAL_DOCUMENT', 'ACCOUNT_HTML'}
METADATA_FIELDS = {'chunk_id', 'document_id', 'issuer_id', 'source_url', 'source_date',
                   'observed_at', 'published_at', 'permission', 'content_hash',
                   'offset_start', 'offset_end', 'license', 'data_environment',
                   'model_id', 'supersedes_chunk_id', 'document_kind', 'source_locator',
                   'publisher', 'source_id', 'run_id'}


def open_search_connection(path, *, readonly=False):
    connection = connect(path, readonly=readonly, initialize=not readonly)
    try:
        runtime_path = os.environ.get('INVEST_ANALYTICS_RUNTIME')
        if not runtime_path:
            raise DomainError('Pinned SQLite vector runtime manifest unavailable', 2)
        try:
            record = json.loads(Path(runtime_path).read_text())['sqlite_vec']
            binary = Path(record['path'])
            if (record['version'] != '0.1.6' or not binary.is_file() or
                    hashlib.sha256(binary.read_bytes()).hexdigest() != record['sha256']):
                raise DomainError('Pinned SQLite vector binary verification failed', 2)
        except (OSError, KeyError, ValueError) as error:
            raise DomainError('Pinned SQLite vector manifest is invalid', 2) from error
        try:
            connection.enable_load_extension(True)
            connection.load_extension(str(binary))
        finally:
            connection.enable_load_extension(False)
        if connection.execute('SELECT vec_version()').fetchone()[0] != 'v0.1.6':
            raise DomainError('Loaded SQLite vector extension version differs from pin', 2)
        return connection
    except Exception:
        connection.close()
        raise


def _vector(values):
    if not isinstance(values, (list, tuple)) or not values or len(values) > 4096:
        raise DomainError('Embedding vector must have between 1 and 4096 dimensions')
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or
           not math.isfinite(value) for value in values):
        raise DomainError('Embedding vector must contain finite real values')
    norm = math.sqrt(math.fsum(value * value for value in values))
    if not math.isclose(norm, 1, abs_tol=1e-5):
        raise DomainError('Embedding vector must be nonzero and unit normalized')
    try:
        blob = struct.pack('<' + 'f' * len(values), *values)
    except (OverflowError, struct.error):
        raise DomainError('Embedding vector is not representable as float32') from None
    decoded = struct.unpack('<' + 'f' * len(values), blob)
    if not all(math.isfinite(value) for value in decoded):
        raise DomainError('Embedding vector is not finite float32')
    return blob


def _name(model, dimension):
    return 'search_vec_' + hashlib.sha256(f'{model}:{dimension}'.encode()).hexdigest()[:24]


def _rebuild(connection):
    connection.execute('CREATE VIRTUAL TABLE IF NOT EXISTS search_fts USING fts5(chunk_id UNINDEXED,text)')
    connection.execute('DELETE FROM search_fts')
    connection.execute("INSERT INTO search_fts SELECT id,text FROM document_chunks WHERE permission='PERMITTED'")
    names = connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'search_vec_%' AND sql LIKE '%USING vec0%'").fetchall()
    for (name,) in names:
        connection.execute(f'DROP TABLE "{name}"')
    models = connection.execute('SELECT DISTINCT model_id,dimension FROM embeddings').fetchall()
    for model, dimension in models:
        name = _name(model, dimension)
        connection.execute(f'CREATE VIRTUAL TABLE "{name}" USING vec0(chunk_id TEXT PRIMARY KEY,embedding FLOAT[{int(dimension)}] distance_metric=cosine)')
        for chunk_id, blob in connection.execute('''SELECT e.chunk_id,e.vector FROM embeddings e
                JOIN document_chunks c ON c.id=e.chunk_id
                WHERE e.model_id=? AND e.dimension=? AND c.permission='PERMITTED'
                    AND e.chunk_hash=c.content_hash ORDER BY e.chunk_id''', (model, dimension)):
            connection.execute(f'INSERT INTO "{name}" VALUES (?,?)', (chunk_id, blob))


def rebuild_index(path):
    """Explicit derived-index mutation leaves canonical passages/vectors unchanged."""
    connection = open_search_connection(path)
    try:
        with connection:
            _rebuild(connection)
        return {'status': 'AVAILABLE', 'canonical_changed': False}
    finally:
        connection.close()


def store_chunks(path, chunks, *, confirmed=False):
    prepared = []
    seen = set()
    for supplied in chunks:
        row = dict(supplied)
        if (row.get('document_kind') in PRIVATE_KINDS or
                row.get('source_kind') in PRIVATE_KINDS | {'BROKERAGE', 'PERSONAL_CONTRIBUTION'}):
            raise DomainError('Private broker or personal documents are excluded from corpus indexing', 3)
        if row.get('source_kind') is not None:
            raise DomainError('source_kind is unsupported; supply an explicit document_kind')
        if row.get('permission') != 'PERMITTED':
            # Retain only exclusion metadata; never denied text or embeddings.
            if row.get('permission') not in {'DENIED', 'UNKNOWN'}:
                raise DomainError('Corpus permission must be explicit')
            row.update(text='', content_hash=hashlib.sha256(b'').hexdigest(),
                       offset_start=0, offset_end=0)
            row.pop('vector', None)
        required = {'chunk_id', 'document_id', 'text', 'source_url', 'source_date',
                    'content_hash', 'offset_start', 'offset_end', 'license', 'data_environment'}
        if required - row.keys():
            raise DomainError('Permitted chunks require text, source, hash, offsets, license and environment')
        if row['data_environment'] not in {'REAL', 'SYNTHETIC'}:
            raise DomainError('Corpus source environment must be explicit')
        if (not row['license'] or not isinstance(row['text'], str) or
                row['permission'] == 'PERMITTED' and not row['text'].strip()):
            raise DomainError('Corpus text and independent source permission must be explicit')
        if len(row['text'].encode()) > 65536:
            raise DomainError('A corpus chunk must not exceed 64 KiB')
        locator = urlsplit(row['source_url'])
        if locator.scheme not in {'https', 'http'} or not locator.hostname or locator.username or locator.password:
            raise DomainError('Corpus source URLs must be public credential-free locators')
        row['source_url'] = safe_url(row['source_url'])
        try:
            date.fromisoformat(row['source_date'])
        except (ValueError, TypeError):
            raise DomainError('Corpus source dates must be ISO dates') from None
        digest = hashlib.sha256(row['text'].encode()).hexdigest()
        if digest != row['content_hash']:
            raise DomainError('Chunk content hash does not match text')
        if (not isinstance(row['offset_start'], int) or not isinstance(row['offset_end'], int)
                or row['offset_start'] < 0 or row['offset_end'] - row['offset_start'] != len(row['text'])):
            raise DomainError('Chunk character offsets must match its exact text')
        if row['chunk_id'] in seen:
            raise DomainError('Duplicate chunk identity')
        seen.add(row['chunk_id'])
        blob = _vector(row['vector']) if 'vector' in row else None
        if blob is not None and not row.get('model_id'):
            raise DomainError('Embedding model identity is required')
        prepared.append((row, digest, blob))
    if not confirmed:
        return {'status': 'PREVIEW', 'accepted_chunks': len(prepared), 'committed': False}
    connection = open_search_connection(path)
    try:
        with connection:
            for row, digest, blob in prepared:
                metadata = {key: value for key, value in row.items() if key in METADATA_FIELDS}
                values = (row['chunk_id'], row['document_id'], row.get('issuer_id'),
                          row['source_url'], row['source_date'], row.get('observed_at'),
                          row['permission'], digest, row['offset_start'], row['offset_end'],
                          row['text'], json.dumps(metadata, sort_keys=True))
                existing = connection.execute('SELECT * FROM document_chunks WHERE id=?',
                                              (row['chunk_id'],)).fetchone()
                if existing is not None and tuple(existing) != values:
                    raise DomainError('Canonical chunk is immutable; submit a separate revision', 3)
                if row.get('supersedes_chunk_id'):
                    original = connection.execute(
                        'SELECT document_id,issuer_id FROM document_chunks WHERE id=?',
                        (row['supersedes_chunk_id'],)).fetchone()
                    if original is None or tuple(original) != (row['document_id'], row.get('issuer_id')):
                        raise DomainError('Chunk revision references an incompatible original', 3)
                if existing is None:
                    connection.execute('INSERT INTO document_chunks VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', values)
                if blob is not None:
                    model = row['model_id']
                    dimension = len(row['vector'])
                    dimensions = {item[0] for item in connection.execute(
                        'SELECT DISTINCT dimension FROM embeddings WHERE model_id=?', (model,))}
                    if dimensions - {dimension}:
                        raise DomainError('Embedding model dimensions conflict', 3)
                    prior = connection.execute('SELECT dimension,vector,chunk_hash FROM embeddings WHERE chunk_id=? AND model_id=?',
                                               (row['chunk_id'], model)).fetchone()
                    if prior is not None and tuple(prior) != (dimension, blob, digest):
                        raise DomainError('Canonical embedding is immutable; use a new revision/model', 3)
                    if prior is None:
                        connection.execute('INSERT INTO embeddings VALUES (?,?,?,?,?)',
                                           (row['chunk_id'], model, dimension, blob, digest))
            _rebuild(connection)
        return {'status': 'AVAILABLE', 'accepted_chunks': len(prepared), 'committed': True}
    finally:
        connection.close()


def search(path, *, query='', top_k=10, issuer_id=None, date_from=None, date_to=None,
           vector=None, model_id=None):
    """Read-only cited retrieval; filter candidates before deterministic ranking."""
    if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 100:
        raise DomainError('Search top_k must be between one and 100')
    result = {'status': 'AVAILABLE', 'method': 'HYBRID' if vector is not None and query else
              'VECTOR' if vector is not None else 'FTS5', 'results': [], 'issues': [], 'external_calls': 0}

    def blocked(code, status='BLOCKED'):
        result.update(status=status, issues=[{'code': code, 'blocks_calculation': True,
                      'blocks_proposals': True, 'blocks_execution_review': True}])
        return result

    if not Path(path).exists():
        return blocked('CORPUS_UNAVAILABLE', 'UNAVAILABLE')
    connection = (open_search_connection(path, readonly=True) if vector is not None
                  else connect(path, readonly=True, initialize=False))
    try:
        result['coverage'] = {'excluded_permission_chunks': connection.execute(
            "SELECT count(*) FROM document_chunks WHERE permission!='PERMITTED'").fetchone()[0]}
        where, arguments = ["c.permission='PERMITTED'"], []
        if vector is not None:
            blob = _vector(vector)
            dimensions = {row[0] for row in connection.execute(
                'SELECT DISTINCT dimension FROM embeddings WHERE model_id=?', (model_id,))}
            if not dimensions:
                return blocked('EMBEDDING_MODEL_MISMATCH')
            if dimensions != {len(vector)}:
                return blocked('EMBEDDING_DIMENSION_MISMATCH')
            name = _name(model_id, len(vector))
            if not connection.execute('SELECT 1 FROM sqlite_master WHERE name=?', (name,)).fetchone():
                return blocked('VECTOR_INDEX_UNAVAILABLE', 'UNAVAILABLE')
            # Both lexical and vector ranking use the same compatible corpus.
            # A keyword hit cannot admit a different model or unembedded text.
            where.append('''EXISTS (SELECT 1 FROM embeddings e WHERE e.chunk_id=c.id
                AND e.model_id=? AND e.dimension=? AND e.chunk_hash=c.content_hash)''')
            arguments.extend((model_id, len(vector)))
        if issuer_id:
            where.append('c.issuer_id=?')
            arguments.append(issuer_id)
        for bound, operator in ((date_from, '>='), (date_to, '<=')):
            if bound:
                where.append(f'c.published_at {operator} ?')
                arguments.append(bound)
        candidates = connection.execute('SELECT c.* FROM document_chunks c WHERE ' +
                                        ' AND '.join(where) + ' ORDER BY c.id', arguments).fetchall()
        rows = {row[0]: row for row in candidates}
        term_scores = {}
        if query:
            terms = re.findall(r'\w+', query, flags=re.UNICODE)
            expression = ' OR '.join('"' + term.replace('"', '""') + '"' for term in terms)
            if expression:
                try:
                    term_scores = {chunk_id: -score for chunk_id, score in connection.execute(
                        'SELECT chunk_id,bm25(search_fts) FROM search_fts WHERE search_fts MATCH ?',
                        (expression,)) if chunk_id in rows}
                except Exception as error:
                    if 'no such table' in str(error):
                        return blocked('TEXT_INDEX_UNAVAILABLE', 'UNAVAILABLE')
                    raise
        vector_scores = {}
        if vector is not None:
            sql = f'''SELECT c.id,1-vec_distance_cosine(v.embedding,?) FROM "{name}" v
                JOIN document_chunks c ON c.id=v.chunk_id WHERE {' AND '.join(where)}'''
            vector_scores = dict(connection.execute(sql, [blob, *arguments]))
        identifiers = set(term_scores) | set(vector_scores)
        ranked = sorted(identifiers, key=lambda key: (
            -(vector_scores.get(key, 0) + term_scores.get(key, 0)), key))[:top_k]
        for chunk_id in ranked:
            row = rows[chunk_id]
            metadata = json.loads(row[11])
            result['results'].append({**metadata, 'chunk_id': chunk_id,
                'issuer_id': row[2], 'source_url': row[3], 'source_date': row[4],
                'permission': row[6], 'content_hash': row[7], 'offset_start': row[8],
                'offset_end': row[9], 'passage': row[10], 'model_id': model_id or metadata.get('model_id'),
                'term_score': term_scores.get(chunk_id, 0), 'cosine_score': vector_scores.get(chunk_id)})
        return result
    finally:
        connection.close()


def store_embeddings(path, chunk_ids, vectors, *, model_id, user_authorized=False):
    """Store reviewed adapter output only after explicit authorization."""
    if user_authorized is not True:
        raise DomainError('Embedding generation requires explicit user authorization', 3)
    if not model_id or len(chunk_ids) != len(vectors) or len(set(chunk_ids)) != len(chunk_ids):
        raise DomainError('Embedding output must match unique chunk IDs and explicit model')
    prepared = [(chunk_id, len(vector), _vector(vector))
                for chunk_id, vector in zip(chunk_ids, vectors, strict=True)]
    connection = open_search_connection(path)
    try:
        with connection:
            for chunk_id, dimension, blob in prepared:
                chunk = connection.execute('SELECT content_hash,permission FROM document_chunks WHERE id=?',
                                           (chunk_id,)).fetchone()
                if chunk is None or chunk[1] != 'PERMITTED':
                    raise DomainError('Embedding requires independently permitted canonical text', 3)
                dimensions = {row[0] for row in connection.execute(
                    'SELECT DISTINCT dimension FROM embeddings WHERE model_id=?', (model_id,))}
                if dimensions - {dimension}:
                    raise DomainError('Embedding model dimensions conflict', 3)
                previous = connection.execute('SELECT dimension,vector,chunk_hash FROM embeddings WHERE chunk_id=? AND model_id=?',
                                              (chunk_id, model_id)).fetchone()
                if previous is not None and tuple(previous) != (dimension, blob, chunk[0]):
                    raise DomainError('Canonical embedding is immutable', 3)
                if previous is None:
                    connection.execute('INSERT INTO embeddings VALUES (?,?,?,?,?)',
                                       (chunk_id, model_id, dimension, blob, chunk[0]))
            _rebuild(connection)
        return {'status': 'AVAILABLE', 'model_id': model_id, 'embedded_chunks': len(prepared)}
    finally:
        connection.close()
