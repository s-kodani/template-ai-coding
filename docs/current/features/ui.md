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
- チャット開始時に Gateway の `GET /v1/mcp`（role でフィルタ）から許可サーバーを得て、サーバー側で各 catalog `url` へ Chainlit MCP セッションを auto-connect する。`tools/list` で得た schema は LLM 名 `{server_id}__{mcp_tool_name}` に接頭辞付けする。実行は同じ MCP セッションの `tools/call`（[ADR-0013](/decisions/ADR-0013-mcp-gateway-per-server-streamable-http.md)）
- Chainlit の Keycloak トークンを knowledge-mcp へ渡さない
- refresh token はアプリ Postgres（`TOKEN_STORE_DATABASE_URL` + pgcrypto）に保存する。Chainlit 内蔵 data layer の `DATABASE_URL` は空
- Chainlit 内蔵 MCP 接続 UI で Streamable HTTP / SSE サーバを追加接続できる。接続先は `.chainlit/config.toml` の `user_servers.allowed_urls` に含まれる origin に限る（[ADR-0009](/decisions/ADR-0009-chainlit-mcp-user-servers-allowlist.md)）
- Registry の enabled Gateway MCP はプラグ UI（MCP Servers）に載せ、Chainlit MCP セッションとして接続する。My MCPs の OFF で disconnect し、ON で `POST /mcp` 再接続する。UI 状態と実行経路は一致する
- 追加接続したサーバのツールはセッションに載り、LLM の function tools に動的追加される
- 追加サーバへの `tools/call` では `_meta` へ W3C `traceparent` と Langfuse `baggage` を注入する（詳細は [Langfuse OTEL トレーシング](/current/features/tracing.md)）
- Gateway ツールの同名衝突は `{server_id}__` 接頭辞で共存する。追加 MCP セッション同士の同名は先に接続した方を優先する
- stdio MCP は無効（named server も宣言せず、Chainlit サーバ上での任意コマンド実行を避ける）
- Langfuse: `chat.turn` ルート、`llm.generate`（generation）、ツール observation。`user.id` / `session.id` は `propagate_attributes` で付与（[トレーシング](/current/features/tracing.md)）

## MCP 接続 UI

接続はブラウザではなく **Chainlit プロセス** から行われる。

- 追加 MCP へは、Chainlit コンテナから到達でき、allowlist に含まれる URL を指定する
- 既定 allowlist: `http://mcp-server:8000`、`http://localhost:8000`、`http://127.0.0.1:8000`、`http://host.docker.internal:8000`
- Gateway MCP は `mcp-autoload.js` が Registry から一覧へ載せる（表示 seed のみ）。プラグ UI の `POST|DELETE /mcp` は Chainlit 標準のまま。Gateway 名は `gateway_mcp_connect` ミドルウェアが JWT 注入 connect として処理する
- 接続数バッジ（クリップアイコン右上）は Chainlit が MCP セッション状態を管理する。Gateway MCP の JWT は DevTools の `/mcp` body に含まれない
- knowledge-mcp へ UI からヘッダーなしで直接接続しようとすると JWT 必須のため失敗する（allowlist 内でも Gateway 名はミドルウェア経由）

## 設定

`CHAT_MODEL`、`OPENAI_API_KEY`、`MCP_GATEWAY_URL`、`MCP_GATEWAY_REGISTRY_PATH`、`TOKEN_STORE_*`、`CHAINLIT_AUTH_SECRET`、`OAUTH_GENERIC_*`、Langfuse キーはルートの `.env.example` を参照。トレースメタデータの一覧は [Langfuse OTEL トレーシング](/current/features/tracing.md)。
