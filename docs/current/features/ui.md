---
type: UI Capability
title: Chainlit チャット UI
description: Keycloak OAuth 付きの Chainlit チャット UI。knowledge-mcp への traced FastMCP 接続と追加 MCP 接続。
tags: [chainlit, ui, mcp, oauth, keycloak]
status: stable
generated:
  at: "2026-08-29T12:00:00Z"
  by: process:cursor-agent
---

# Chainlit チャット UI

## エントリポイント

- モジュール: `src/chat_ui/app.py`
- URL: http://localhost:8080
- 設定: `.chainlit/config.toml`
- 認証: Keycloak OAuth（[ADR-0011](/decisions/ADR-0011-keycloak-chainlit-oauth.md)）

## 動作

- 未ログインではチャットできない。Keycloak（`knowledge` realm）でログインする
- 開発ユーザーは `dev` / `dev`（email `dev@localhost`）。管理者コンソールは http://localhost:8081
- OpenAI 互換チャットに、knowledge-mcp の `search_knowledge` / `get_document` を常に載せる
- 既定ツールは `MCP_SERVER_URL` へ FastMCP Client で呼び出す（native telemetry）
- Chainlit 内蔵 MCP 接続 UI で Streamable HTTP / SSE サーバを追加接続できる。接続先は `.chainlit/config.toml` の `user_servers.allowed_urls` に含まれる origin に限る（[ADR-0009](/decisions/ADR-0009-chainlit-mcp-user-servers-allowlist.md)）
- 既定の knowledge-mcp（`MCP_SERVER_URL`）は MCP 一覧に user-provided として表示され、ページ読み込み時に UI 経由でも接続する
- 追加接続したサーバのツールはセッションに載り、LLM の function tools に動的追加される
- 追加サーバへの `tools/call` では `_meta` へ W3C `traceparent` と Langfuse `baggage` を注入する
- ツール名が衝突した場合は knowledge-mcp、続いて先に接続したセッションを優先する
- stdio MCP は無効（named server も宣言せず、Chainlit サーバ上での任意コマンド実行を避ける）
- Langfuse ルート観測 `chat.turn` とネストされた `llm.generate` を作成

## MCP 接続 UI

接続はブラウザではなく **Chainlit プロセス** から行われる。

- Docker compose 利用時、同一スタックの knowledge-mcp は `http://mcp-server:8000/mcp` として一覧に出る（接続は Chainlit サーバから行われる）
- ホスト上の追加 MCP へは、Chainlit コンテナから到達でき、allowlist に含まれる URL を指定する（既定は `:8000`。他ポートは `allowed_urls` へ追記する）
- 既定 allowlist: `http://mcp-server:8000`、`http://localhost:8000`、`http://127.0.0.1:8000`、`http://host.docker.internal:8000`

## 設定

`CHAT_MODEL`、`OPENAI_API_KEY`、`MCP_SERVER_URL`、`CHAINLIT_AUTH_SECRET`、`OAUTH_GENERIC_*`、Langfuse キーはルートの `.env.example` を参照。
