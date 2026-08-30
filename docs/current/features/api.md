---
type: API Contract
title: MCP ツール契約
description: ベクトル検索と文書取得の FastMCP ツール。
tags: [mcp, api]
status: stable
---

# MCP ツール契約

トランスポート: **Streamable HTTP**、stateless、パス `/mcp`。Compose 上では Keycloak JWT（`aud=http://localhost:8000/mcp`、scope `mcp-tools`、role `mcp-reader`）が必要（[ADR-0012](/decisions/ADR-0012-mcp-gateway-resource-server.md)）。Inspector は `scripts/mcp_dev_token.py` で Bearer を発行する。

## Gateway HTTP

Chainlit は `MCP_GATEWAY_URL` へ次を呼ぶ（Bearer は `aud=mcp-gateway` の Chainlit トークン）。

| メソッド | パス | 用途 |
|---|---|---|
| GET | `/v1/mcp` | enabled かつ JWT の `realm_access.roles` が `required_roles` を満たす `{id, name, tools}`。Registry のみ。下流 MCP は呼ばない |
| GET | `/v1/mcp/{server_id}/tools` | そのサーバーの tool schema（`allowed_tools` でフィルタ） |
| POST | `/v1/mcp/{server_id}/tools/{name}:call` | ツール実行 |

## ツール

### `search_knowledge`

| フィールド | 型 | 備考 |
|---|---|---|
| `query` | string | 必須、空不可 |
| `top_k` | integer | 既定 5、最小 1、最大 20 |

`document_id`、`title`、`excerpt`、`source`、`similarity` を含むヒットを返します。`document_id` はヒットした chunk 行の UUID です。

Langfuse では Chainlit 側の `chat.turn` 配下に tool observation として **input** `{"query": "...", "top_k": N}` と **output**（ヒット一覧）がネスト記録されます。MCP サーバー側は FastMCP の server span（分散トレース）に同じ input / output が付与されます。

### `get_document`

| フィールド | 型 | 備考 |
|---|---|---|
| `document_id` | string | 検索結果の chunk 行 UUID |

ヒット行の `content`（chunk 本文）を返すか、見つからない場合はエラーを返します。親文書の全文結合はしません。

Langfuse では Chainlit 側の `chat.turn` 配下に tool observation として **input** `{"document_id": "..."}` と **output**（文書メタデータと chunk 本文の先頭 500 文字）がネスト記録されます。MCP サーバー側は FastMCP の server span に同じ input / output が付与されます。

## MCP では公開しないもの

- 文書 ingest（`scripts/seed.py`、`scripts/run_langflow_ingest.py`、`scripts/import_langflow.py` を使用）
- 文書削除（`scripts/delete_document.py`。親 `document_id` 単位）
- Resource と Prompt

