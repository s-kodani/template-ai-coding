---
type: Decision Record
title: "ADR-0013: MCP Gateway をサーバー単位の Streamable HTTP にする"
description: Chainlit と MCP Gateway のツール list/call を REST ではなくサーバー単位の Streamable HTTP にする。カタログ発見だけ GET /v1/mcp を残す。
tags: [decision, architecture, mcp, gateway, transport]
status: stable
decision_status: accepted
generated:
  at: "2026-09-01T15:50:00Z"
  by: process:cursor-agent
---

# ADR-0013: MCP Gateway をサーバー単位の Streamable HTTP にする

## 背景

[ADR-0012](/decisions/ADR-0012-mcp-gateway-resource-server.md) は Token Exchange・パススルー禁止・role フィルタを決めた。当時の Chainlit–Gateway 契約は Gateway 独自 REST（`GET /v1/mcp/{id}/tools` と `POST ...:call`）だった。

Chainlit 2.12 は `mcp<2`、Gateway は公式 `mcp>=2` のため同一 Python 環境に載せられない。ツール実行だけ REST にすると、プロトコル透過性がなく、クライアントは Gateway 専用 HTTP を持ち続ける。

代替は次だった。

- 案 A: Registry のサーバーごとに Streamable HTTP（`/mcp/{server_id}`）
- 案 B: 単一集約 `/mcp` に全ツールを載せる
- 案 C: HTTP リバースプロキシ

## 決定

- **案 A** を採用する。Gateway は `POST /mcp/{server_id}` で Streamable HTTP JSON-RPC を受ける
- サーバー一覧の発見だけ **`GET /v1/mcp`** を残す。応答は `{id, name, tools, url}`。`url` は Compose 内部の `PUBLIC_BASE_URL`（既定 `http://mcp-gateway:8082`）から `{base}/mcp/{server_id}`
- REST の tool schema / call は削除する。`GET /health` は残す
- Chainlit はプラグ UI ではなく **アプリ管理の FastMCP Client** で catalog `url` に接続する。Bearer は `TokenManager` の Chainlit JWT（`aud=mcp-gateway`）。JWT をブラウザに出さない
- プラグ UI のサーバー単位 ON/OFF は `/gateway-mcp` のまま。`user_servers.allowed_urls` に Gateway を足さない
- Gateway ホストポートは公開しない。Inspector は knowledge-mcp `:8000` 直結のまま
- LLM 名は `{server_id}__{mcp_tool_name}` のまま。MCP パス上の名前は接頭辞なし
- Token Exchange・パススルー禁止・`required_roles` / `allowed_tools` は [ADR-0012](/decisions/ADR-0012-mcp-gateway-resource-server.md) のまま
- inbound は公式 `mcp>=2` MCPServer ではない。ルートの FastMCP（`mcp 1.29`）が JSON 応答する Streamable HTTP クライアントと話せる **JSON-RPC アダプタ** にする。下流呼び出しは公式 `mcp>=2` Client
- トレースは Chainlit の FastMCP `tools/call` `_meta` を Gateway が下流へ転送する（[ADR-0004](/decisions/ADR-0004-langfuse-mcp-meta-tracing.md)）

## 結果

- Chainlit の既定ツール list/call は MCP プロトコルになる。カタログだけ REST
- Gateway は引き続き Resource Server 境界。Chainlit JWT は knowledge-mcp に届かない
- FastMCP 2.14 Client が必要とするメソッドは `initialize` / `notifications/*` / `ping` / `tools/list` / `tools/call`。セッション ID は持たない
- 現行シーケンスは [認証認可](/current/features/authentication.md)
