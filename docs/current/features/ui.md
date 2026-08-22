---
type: UI Capability
title: Chainlit チャット UI
description: knowledge-mcp への traced FastMCP 接続と、追加 MCP サーバを選べる Chainlit チャット UI。
tags: [chainlit, ui, mcp]
status: stable
---

# Chainlit チャット UI

## エントリポイント

- モジュール: `src/chat_ui/app.py`
- URL: http://localhost:8080
- 設定: `.chainlit/config.toml`

## 動作

- OpenAI 互換チャットに、knowledge-mcp の `search_knowledge` / `get_document` を常に載せる
- 既定ツールは `MCP_SERVER_URL` へ FastMCP Client で呼び出す（native telemetry）
- Chainlit 内蔵 MCP 接続 UI で Streamable HTTP / SSE サーバを追加接続できる
- 既定の knowledge-mcp（`MCP_SERVER_URL`）は MCP 一覧に表示され、ページ読み込み時に UI 経由でも接続する
- 追加接続したサーバのツールはセッションに載り、LLM の function tools に動的追加される
- 追加サーバへの `tools/call` では `inject_trace_context` により `_meta` へ traceparent を注入する
- ツール名が衝突した場合は knowledge-mcp、続いて先に接続したセッションを優先する
- stdio MCP は無効（Chainlit サーバ上での任意コマンド実行を避ける）
- Langfuse ルート観測 `chat.turn` とネストされた `llm.generate` を作成

## MCP 接続 UI

接続はブラウザではなく **Chainlit プロセス** から行われる。

- Docker compose 利用時、同一スタックの knowledge-mcp は `http://mcp-server:8000/mcp` として一覧に出る（接続は Chainlit サーバから行われる）
- ホスト上の追加 MCP へは、Chainlit コンテナから到達できる URL（例: `http://host.docker.internal:<port>/mcp`）を指定する

## 設定

`CHAT_MODEL`、`OPENAI_API_KEY`、`MCP_SERVER_URL`、Langfuse キーはルートの `.env.example` を参照。
