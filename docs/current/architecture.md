---
type: Architecture
title: アーキテクチャ
description: FastMCP、Chainlit、pgvector、Langfuse のトレース構成と、ホスト原本から Langflow API 経由で documents へ載せる Ingest。
tags: [architecture, mcp, tracing, langflow]
status: stable
---

# アーキテクチャ

## コンポーネント

| コンポーネント | 役割 |
|---|---|
| Chainlit（`src/chat_ui/`） | チャット UI、Langfuse ルートスパン、既定 FastMCP クライアント、追加 MCP 接続 UI |
| FastMCP サーバー（`src/knowledge_mcp/`） | Streamable HTTP MCP、検索ツール、子スパン |
| PostgreSQL + pgvector | アプリ用ベクトルストア（Langfuse DB・Langflow DB とは分離） |
| Langfuse（公式 compose） | トレース取り込みと UI |
| Langflow（任意サイドカー） | ファイル Ingest。専用 DB へ書き、ホスト adapter が `documents` へ複製する |
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

    subgraph optional["任意"]
        ExtraMCP[追加 MCP サーバ]
        Langflow["Langflow<br/>infra/langflow/"]
        LFPG[("Langflow Postgres<br/>metadata + Collection")]
        Adapter["run_langflow_ingest.py\nimport_langflow.py"]
    end

    User -->|HTTP :8080| Chainlit
    User -->|HTTP :7860| Langflow
    User -->|"host files (data/ingest)"| Adapter
    Adapter -->|"Files API + Flow API"| Langflow
    Langflow --> LFPG
    Langflow -->|embeddings| LLM
    Adapter -->|read Collection| LFPG
    Adapter -->|lifecycle sync| PG
    User -->|"MCP 接続 UI（HTTP/SSE）"| Chainlit
    Inspector -->|"Streamable HTTP :8000/mcp"| MCP
    Chainlit -->|"Streamable HTTP /mcp（既定）"| MCP
    Chainlit -->|追加 MCP tools/call + _meta| ExtraMCP
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
    client -->|"W3C traceparent + baggage in MCP _meta"| server
    server --> embed
    server --> query
    query --> db
```

- Chainlit が `chat.turn` と `llm.generate` 観測を作成
- 既定の knowledge-mcp 呼び出しは FastMCP Client の native telemetry で `_meta` に W3C トレースコンテキストを注入する。Langfuse 向けに `baggage`（`langfuse_trace_id`）も載せる
- UI から接続した追加 MCP は公式 SDK の `ClientSession.call_tool(..., meta=...)` で同じ `_meta` を注入
- FastMCP Server が `_meta` を extract し SERVER スパンを子として接続する。baggage により Langfuse はこれらのスパンを追加ルートにしない
- カスタム OTel スパン: `search.embed`、`search.query`（MCP server span の子。Langfuse 独立トレースにはしない）
- Postgres クライアントスパンは `opentelemetry-instrumentation-asyncpg`
- Langfuse への export は SDK デフォルト（Langfuse / gen_ai / 既知 LLM instrumentor）に加え `fastmcp` と `opentelemetry.instrumentation.asyncpg` を許可する

compose 構成は [インフラ](/current/infrastructure.md) を参照。
