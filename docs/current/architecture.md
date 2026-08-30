---
type: Architecture
title: アーキテクチャ
description: FastMCP、MCP Gateway、Chainlit、pgvector、Keycloak、Langfuse のトレース構成と、ホスト原本から Langflow API 経由で documents へ載せる Ingest。
tags: [architecture, mcp, tracing, langflow, keycloak, gateway]
status: stable
generated:
  at: "2026-08-30T05:50:00Z"
  by: process:cursor-agent
---

# アーキテクチャ

## コンポーネント

| コンポーネント | 役割 |
|---|---|
| Chainlit（`src/chat_ui/`） | チャット UI、Keycloak OAuth、Langfuse ルートスパン、既定ツールは MCP Gateway 経由、追加 MCP 接続 UI |
| MCP Gateway（`gateway/`） | Chainlit JWT 検証、Keycloak Token Exchange、公式 `mcp>=2` クライアント |
| FastMCP サーバー（`src/knowledge_mcp/`） | Streamable HTTP MCP、Keycloak Resource Server、検索ツール、子スパン |
| PostgreSQL + pgvector | アプリ用ベクトルストアと Chainlit refresh token（pgcrypto） |
| Keycloak | ローカル IdP（realm import）。Chainlit ログインと Token Exchange |
| Langfuse（公式 compose） | トレース取り込みと UI |
| Langflow（任意サイドカー） | ファイル Ingest。専用 DB へ書き、ホスト adapter が `documents` へ複製する |
| MCP Inspector | FastMCP へのプロトコル検証（Bearer 必須） |

## アーキテクチャ図

```mermaid
flowchart TB
    subgraph users["利用者・検証"]
        User([ユーザー])
        Inspector[MCP Inspector]
    end

    subgraph app["アプリスタック（infra/app）"]
        Chainlit["Chainlit<br/>src/chat_ui/"]
        Gateway["MCP Gateway<br/>gateway/"]
        MCP["FastMCP Server<br/>src/knowledge_mcp/"]
        PG[("PostgreSQL 17<br/>pgvector")]
        Keycloak["Keycloak<br/>IdP"]
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
    User -->|OAuth :8081| Keycloak
    Chainlit -->|token / userinfo :8080 コンテナ DNS| Keycloak
    User -->|HTTP :7860| Langflow
    User -->|"host files (data/ingest)"| Adapter
    Adapter -->|"Files API + Flow API"| Langflow
    Langflow --> LFPG
    Langflow -->|embeddings| LLM
    Adapter -->|read Collection| LFPG
    Adapter -->|lifecycle sync| PG
    User -->|"MCP 接続 UI（HTTP/SSE）"| Chainlit
    Inspector -->|"Bearer + Streamable HTTP :8000/mcp"| MCP
    Chainlit -->|"JWT aud=mcp-gateway"| Gateway
    Gateway -->|Token Exchange| Keycloak
    Gateway -->|"Bearer aud=http://localhost:8000/mcp"| MCP
    Chainlit -->|追加 MCP tools/call + _meta| ExtraMCP
    Chainlit -->|chat completions| LLM
    MCP -->|vector search / get| PG
    MCP -->|embeddings| LLM
    Chainlit -->|OTLP / Langfuse SDK| Langfuse
    MCP -->|OTLP / Langfuse SDK| Langfuse
```

## 認証フロー（既定ツール）

```text
Keycloak ログイン（client=chainlit）
  -> Chainlit が refresh token をアプリ Postgres に保存
  -> チャット開始時、Chainlit は GET /v1/mcp（role でフィルタ）と GET /v1/mcp/{id}/tools でツールを発見する
  -> 既定ツール実行時、Chainlit は Gateway へ Bearer（aud に mcp-gateway）
  -> Gateway が Token Exchange（client=mcp-gateway、scope=mcp-tools。Keycloak 26 V2 では audience パラメータなし）
  -> knowledge-mcp が JWT を検証（aud に http://localhost:8000/mcp、role mcp-reader）
```

Chainlit トークンは knowledge-mcp に渡さない（[ADR-0012](/decisions/ADR-0012-mcp-gateway-resource-server.md)）。

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
- 既定の knowledge-mcp 呼び出しは Chainlit が Gateway へ HTTP し、Gateway が公式 MCP クライアントで `_meta` に W3C トレースコンテキストを注入する
- UI から接続した追加 MCP は公式 SDK の `ClientSession.call_tool(..., meta=...)` で同じ `_meta` を注入
- FastMCP Server が `_meta` を extract し SERVER スパンを子として接続する。baggage により Langfuse はこれらのスパンを追加ルートにしない
- カスタム OTel スパン: `search.embed`、`search.query`（MCP server span の子。Langfuse 独立トレースにはしない）
- Postgres クライアントスパンは `opentelemetry-instrumentation-asyncpg`
- Langfuse への export は SDK デフォルト（Langfuse / gen_ai / 既知 LLM instrumentor）に加え `fastmcp` と `opentelemetry.instrumentation.asyncpg` を許可する

compose 構成は [インフラ](/current/infrastructure.md) を参照。
