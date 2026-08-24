CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL,
    chunk_index INTEGER NOT NULL DEFAULT 0,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT,
    metadata JSONB NOT NULL DEFAULT '{}',
    content_hash TEXT,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    embedding_model TEXT,
    embedding vector(1536),
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS documents_embedding_hnsw_idx
    ON documents USING hnsw (embedding vector_cosine_ops);
