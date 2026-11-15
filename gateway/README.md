# mcp-gateway

FastMCPと別環境の公式MCP SDK 2.xで下流MCPを呼び、Keycloak Token Exchangeを行う認証付きStreamable HTTP Gatewayです。ホストポートは公開しません。

- `GET /v1/mcp`: enabledかつJWTのrealm roleを満たす接続先を返す。
- `POST /mcp/{server_id}`: core `2025-11-25`互換のTool/Resource list/read/callを中継する。
- Tool schema、`_meta.ui`、`structuredContent`、`isError`、Resource MIME/CSP、list cursorを保持する。
- ResourceはRegistryの`authorization.allowed_resources`と完全一致するURIのみ許可する。
- inboundは`aud=mcp-gateway`、`azp=open-webui`を検証し、下流へは接続先専用の交換後トークンを送る。

依存は`gateway/uv.lock`、起動・認証・MCP Appsの正本は`docs/current/`を参照してください。
