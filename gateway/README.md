# mcp-gateway

Chainlit / FastMCP アプリとは別の Python プロジェクト。公式 `mcp>=2` で下流 MCP を呼び、Keycloak Token Exchange する。inbound はルートの FastMCP（`mcp 1.29`）向け JSON-RPC Streamable HTTP アダプタ。

- `GET /v1/mcp` — enabled かつ JWT の realm role が `required_roles` を満たす `{id, name, tools, url}`（Chainlit JWT）
- `POST /mcp/{server_id}` — Streamable HTTP（`tools/list` / `tools/call` 等）

ルートの Chainlit 2.12 は `mcp<2` のため、同一環境には載せない。ホストポートは公開しない。
