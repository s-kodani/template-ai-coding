---
type: API Contract
title: MCP ツール契約
description: ベクトル検索と文書取得の FastMCP ツール。
tags: [mcp, api]
status: stable
---

# MCP ツール契約

トランスポート: **Streamable HTTP**、stateless、パス `/mcp`。

## ツール

### `search_knowledge`

| フィールド | 型 | 備考 |
|---|---|---|
| `query` | string | 必須、空不可 |
| `top_k` | integer | 既定 5、最小 1、最大 20 |

`document_id`、`title`、`excerpt`、`source`、`similarity` を含むヒットを返します。

Langfuse では Chainlit 側の `chat.turn` 配下に tool observation として **input** `{"query": "...", "top_k": N}` がネスト記録されます。MCP サーバー側は FastMCP の server span（分散トレース）に同じ input が付与されます。

### `get_document`

| フィールド | 型 | 備考 |
|---|---|---|
| `document_id` | string | 検索結果の UUID |

全文 `content` を返すか、見つからない場合はエラーを返します。

Langfuse では Chainlit 側の `chat.turn` 配下に tool observation として **input** `{"document_id": "..."}` がネスト記録されます。MCP サーバー側は FastMCP の server span に同じ input が付与されます。

## MCP では公開しないもの

- 文書 ingest（`scripts/seed.py` を使用）
- Resource と Prompt
