# Local research search

Search indexes independently permitted public or accepted research passages. It
retains citation URLs/dates, exact text hashes, character offsets, licenses and
revision provenance. Denied sources retain exclusion metadata with empty text and
no embeddings; their passages are excluded. Private broker HTML and named
personal-contribution documents are rejected before any write. Permission and
source truth require human review: an agent's assertion is not independent rights
approval. Chunks never alter financial state.

Canonical passages and embeddings are immutable SQLite rows. Changed text needs a
new chunk ID and an explicit `supersedes_chunk_id`; changed embedding models retain
the original vectors. Vectors are finite, nonzero, unit-normalized float32 values
with an explicit model and dimension. Conflicting repeat writes fail atomically.
Preview validates inputs without creating a selected ledger.

FTS5 provides offline keyword retrieval. Compatible vectors add cosine similarity
through the pinned sqlite-vec extension baked into Docker. Issuer/date constraints
select eligible candidates before final ranking; equal scores sort by chunk ID.
The hybrid score is lexical BM25 plus cosine similarity, a retrieval aid rather
than investment quality. Results retain both score components and citation data.

FTS5 and vector tables are derived, explicitly rebuildable indexes. Rebuilding
reads canonical text/vector rows without changing them. A missing vector index
returns `VECTOR_INDEX_UNAVAILABLE`; keyword search remains usable. Unknown models
or incompatible dimensions are explicit blocked outcomes, never silent model
substitution. Search itself opens the existing ledger read-only and makes no
network calls or automatic repairs.

Embedding generation requires explicit user authorization before invoking an
adapter. Reviewed adapter output can be stored through `store_embeddings` after
permission/model/dimension checks. No provider is contacted automatically and no
broker or personal document is automatically embedded. The Docker extension is
loaded from the installed pinned package; there are no runtime downloads.
