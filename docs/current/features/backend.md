---
type: Backend Capability
title: 検索バックエンド
description: pgvector 上のプロトコル非依存ベクトル検索サービス。
tags: [backend, pgvector, search]
status: stable
---

# 検索バックエンド

## SearchService

場所: `src/knowledge_mcp/service.py`

責務:

- `query` と `top_k`（1–20）の検証
- OpenAI 互換 API によるクエリの embedding
- cosine 距離（`<=>`）と HNSW インデックスによる pgvector 検索
- 類似度、タイトル、抜粋、出典、document id を含む構造化ヒットの返却

## データ投入

- スキーマ: `infra/app/init.sql`（`documents`。1 行 = 1 chunk。システム検索インデックスの SoT）
- 行の識別: `document_id` が親、`id` が chunk_id（MCP ヒット行 UUID）。加えて `content_hash` / `ingested_at` / `embedding_model`
- 既存 volume: `make -C infra migrate`（`init.sql` は初回のみ）
- シード: `scripts/seed.py`（1 文書 = 1 chunk。未変更なら Skip。MCP ingest ではない）
- Langflow: `scripts/run_langflow_ingest.py` がホスト原本を Files / Flow API で投入し、`scripts/import_langflow.py` が Collection を `documents` へ載せる。未変更なら Skip、変更時は親配下を削除して再投入。SearchService は Collection を読まない（[Ingest](/current/features/ingest.md)、[ADR-0006](/decisions/ADR-0006-documents-chunk-schema.md)、[ADR-0007](/decisions/ADR-0007-document-lifecycle.md)、[ADR-0008](/decisions/ADR-0008-host-originals-langflow-api.md)）
- 文書単位削除: `scripts/delete_document.py`（親 `document_id` 配下の全 chunk）

## エラー

MCP ツール境界では、API キー未設定、空インデックス、DB 到達不能などに対し、短く actionable なメッセージを返します（汎用 500 は返しません）。
