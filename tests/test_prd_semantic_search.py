"""Hybrid retrieval must stay within one explicitly selected embedding model."""

import hashlib
import json

import pytest
from typer.testing import CliRunner

from invest.cli import app
from invest.contracts import tools_describe
from invest.ledger import Ledger
from invest.search import search, store_chunks, store_embeddings


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    path = tmp_path / 'fictional-corpus.db'
    monkeypatch.setenv('INVEST_DB', str(path))
    ledger = Ledger(path)
    financial = ledger.planning_state()
    ledger.connection.close()
    chunks = []
    for identity in ['model-a', 'model-b', 'text-only']:
        text = f'Fictional factory evidence from {identity}.'
        chunks.append({'chunk_id': identity, 'document_id': identity, 'text': text,
            'source_url': 'https://example.invalid/' + identity, 'source_date': '2026-10-10',
            'permission': 'PERMITTED', 'content_hash': hashlib.sha256(text.encode()).hexdigest(),
            'offset_start': 0, 'offset_end': len(text), 'license': 'Reviewed fictional public reuse',
            'data_environment': 'SYNTHETIC'})
    store_chunks(path, chunks, confirmed=True)
    store_embeddings(path, ['model-a'], [[1.0, 0.0]], model_id='fictional-model-a', user_authorized=True)
    store_embeddings(path, ['model-b'], [[1.0, 0.0]], model_id='fictional-model-b', user_authorized=True)
    file = tmp_path / 'explicit-query-vector.json'
    file.write_text(json.dumps([1.0, 0.0]))
    yield {'path': path, 'file': file, 'financial': financial}
    ledger = Ledger(path)
    try:
        assert ledger.planning_state() == financial
    finally:
        ledger.connection.close()


def test_hybrid_keyword_union_excludes_other_model_and_unembedded_chunks(corpus):
    result = search(corpus['path'], query='factory', vector=[1.0, 0.0], model_id='fictional-model-a')
    assert result['status'] == 'AVAILABLE'
    assert result['method'] == 'HYBRID'
    assert [hit['chunk_id'] for hit in result['results']] == ['model-a']
    assert all(hit['model_id'] == 'fictional-model-a' for hit in result['results'])


def test_explicit_text_fallback_retains_all_authorized_model_agnostic_chunks(corpus):
    result = search(corpus['path'], query='factory')
    assert result['status'] == 'AVAILABLE'
    assert result['method'] == 'FTS5'
    assert {hit['chunk_id'] for hit in result['results']} == {'model-a', 'model-b', 'text-only'}


def test_semantic_cli_reads_explicit_vector_and_matches_compatible_domain(corpus):
    result = CliRunner().invoke(app, ['research', 'search', '--query', 'factory', '--semantic',
        '--embedding-file', str(corpus['file']), '--model-id', 'fictional-model-a'])
    assert result.exit_code == 0, result.output
    actual = json.loads(result.stdout)
    expected = search(corpus['path'], query='factory', vector=[1.0, 0.0], model_id='fictional-model-a')
    assert actual == expected
    assert [hit['chunk_id'] for hit in actual['results']] == ['model-a']
    assert actual['external_calls'] == 0


@pytest.mark.parametrize('mismatch', ['model', 'dimension'])
def test_semantic_cli_mismatch_returns_typed_empty_outcome(corpus, mismatch):
    model = 'fictional-model-a'
    if mismatch == 'model':
        model = 'fictional-model-unknown'
    else:
        corpus['file'].write_text(json.dumps([1.0, 0.0, 0.0]))
    result = CliRunner().invoke(app, ['research', 'search', '--query', 'factory', '--semantic',
        '--embedding-file', str(corpus['file']), '--model-id', model])
    assert result.exit_code == 0, result.output
    actual = json.loads(result.stdout)
    assert actual['status'] == 'BLOCKED'
    assert actual['results'] == []
    assert actual['issues'][0]['code'] == ('EMBEDDING_MODEL_MISMATCH' if mismatch == 'model'
                                         else 'EMBEDDING_DIMENSION_MISMATCH')
    assert actual['external_calls'] == 0


def test_semantic_search_discovery_exposes_explicit_model_vector_flags():
    contract = tools_describe('research.search')
    parameters = {item['name']: item for item in contract['parameters']}
    for name, flag in [('semantic', '--semantic'), ('embedding_file', '--embedding-file'),
                       ('model_id', '--model-id')]:
        assert name in parameters, f'Missing semantic retrieval parameter {name}'
        assert flag in parameters[name]['flags']
    assert contract['input_schema']['properties']['semantic']['type'] == 'boolean'
    assert contract['mutation_scope'] == 'read'
