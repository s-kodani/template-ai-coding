# 意思決定

- [ADR-0001: FastMCP Streamable HTTP](/decisions/ADR-0001-fastmcp-streamable-http.md)
- [ADR-0002: アプリデータに PostgreSQL pgvector](/decisions/ADR-0002-postgres-pgvector.md)
- [ADR-0003: traced MCP クライアント UI として Chainlit](/decisions/ADR-0003-chainlit-traced-client.md) — 既定 FastMCP 接続と追加 MCP 接続 UI
- [ADR-0004: MCP _meta 伝播による Langfuse トレース](/decisions/ADR-0004-langfuse-mcp-meta-tracing.md) — FastMCP / asyncpg の export と `_meta` baggage 伝播
- [ADR-0005: Langflow を Ingest 用サイドカーにする](/decisions/ADR-0005-langflow-ingest-sidecar.md) — Retrieval は Chainlit + FastMCP、システムインデックスは `documents`
- [ADR-0006: documents を Chunk 行として進化させる](/decisions/ADR-0006-documents-chunk-schema.md) — 1 行 = 1 chunk、親 ID は `uuid5(source)`
- [ADR-0007: document_id / content_hash による冪等な再 Ingest](/decisions/ADR-0007-document-lifecycle.md) — 未変更は Skip、変更時は親 ID 配下を削除して再投入
- [ADR-0008: 原本はホスト、Langflow Files API は一時転送](/decisions/ADR-0008-host-originals-langflow-api.md) — My Files に依存せず API で Ingest Flow を実行する
