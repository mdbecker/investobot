"""CLI corpus retrieval and explicit derived-index rebuilding use real SQLite."""

import hashlib
import json

import pytest
from typer.testing import CliRunner

from invest.cli import app
from invest.db import connect
from invest.ledger import Ledger
from invest.search import store_chunks


@pytest.fixture
def context(tmp_path, monkeypatch):
    path = tmp_path / 'corpus.db'
    monkeypatch.setenv('INVEST_DB', str(path))
    return path, CliRunner()


def invoke(context, args):
    result = context[1].invoke(app, args)
    assert result.exit_code == 0, result.stderr
    return json.loads(result.stdout)


def financial_state(path):
    selected = Ledger(path)
    try:
        return selected.planning_state()
    finally:
        selected.connection.close()


def corpus_state(path):
    connection = connect(path, readonly=True, initialize=False)
    try:
        return {table: connection.execute(f'SELECT * FROM {table} ORDER BY 1').fetchall()
                for table in ('document_chunks', 'embeddings')}
    finally:
        connection.close()


def accepted_corpus(context):
    path = context[0]
    selected = Ledger(path)
    try:
        selected.register_security({'ticker': 'FICT', 'name': 'Fictional Issuer',
                                   'asset_type': 'STOCK', 'currency': 'USD',
                                   'source': 'Reviewed fictional identity record'})
    finally:
        selected.connection.close()
    text = 'Fictional permitted issuer reports a new facility.'
    chunk = {'chunk_id': 'fictional-chunk', 'document_id': 'fictional-document',
             'text': text, 'source_url': 'https://fictional-issuer.example/release',
             'source_date': '2026-10-10', 'permission': 'PERMITTED',
             'content_hash': hashlib.sha256(text.encode()).hexdigest(),
             'offset_start': 0, 'offset_end': len(text),
             'license': 'Independently reviewed fictional permission',
             'data_environment': 'SYNTHETIC', 'document_kind': 'ISSUER_RELEASE'}
    store_chunks(path, [chunk], confirmed=True)
    return chunk


def test_search_lexical_citation_and_unknown_embedding_model_preserve_finances(context):
    chunk = accepted_corpus(context)
    before = financial_state(context[0]), corpus_state(context[0])
    result = invoke(context, ['research', 'search', '--query', 'fictional', '--top-k', '3'])
    assert result['status'] == 'AVAILABLE'
    assert result['method'] == 'FTS5'
    assert result['external_calls'] == 0
    assert len(result['results']) == 1
    hit = result['results'][0]
    for field in ('chunk_id', 'source_url', 'source_date', 'permission', 'content_hash',
                  'offset_start', 'offset_end'):
        assert hit[field] == chunk[field]
    assert hit['passage'] == chunk['text']
    assert hit['model_id'] is None
    assert hit['cosine_score'] is None
    assert (financial_state(context[0]), corpus_state(context[0])) == before


def test_absent_corpus_search_and_index_preview_never_create_selected_ledger(context):
    assert not context[0].exists()
    result = invoke(context, ['research', 'search', '--query', 'fictional', '--top-k', '3'])
    assert result['status'] == 'UNAVAILABLE'
    assert result['results'] == []
    assert result['issues'][0]['code'] == 'CORPUS_UNAVAILABLE'
    preview = invoke(context, ['research', 'index'])
    assert preview['status'] == 'PREVIEW'
    assert preview['committed'] is False
    assert preview['canonical_changed'] is False
    assert not context[0].exists()


def test_derived_index_rebuild_requires_confirmation_and_preserves_canonical_rows(context):
    accepted_corpus(context)
    before = financial_state(context[0]), corpus_state(context[0])
    preview = invoke(context, ['research', 'index'])
    assert preview['status'] == 'PREVIEW'
    assert preview['committed'] is False
    assert (financial_state(context[0]), corpus_state(context[0])) == before
    result = invoke(context, ['research', 'index', '--confirm'])
    assert result['status'] == 'AVAILABLE'
    assert result['committed'] is True
    assert result['canonical_changed'] is False
    assert (financial_state(context[0]), corpus_state(context[0])) == before
    assert invoke(context, ['research', 'search', '--query', 'fictional', '--top-k', '3'])['results']


def test_search_and_derived_index_contracts_are_discoverable(context):
    for tool, scope in [('research.search', 'read'), ('research.index', 'derived_index')]:
        descriptor = invoke(context, ['tools', 'describe', tool])
        assert descriptor['name'] == tool
        assert descriptor['mutation_scope'] == scope
    assert not context[0].exists()
