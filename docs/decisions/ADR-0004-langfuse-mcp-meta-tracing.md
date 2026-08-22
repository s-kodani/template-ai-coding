---
type: Decision Record
title: "ADR-0004: MCP _meta 伝播による Langfuse トレース"
description: Langfuse 公式 compose と FastMCP native telemetry によるトレースのみの可観測性。
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
- Postgres は **`opentelemetry-instrumentation-asyncpg`** で計装する（クライアントスパンのみ）

## 結果

- Langfuse API キーは初回 UI サインアップ後に手動設定する
- キー未設定時はトレースは no-op だが、MCP と Chainlit は利用可能
