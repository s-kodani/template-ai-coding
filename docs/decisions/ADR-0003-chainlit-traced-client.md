---
type: Decision Record
title: "ADR-0003: traced MCP クライアント UI として Chainlit"
description: Chainlit がチャット UI、Langfuse ルートトレース、既定 FastMCP クライアント、追加 MCP 接続 UI を担う。
tags: [decision, chainlit, ui]
status: stable
decision_status: accepted
---

# ADR-0003: traced MCP クライアント UI として Chainlit

## 背景

end-to-end トレーシングには、ツール呼び出し時の MCP `_meta` トレース伝播が必要。LibreChat は SEP-414 `_meta` を注入せず、Mongo / Redis / Meilisearch を追加してもトレース要件を満たさない。

検証時には knowledge-mcp 以外の MCP サーバも Chainlit から接続したい。Chainlit 2.x の内蔵 MCP UI は公式 MCP SDK の `ClientSession` を使うため、当初は `_meta` 注入が保証されないと判断していた。その後、`call_tool(..., meta=...)` で `_meta` を明示できることを確認した。

## 決定

- 検証用チャット UI として **Chainlit** を採用する
- knowledge-mcp（`MCP_SERVER_URL`）は **アプリケーションコード** から FastMCP Client で呼び出す（native telemetry）
- 追加サーバは Chainlit 内蔵 MCP 接続 UI（Streamable HTTP / SSE）で接続する。接続先 URL は [ADR-0009](/decisions/ADR-0009-chainlit-mcp-user-servers-allowlist.md) の allowlist に従う
- 既定 knowledge-mcp は `mcp_storage_key` へシードし、UI 一覧に表示する（接続自体は FastMCP Client でも維持する）
- 追加サーバへの `tools/call` では `inject_trace_context` により `_meta` を明示注入する
- stdio MCP は無効化する（named server も宣言しない）
- 同一プロセス内で FastMCP import より前に Langfuse を初期化する

## 結果

- 開発者向け UI でローカル検証に十分
- 起動直後から knowledge-mcp を使え、追加 MCP は画面から接続できる
- プロセスが分離された環境（Docker compose）では、ツール呼び出しをまたいだ親子トレース結合が機能する
- 追加 MCP 接続は Chainlit サーバから行われるため、Docker 内ではコンテナから到達でき、かつ allowlist に含まれる URL が必要（[ADR-0009](/decisions/ADR-0009-chainlit-mcp-user-servers-allowlist.md)）
