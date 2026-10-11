"""Explicit authorized adapter boundary; never embeds financial or personal pages implicitly."""

import json

from invest.db import connect
from invest.models import DomainError


def generate(search_module, path, chunk_ids, *, model_id, adapter, user_authorized=False):
    if user_authorized is not True:
        raise DomainError('Embedding adapter invocation requires explicit authorization', 3)
    if not model_id or not callable(adapter) or not chunk_ids or len(set(chunk_ids)) != len(chunk_ids):
        raise DomainError('Supply an explicit model, adapter and unique chunk IDs')
    connection = connect(path, readonly=True)
    texts = []
    try:
        for identity in chunk_ids:
            row = connection.execute(
                'SELECT text,permission,source_metadata_json FROM document_chunks WHERE id=?',
                (identity,)).fetchone()
            if row is None or row[1] != 'PERMITTED':
                raise DomainError('Embedding requires independently permitted canonical text', 3)
            metadata = json.loads(row[2])
            if (metadata.get('document_kind') or metadata.get('source_kind')) in {'BROKERAGE', 'PERSONAL_CONTRIBUTION'}:
                raise DomainError('Personal and brokerage text requires separately reviewed indexing rights', 3)
            texts.append(row[0])
    finally:
        connection.close()
    vectors = adapter(texts)
    return search_module.store_embeddings(path, chunk_ids, vectors, model_id=model_id,
                                          user_authorized=True)
