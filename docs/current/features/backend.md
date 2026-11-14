---
type: Backend Capability
title: 検索バックエンド
description: pgvector上のプロトコル非依存検索、安定した順位によるoffsetページ取得、チャンク本文参照。
tags: [backend, pgvector, search, pagination]
status: stable
generated:
  at: "2026-11-14T11:36:15Z"
  by: process:codex-agent
---

# 検索バックエンド

## SearchService

場所: `src/knowledge_mcp/service.py`。MCPやUIから独立して次を担当する。

- `query`（空不可）、`top_k`（1〜20）、`offset`（0以上）をembedding生成前に検証する。
- OpenAI互換APIでクエリのembeddingを生成する。
- cosine距離（`<=>`）とチャンクUUIDで安定した順位を付ける。
- `top_k + 1`件を取得し、先頭`top_k`件と続きを示すpaginationを返す。
- チャンクIDから本文とメタデータを取得する。

戻り値は既存の`query` / `hits`と、`offset` / `page_size` / `has_more` / `next_offset`を持つ`pagination`。Toolの契約は[API](/current/features/api.md)を参照。

## ページ検索の方式と上限

`VectorRepository.search`は距離だけをMATERIALIZED CTEで計算し、`ORDER BY distance, id LIMIT ... OFFSET ...`でページを選んでから本文を読み込む。HNSW indexはDBに残すが、現行のページ検索はexact距離順位を使う。HNSWの既定探索候補数によって40件程度より深いページが途中終了する問題を避けるためである。

各ページでクエリembeddingとO(N)の距離計算が発生する。ローカル検証用の小規模ナレッジを対象とし、大規模データ向けの候補キャッシュや索引ベースのページ取得は実装していない。総件数・関連度閾値・総ページ数は導入しない。

順序の同点はUUIDで解消する。同時Ingest・削除中はページ間でデータが変化し得る。検索全体のスナップショットやサーバー側cursor storeは保持しない。

## データ投入

- スキーマは`infra/app/init.sql`の`documents`。1行は1チャンクで、システム検索インデックスの正本。
- 親文書は`document_id`、検索hitは行の`id`（chunk UUID）。`content_hash` / `ingested_at` / `embedding_model`も保持する。
- 既存volumeの列更新は`make -C infra migrate`。`init.sql`は初回のみ実行される。
- `scripts/seed.py`は1文書1チャンクのseed。未変更ならSkipする。
- LangflowはホストのFiles / Flow API経由でIngestし、adapterがCollectionから`documents`へ複製する。未変更はSkipし、変更時は親配下を置換する。SearchServiceはCollectionを直接読まない（[Ingest](/current/features/ingest.md)）。
- 文書単位削除は`scripts/delete_document.py`。親`document_id`配下のチャンクを削除する。
- 旧`chainlit_oauth_tokens`は既存データを保持する。Open WebUIの会話・OAuth状態は別の`open_webui_data`に置き、このテーブルを利用しない。

データ構成の判断は[ADR-0006](/decisions/ADR-0006-documents-chunk-schema.md)、更新単位は[ADR-0007](/decisions/ADR-0007-document-lifecycle.md)、ホスト原本は[ADR-0008](/decisions/ADR-0008-host-originals-langflow-api.md)を参照。

## エラーと観測

MCP Tool境界は入力エラー、embeddingやDBの障害、文書未検出を`error`として返す。Appは検索失敗と空結果を区別する。`search.embed`、`search.query`、`get_document.fetch`とDB spanは[トレーシング](/current/features/tracing.md)の規則で記録する。
