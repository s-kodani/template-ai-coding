from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INIT_SQL = (ROOT / "infra" / "app" / "init.sql").read_text(encoding="utf-8")
MIGRATE_SQL = (ROOT / "infra" / "app" / "migrate_documents_chunks.sql").read_text(encoding="utf-8")
MAKEFILE = (ROOT / "infra" / "Makefile").read_text(encoding="utf-8")
LANGFLOW_COMPOSE = (ROOT / "infra" / "langflow" / "compose.yml").read_text(encoding="utf-8")
SEED_PY = (ROOT / "scripts" / "seed.py").read_text(encoding="utf-8")
IMPORT_PY = (ROOT / "scripts" / "import_langflow.py").read_text(encoding="utf-8")
DELETE_PY = (ROOT / "scripts" / "delete_document.py").read_text(encoding="utf-8")


def test_init_sql_defines_chunk_columns_and_parent_unique() -> None:
    assert "document_id UUID NOT NULL" in INIT_SQL
    assert "chunk_index INTEGER NOT NULL DEFAULT 0" in INIT_SQL
    assert "metadata JSONB NOT NULL DEFAULT '{}'" in INIT_SQL
    assert "content_hash TEXT" in INIT_SQL
    assert "ingested_at TIMESTAMPTZ NOT NULL DEFAULT now()" in INIT_SQL
    assert "embedding_model TEXT" in INIT_SQL
    assert "UNIQUE (document_id, chunk_index)" in INIT_SQL
    assert "source TEXT UNIQUE" not in INIT_SQL


def test_migrate_sql_backfills_parent_id_and_drops_source_unique() -> None:
    assert "ADD COLUMN IF NOT EXISTS document_id UUID" in MIGRATE_SQL
    assert "ADD COLUMN IF NOT EXISTS chunk_index" in MIGRATE_SQL
    assert "ADD COLUMN IF NOT EXISTS metadata JSONB" in MIGRATE_SQL
    assert "ADD COLUMN IF NOT EXISTS content_hash TEXT" in MIGRATE_SQL
    assert "ADD COLUMN IF NOT EXISTS ingested_at TIMESTAMPTZ" in MIGRATE_SQL
    assert "ADD COLUMN IF NOT EXISTS embedding_model TEXT" in MIGRATE_SQL
    assert "uuid_generate_v5('6ba7b811-9dad-11d1-80b4-00c04fd430c8'" in MIGRATE_SQL
    assert "DROP CONSTRAINT IF EXISTS documents_source_key" in MIGRATE_SQL
    assert "documents_document_id_chunk_index_key" in MIGRATE_SQL
    assert "encode(sha256(convert_to(content, 'UTF8')), 'hex')" in MIGRATE_SQL


def test_makefile_exposes_migrate_and_langflow_import() -> None:
    assert "migrate:" in MAKEFILE
    assert "import-langflow:" in MAKEFILE
    assert "seed: migrate" in MAKEFILE
    assert "delete-document:" in MAKEFILE
    assert "scripts/delete_document.py" in MAKEFILE


def test_langflow_postgres_is_published_on_5434() -> None:
    assert "5434:5432" in LANGFLOW_COMPOSE


def test_seed_and_import_use_document_lifecycle() -> None:
    assert "fingerprint_matches" in SEED_PY
    assert "replace_document" in SEED_PY
    assert "sync_document" in IMPORT_PY
    assert "upsert_document(" not in SEED_PY
    assert "upsert_document(" not in IMPORT_PY
    assert "delete_document" in DELETE_PY
