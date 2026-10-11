"""Verified future migrations preserve canonical corpus despite derived vec0 tables."""

import hashlib

from invest.backup import create, verify
from invest.ledger import Ledger
from invest.migrations import migrate
from invest.search import open_search_connection, store_chunks


def test_verified_future_migration_with_vector_index_preserves_canonical_corpus(tmp_path):
    path = tmp_path / 'fictional-vector-migration.db'
    ledger = Ledger(path)
    ledger.connection.close()
    text = 'Fictional permitted issuer disclosure for vector migration recovery.'
    digest = hashlib.sha256(text.encode()).hexdigest()
    result = store_chunks(path, [{
        'chunk_id': 'fictional-chunk', 'document_id': 'fictional-document',
        'issuer_id': 'fictional-issuer', 'text': text,
        'source_url': 'https://example.invalid/fictional-disclosure', 'source_date': '2026-10-10',
        'permission': 'PERMITTED', 'license': 'Reviewed fictional source indexing rights',
        'content_hash': digest, 'offset_start': 0, 'offset_end': len(text),
        'data_environment': 'SYNTHETIC', 'model_id': 'fictional-normalized-2d', 'vector': [1.0, 0.0],
    }], confirmed=True)
    assert result['status'] == 'AVAILABLE'
    connection = open_search_connection(path)
    try:
        before_chunks = connection.execute('SELECT * FROM document_chunks ORDER BY id').fetchall()
        before_vectors = connection.execute('SELECT * FROM embeddings ORDER BY chunk_id,model_id').fetchall()
        assert before_vectors
        assert connection.execute("SELECT count(*) FROM sqlite_master WHERE sql LIKE '%USING vec0%'").fetchone()[0] == 1
        before_history = connection.execute('SELECT id,checksum FROM schema_migrations ORDER BY id').fetchall()
    finally:
        connection.close()
    archive = tmp_path / 'verified-vector-backup.tar.gz'
    backed_up = create(path, archive)
    assert backed_up['status'] == 'AVAILABLE', backed_up
    assert verify(archive)['status'] == 'AVAILABLE'
    sql = 'CREATE TABLE fictional_migration_probe (id TEXT PRIMARY KEY, value TEXT NOT NULL);'
    checksum = hashlib.sha256(sql.encode()).hexdigest()
    migrated = migrate(path, [{'id': '002-vector-fixture', 'sql': sql, 'checksum': checksum,
                              'destructive': False}])
    assert migrated['status'] == 'AVAILABLE', migrated
    assert migrated['applied_migrations'] == ['002-vector-fixture']
    connection = open_search_connection(path)
    try:
        assert connection.execute('PRAGMA integrity_check').fetchall() == [('ok',)]
        assert connection.execute('PRAGMA foreign_key_check').fetchall() == []
        assert connection.execute('SELECT * FROM document_chunks ORDER BY id').fetchall() == before_chunks
        assert connection.execute('SELECT * FROM embeddings ORDER BY chunk_id,model_id').fetchall() == before_vectors
        assert connection.execute('SELECT id,checksum FROM schema_migrations ORDER BY id').fetchall() == [
            *before_history, ('002-vector-fixture', checksum)]
        assert connection.execute('SELECT count(*) FROM fictional_migration_probe').fetchone()[0] == 0
    finally:
        connection.close()
