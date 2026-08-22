---
type: Architecture
title: アーキテクチャ
description: FastMCP、Chainlit、pgvector、Langfuse のトレース構成。
tags: [architecture, mcp, tracing]
status: stable
---

# アーキテクチャ

## コンポーネント

| コンポーネント | 役割 |
|---|---|
| Chainlit（`src/chat_ui/`） | チャット UI、Langfuse ルートスパン、FastMCP クライアント |
| FastMCP サーバー（`src/knowledge_mcp/`） | Streamable HTTP MCP、検索ツール、子スパン |
| PostgreSQL + pgvector | アプリ用ベクトルストア（Langfuse DB とは分離） |
| Langfuse（公式 compose） | トレース取り込みと UI |
| MCP Inspector | FastMCP へのプロトコル検証 |

## アーキテクチャ図

```mermaid
flowchart TB
    subgraph users["利用者・検証"]
        User([ユーザー])
        Inspector[MCP Inspector]
    end

    subgraph app["アプリスタック（infra/app）"]
        Chainlit["Chainlit<br/>src/chat_ui/"]
        MCP["FastMCP Server<br/>src/knowledge_mcp/"]
        PG[("PostgreSQL 17<br/>pgvector")]
    end

    subgraph external["外部 API"]
        LLM["OpenAI 互換 API<br/>（chat / embeddings）"]
    end

    subgraph observability["オブザーバビリティ（infra/langfuse）"]
        Langfuse["Langfuse<br/>UI + trace ingest"]
    end

    User -->|HTTP :8080| Chainlit
    Inspector -->|"Streamable HTTP :8000/mcp"| MCP
    Chainlit -->|"Streamable HTTP /mcp"| MCP
    Chainlit -->|chat completions| LLM
    MCP -->|vector search / get| PG
    MCP -->|embeddings| LLM
    Chainlit -->|OTLP / Langfuse SDK| Langfuse
    MCP -->|OTLP / Langfuse SDK| Langfuse
```

## レイヤ構成（MCP サーバー）

```text
HTTP トランスポート（Streamable HTTP、Origin 検証）
  -> MCP ツール（search_knowledge, get_document）
    -> SearchService
      -> EmbeddingClient（OpenAI 互換 API）
      -> VectorRepository（asyncpg + pgvector）
```

## トレース伝播

```mermaid
flowchart TD
    chat["chat.turn<br/>（Chainlit ルート）"]
    llm["llm.generate"]
    tool["search_knowledge / get_document<br/>（Langfuse tool observation）"]
    client["FastMCP Client span"]
    server["FastMCP Server span<br/>（_meta traceparent から接続）"]
    embed["search.embed<br/>（OTel span）"]
    query["search.query<br/>（OTel span）"]
    db["asyncpg spans<br/>（Postgres クエリ）"]

    chat --> llm
    chat --> tool
    tool --> client
    client -->|"W3C traceparent in MCP _meta"| server
    server --> embed
    server --> query
    query --> db
```

- Chainlit が `chat.turn` と `llm.generate` 観測を作成
- FastMCP Client が W3C トレースコンテキストを MCP `_meta` に注入（native telemetry）
- FastMCP Server が `_meta` を extract し SERVER スパンを子として接続
- カスタム OTel スパン: `search.embed`、`search.query`（MCP server span の子。Langfuse 独立トレースにはしない）
- Postgres クライアントスパンは `opentelemetry-instrumentation-asyncpg`

compose 構成は [インフラ](/current/infrastructure.md) を参照。
