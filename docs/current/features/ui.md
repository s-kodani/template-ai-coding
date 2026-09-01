---
type: UI Capability
title: Chainlit チャット UI
description: Keycloak OAuth 付きの Chainlit チャット UI。既定 knowledge-mcp は MCP Gateway 経由。追加 MCP は接続 UI。
tags: [chainlit, ui, mcp, oauth, keycloak, gateway]
status: stable
generated:
  at: "2026-09-01T15:50:00Z"
  by: process:cursor-agent
---

# Chainlit チャット UI

## エントリポイント

- モジュール: `src/chat_ui/app.py`
- URL: http://localhost:8080
- 設定: `.chainlit/config.toml`
- 認証: Keycloak OAuth（[ADR-0011](/decisions/ADR-0011-keycloak-chainlit-oauth.md)）。既定ツールは [ADR-0012](/decisions/ADR-0012-mcp-gateway-resource-server.md)。シーケンスは [認証認可](/current/features/authentication.md)

## 動作

- 未ログインではチャットできない。Keycloak（`knowledge` realm）でログインする
- 開発ユーザーは `dev` / `dev`（email `dev@localhost`、role `knowledge-mcp-reader`）。`readerless` はログインできるが `GET /v1/mcp` に knowledge が出ず、ツール実行も Gateway が拒否する。管理者コンソールは http://localhost:8081
- チャット開始時に Gateway の `GET /v1/mcp`（role でフィルタ）から許可サーバーと `url` を得て、各 `url` へアプリ管理の FastMCP Client で `tools/list` する。LLM 名は `{server_id}__{mcp_tool_name}`。実行は同じ Client の `tools/call`（[ADR-0013](/decisions/ADR-0013-mcp-gateway-per-server-streamable-http.md)）
- Chainlit の Keycloak トークンを knowledge-mcp へ渡さない
- refresh token はアプリ Postgres（`TOKEN_STORE_DATABASE_URL` + pgcrypto）に保存する。Chainlit 内蔵 data layer の `DATABASE_URL` は空
- Chainlit 内蔵 MCP 接続 UI で Streamable HTTP / SSE サーバを追加接続できる。接続先は `.chainlit/config.toml` の `user_servers.allowed_urls` に含まれる origin に限る（[ADR-0009](/decisions/ADR-0009-chainlit-mcp-user-servers-allowlist.md)）
- Registry の enabled Gateway MCP はプラグ UI（MCP Servers）に載せる。Chainlit はそれらへ MCP セッションを張らない。切断するとそのサーバーのツールを LLM / 実行から外し、再接続で戻す（チャットを開き直すと再び有効）
- 追加接続したサーバのツールはセッションに載り、LLM の function tools に動的追加される
- 追加サーバへの `tools/call` では `_meta` へ W3C `traceparent` と Langfuse `baggage` を注入する
- Gateway ツールの同名衝突は `{server_id}__` 接頭辞で共存する。追加 MCP セッション同士の同名は先に接続した方を優先する
- stdio MCP は無効（named server も宣言せず、Chainlit サーバ上での任意コマンド実行を避ける）
- Langfuse ルート観測 `chat.turn` とネストされた `llm.generate` を作成

## MCP 接続 UI

接続はブラウザではなく **Chainlit プロセス** から行われる。

- 追加 MCP へは、Chainlit コンテナから到達でき、allowlist に含まれる URL を指定する
- 既定 allowlist: `http://mcp-server:8000`、`http://localhost:8000`、`http://127.0.0.1:8000`、`http://host.docker.internal:8000`
- Gateway MCP は `mcp-autoload.js` が Registry から一覧へ載せる。プラグ UI の `POST|DELETE /mcp` は `/gateway-mcp` に書き換わり、セッションの利用フラグだけを更新する。Chainlit プロセスは Streamable HTTP セッションを張らない
- knowledge-mcp へ UI からヘッダーなしで実接続しようとすると JWT 必須のため失敗する。ツール実行は Gateway 経由のまま

## 設定

`CHAT_MODEL`、`OPENAI_API_KEY`、`MCP_GATEWAY_URL`、`MCP_GATEWAY_REGISTRY_PATH`、`TOKEN_STORE_*`、`CHAINLIT_AUTH_SECRET`、`OAUTH_GENERIC_*`、Langfuse キーはルートの `.env.example` を参照。
