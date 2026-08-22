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

- スキーマ: `infra/app/init.sql`
- シード: `scripts/seed.py`（fixture 文書。MCP ingest ではない）

## エラー

MCP ツール境界では、API キー未設定、空インデックス、DB 到達不能などに対し、短く actionable なメッセージを返します（汎用 500 は返しません）。
