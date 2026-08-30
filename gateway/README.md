# mcp-gateway

Chainlit / FastMCP アプリとは別の Python プロジェクト。公式 `mcp>=2` を使い、Keycloak Token Exchange のあと Registry 上の MCP を呼ぶ。

- `GET /v1/mcp` — enabled かつ JWT の realm role が `required_roles` を満たすサーバー一覧（Chainlit JWT）
- `GET /v1/mcp/{server_id}/tools` — tool schema
- `POST /v1/mcp/{server_id}/tools/{name}:call` — 実行

ルートの Chainlit 2.12 は `mcp<2` のため、同一環境には載せない。
