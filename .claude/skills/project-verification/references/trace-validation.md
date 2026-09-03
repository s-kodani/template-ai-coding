# Trace Validation

## 規約（変更時に確認）

正本: [Langfuse OTEL トレーシング](/current/features/tracing.md)

1. Langfuse SDK は **FastMCP import 前** に初期化（`src/knowledge_mcp/server.py`, `src/chat_ui/app.py`）
2. `should_export_langfuse_span` で `fastmcp` / `asyncpg` のみ追加 export
3. MCP `_meta` に W3C `traceparent` + Langfuse `baggage`（`langfuse_trace_id` および `propagate_attributes` の `as_baggage`）
4. `chat.turn` で `user.id` / `session.id` / tags / metadata を伝播
5. API キー・embedding ベクトル・全文 document を span にログしない

## 自動テスト

```bash
uv run pytest tests/test_trace_propagation.py tests/test_langfuse_span_export.py tests/test_tracing_metadata.py tests/test_tool_trace_output.py
```

## 手動（Langfuse UI）

`docs/current/infrastructure.md` の「トレース検証チェックリスト」に従う。

- 1 チャットターン = Langfuse 一覧に `chat.turn` が 1 行
- トレース属性に `user.id` / `session.id`（設定時 `langfuse.environment` / `langfuse.release`）
- ツールスパンが同一 trace 内にネスト

## 関連 ADR

- [ADR-0004](/decisions/ADR-0004-langfuse-mcp-meta-tracing.md)
