---
type: Decision Record
title: "ADR-0005: Langflow を Ingest 用サイドカーにする"
description: Langflow は任意の Ingest パイプライン。Retrieval は Chainlit + FastMCP。システムインデックスは documents。
tags: [decision, langflow, ingest, architecture]
status: stable
decision_status: accepted
---

# ADR-0005: Langflow を Ingest 用サイドカーにする

## 背景

ファイルアップロードからの文書投入を検証したい。現行 ingest は `scripts/seed.py` のみで、MCP ツールは read-only である。

Langflow の `PGVector` コンポーネントは LangChain Collection スキーマへ書き込む。SearchService は独自の `documents` テーブルを読む。両者を同一インデックスとしてつなぐと、スキーマ衝突と Langflow バージョン依存が生じる。

## 決定

1. Langflow は **任意サイドカー** とする。`make -C infra up` には含めない。
2. システムの Retrieval / Chat は **Chainlit + FastMCP** のままとする。Langflow 上の Similarity Search は Ingest 評価専用。
3. システム検索インデックスの Source of Truth は **`documents` テーブル** とする。LangChain / Langflow Collection はシステムインデックスにしない。
4. Phase 1（本実装）では Langflow 専用 Postgres にメタデータと PoC 用 Vector Store を置き、`app-postgres` には接続しない。
5. SearchService へつなぐ場合は `documents` を Chunk 対応へ進化させ、Langflow ネイティブ Collection を直読みしない。実装は [ADR-0006](/decisions/ADR-0006-documents-chunk-schema.md)。

## 検討した代替

- Langflow `PGVector` を `documents` へ直接書き込む — コンポーネントが LangChain スキーマを前提とするため不採用
- SearchService を LangChain Collection 直読みにする — Langflow アップグレードで壊れやすいため不採用
- Langflow をシステムの Chat UI にする — [ADR-0003](/decisions/ADR-0003-chainlit-traced-client.md) のトレース付き検証経路と二重化するため不採用

## 結果

- 既存の FastMCP / Chainlit / Langfuse 検証を壊さずに Ingest パイプラインを試せる
- Embedding モデルは現行どおり `text-embedding-3-small` / 1536 次元（[ADR-0002](/decisions/ADR-0002-postgres-pgvector.md)）
- MCP ingest ツールは追加しない
