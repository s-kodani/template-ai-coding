---
type: Decision Record
title: "ADR-0004: MCP _meta 伝播による Langfuse トレース"
description: Langfuse 公式 compose と FastMCP native telemetry。SDK 4 の export フィルタと `_meta` baggage 伝播。
tags: [decision, langfuse, tracing, otel]
status: stable
decision_status: accepted
---

# ADR-0004: MCP _meta 伝播による Langfuse トレース

## 背景

1 チャットターンあたり 1 本の Langfuse トレースに、LLM、MCP クライアント/サーバー、embedding、Postgres クライアントスパンを含める必要がある。

## 決定

- Langfuse は `infra/langfuse/` 配下の **公式 Docker Compose** コピーでデプロイする
- 可観測性は **トレースのみ**（OTel metrics / logs パイプラインはスコープ外）
- W3C トレースコンテキストは **FastMCP native telemetry**（`FASTMCP_TELEMETRY_MODE=native`）で MCP `_meta` 経由で伝播する
- FastMCP 既定の `_meta` 注入は `traceparent` / `tracestate` のみのため、Langfuse SDK 4 がプロセスを跨いだルート判定に使う **`langfuse_trace_id` baggage も `_meta` へ載せる**（同一 `traceId` の FastMCP / asyncpg スパンがトレース一覧の追加ルートにならないようにする）
- Postgres は **`opentelemetry-instrumentation-asyncpg`** で計装する（クライアントスパンのみ）
- Langfuse SDK 4 のデフォルト export フィルタに加え、`fastmcp` と `opentelemetry.instrumentation.asyncpg` を **`should_export_span` で明示 allow** する（httpx 等の汎用クライアントスパンは送らない）

## 結果

- Langfuse API キーは初回 UI サインアップ後に手動設定する
- キー未設定時はトレースは no-op だが、MCP と Chainlit は利用可能
- 1 チャットターンの Langfuse 一覧ルートは `chat.turn` 1 件。FastMCP / asyncpg スパンは同一 `traceId` の子としてネストする

## 改訂

既定ツールは Chainlit の FastMCP Client が Gateway `/mcp/{server_id}` の `tools/call` `_meta` に W3C を載せ、Gateway が下流 knowledge-mcp へ転送する（[ADR-0012](/decisions/ADR-0012-mcp-gateway-resource-server.md)、[ADR-0013](/decisions/ADR-0013-mcp-gateway-per-server-streamable-http.md)）。追加 MCP の `_meta` 注入は従来どおり Chainlit 側。
