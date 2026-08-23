CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

ALTER TABLE documents ADD COLUMN IF NOT EXISTS document_id UUID;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS chunk_index INTEGER NOT NULL DEFAULT 0;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}';

UPDATE documents
SET document_id = uuid_generate_v5('6ba7b811-9dad-11d1-80b4-00c04fd430c8'::uuid, source)
WHERE document_id IS NULL
  AND source IS NOT NULL
  AND btrim(source) <> '';

UPDATE documents
SET document_id = id
WHERE document_id IS NULL;

ALTER TABLE documents ALTER COLUMN document_id SET NOT NULL;

ALTER TABLE documents DROP CONSTRAINT IF EXISTS documents_source_key;

CREATE UNIQUE INDEX IF NOT EXISTS documents_document_id_chunk_index_key
    ON documents (document_id, chunk_index);

ALTER TABLE documents ADD COLUMN IF NOT EXISTS content_hash TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS ingested_at TIMESTAMPTZ NOT NULL DEFAULT now();
ALTER TABLE documents ADD COLUMN IF NOT EXISTS embedding_model TEXT;

UPDATE documents
SET content_hash = encode(sha256(convert_to(content, 'UTF8')), 'hex')
WHERE content_hash IS NULL;

UPDATE documents
SET embedding_model = 'text-embedding-3-small'
WHERE embedding_model IS NULL;
