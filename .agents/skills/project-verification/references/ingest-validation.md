# Ingest / Schema Validation

## SoT

- スキーマ: `infra/app/init.sql`
- Migration: `scripts/migrate_documents.py` / `make -C infra migrate`
- Seed: `scripts/seed.py`
- Langflow adapter: `scripts/run_langflow_ingest.py`, `scripts/import_langflow.py`

SearchService は Langflow Collection を直接読まない。

## 自動テスト

```bash
uv run pytest tests/test_ingest_lifecycle.py tests/test_documents_schema.py tests/test_chunk_ids.py tests/test_langflow_import.py
```

## 変更時チェック

- chunk スキーマ変更 → migration + schema テスト更新
- ingest ライフサイクル変更 → `test_ingest_lifecycle.py`
- MCP 経由 ingest **禁止**（`docs/current/features/api.md`）

## 関連 ADR

- ADR-0006（chunk schema）
- ADR-0007（document lifecycle）
- ADR-0008（host originals / Langflow API）
