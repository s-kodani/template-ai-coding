---
type: Architecture
title: アーキテクチャ
description: FastMCP（knowledge-mcp / web-search-mcp）、MCP Gateway、Chainlit、pgvector、Keycloak、Langfuse のトレース構成と、ホスト原本から Langflow API 経由で documents へ載せる Ingest。
tags: [architecture, mcp, tracing, langflow, keycloak, gateway]
status: stable
generated:
  at: "2026-09-13T09:12:00Z"
  by: process:cursor-agent
---

# アーキテクチャ

## コンポーネント

| コンポーネント | 役割 |
|---|---|
| Chainlit（`src/chat_ui/`） | チャット UI、Keycloak OAuth、Langfuse ルートスパン、既定ツールは MCP Gateway 経由（knowledge / web-search）、追加 MCP 接続 UI |
| MCP Gateway（`gateway/`） | Chainlit JWT 検証、Keycloak Token Exchange、サーバー単位 Streamable HTTP、下流は公式 `mcp>=2` |
| FastMCP サーバー（`src/knowledge_mcp/`） | Streamable HTTP MCP、Keycloak Resource Server、ベクトル検索ツール、子スパン |
| FastMCP サーバー（`src/web_search_mcp/`） | Streamable HTTP MCP、Keycloak Resource Server、Brave Web 検索ツール、子スパン |
| PostgreSQL + pgvector | アプリ用ベクトルストアと Chainlit refresh token（pgcrypto） |
| Keycloak | ローカル IdP（realm import）。Chainlit ログイン、Token Exchange、直結 MCP の Authorization Server |
| Langfuse（公式 compose） | トレース取り込みと UI |
| Langflow（任意サイドカー） | ファイル Ingest。専用 DB へ書き、ホスト adapter が `documents` へ複製する |
| MCP Inspector | FastMCP へのプロトコル検証。直結は 3LO（OAuth）、非対話は Bearer |

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
        MCP["knowledge-mcp<br/>src/knowledge_mcp/"]
        WebMCP["web-search-mcp<br/>src/web_search_mcp/"]
        PG[("PostgreSQL 17<br/>pgvector")]
        Keycloak["Keycloak<br/>IdP"]
    end

    subgraph external["外部 API"]
        LLM["OpenAI 互換 API<br/>（chat / embeddings）"]
        Brave["Brave Search API"]
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
    User -->|"host files (docs)"| Adapter
    Adapter -->|"Files API + Flow API"| Langflow
    Langflow --> LFPG
    Langflow -->|embeddings| LLM
    Adapter -->|read Collection| LFPG
    Adapter -->|lifecycle sync| PG
    User -->|"MCP 接続 UI（HTTP/SSE）"| Chainlit
    Inspector -->|"3LO または Bearer + Streamable HTTP :8000/mcp"| MCP
    Chainlit -->|"JWT aud=mcp-gateway"| Gateway
    Gateway -->|Token Exchange| Keycloak
    Gateway -->|"Bearer aud=http://localhost:8000/mcp"| MCP
    Gateway -->|"Bearer aud=http://localhost:8001/mcp"| WebMCP
    Chainlit -->|追加 MCP tools/call + _meta| ExtraMCP
    Chainlit -->|chat completions| LLM
    MCP -->|vector search / get| PG
    MCP -->|embeddings| LLM
    WebMCP -->|search_web| Brave
    Chainlit -->|OTLP / Langfuse SDK| Langfuse
    MCP -->|OTLP / Langfuse SDK| Langfuse
```

## 認証フロー（既定ツール）

詳細なシーケンス（claim、role フィルタ、失敗時、Inspector / 追加 MCP）は [認証認可](/current/features/authentication.md)。

```text
Keycloak ログイン（client=chainlit）
  -> Chainlit が refresh token をアプリ Postgres に保存
  -> プラグ UI の POST /mcp で Chainlit は catalog url へ MCP セッションを張り tools/list する（role フィルタは GET /v1/mcp）
  -> 既定ツール実行時、Chainlit の Gateway MCP セッション経由で POST /mcp/{id} tools/call（Bearer は aud に mcp-gateway）
  -> Gateway が Token Exchange（client=mcp-gateway。knowledge は scope=mcp-tools、web-search は scope=web-search-mcp-tools。Keycloak 26 V2 では audience パラメータなし）
  -> 各 MCP が JWT を検証（knowledge: aud=http://localhost:8000/mcp、role knowledge-mcp-reader。web-search: aud=http://localhost:8001/mcp、role web-search-reader）
```

Chainlit トークンは knowledge-mcp に渡さない（[ADR-0012](/decisions/ADR-0012-mcp-gateway-resource-server.md)）。直結クライアントの 3LO は [ADR-0014](/decisions/ADR-0014-mcp-direct-three-legged-oauth.md)。

## レイヤ構成（MCP サーバー）

```text
HTTP トランスポート（Streamable HTTP、Origin 検証）
  -> MCP ツール（search_knowledge, get_document）
    -> SearchService
      -> EmbeddingClient（OpenAI 互換 API）
      -> VectorRepository（asyncpg + pgvector）
```

## トレース伝播

メタデータの正本は [Langfuse OTEL トレーシング](/current/features/tracing.md)。以下は構成概要。

```mermaid
flowchart TD
    chat["chat.turn<br/>（Chainlit ルート + trace 属性）"]
    llm["llm.generate<br/>（generation）"]
    tool["tool observation"]
    client["FastMCP Client span"]
    server["FastMCP Server span<br/>（_meta から接続）"]
    embed_otel["search.embed<br/>（OTel span）"]
    embed_lf["search.embed<br/>（embedding observation）"]
    query["search.query"]
    fetch["get_document.fetch"]
    db["asyncpg spans"]

    chat --> llm
    chat --> tool
    tool --> client
    client -->|"traceparent + baggage in MCP _meta"| server
    server --> embed_otel
    embed_otel --> embed_lf
    server --> query
    server --> fetch
    query --> db
```

- Chainlit が `chat.turn` / `llm.generate` と tool observation を作成し、`propagate_attributes` で `user.id` / `session.id` 等を子 span へ伝播する
- 既定 Gateway MCP は Chainlit FastMCP Client → Gateway `/mcp/{server_id}` → knowledge-mcp または web-search-mcp。Gateway は `_meta` を転送するのみ
- 追加 MCP は `ClientSession.call_tool(..., meta=...)` で同じ `_meta` を注入
- MCP サーバーは `search.embed`（OTel + embedding observation）、`search.query`、`get_document.fetch` と asyncpg スパンをネストする
- Langfuse export フィルタと秘匿ルールは [トレーシング](/current/features/tracing.md) を参照

compose 構成は [インフラ](/current/infrastructure.md) を参照。
