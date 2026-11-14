# 検証済み依存関係（2026-11-14）

Python 依存の解決結果は `uv.lock` と `gateway/uv.lock` を Source of Truth とする。

| コンポーネント | 宣言 | lock / イメージ |
|---|---|---|
| Python | `>=3.12,<3.13` | 3.12 |
| Open WebUI | 固定base image + hash検証付き観測patch | `ghcr.io/open-webui/open-webui:v0.13.0` |
| MCP Apps SDK | `2.1.0` | `apps/knowledge-search/package-lock.json` |
| Node.js（App buildのみ） | `>=22` | `node:22-slim` |
| FastMCP | `>=3.4.11,<4` | 3.4.11 (`uv.lock`)。`knowledge_mcp` / `web_search_mcp` 共通 |
| web-search-mcp | `src/web_search_mcp/`、`BRAVE_SEARCH_API_KEY` | Brave Search API（`api.search.brave.com`） |
| MCP SDK（アプリ） | FastMCP の依存 | 1.30.0 (`uv.lock`) |
| MCP SDK（Gateway） | `>=2.3.0,<3` | 2.3.0 (`gateway/uv.lock`) |
| MCP SDK（Open WebUI） | v0.13.0 base imageの依存をconstraintsで保持 | 2.3.0（実imageで確認） |
| OTel（Open WebUI） | image専用のsecurity fix固定 | 1.45.2 / 0.66b2 (`infra/app/open-webui-otel-requirements.txt`) |
| Langfuse Python SDK | `>=4.15.1,<5` | 4.15.1 (`uv.lock`) |
| OpenTelemetry API / SDK（アプリ） | `>=1.29.0` | 1.45.2、instrumentation / asyncpg / semantic-conventions は0.66b2 (`uv.lock`) |
| OpenTelemetry API（Gateway） | `>=1.45.2` | 1.45.2 (`gateway/uv.lock`) |
| dnspython（アプリ） | 推移的依存 | 2.9.2 (`uv.lock`) |
| OpenAI Python SDK | `>=1.60.0` | 3.6.0 (`uv.lock`) |
| Keycloak | Compose で固定 | `keycloak/keycloak:26.6.4` |
| Langflow | Compose で固定 | `langflowai/langflow:1.11.4` |
| pgvector（アプリ / Langflow） | Compose で固定 | `pgvector/pgvector:pg17` / `pg16` |
| Langfuse compose | upstream commit で固定 | `62751446149b702b419a9292ddfc2280cdf74b8c` |
| Embedding モデル | 設定で固定 | `text-embedding-3-small`（1536 次元） |

Langfuse compose の取得元と検証 hash は `infra/langfuse/SOURCE.txt` に記録する。更新時は upstream の git SHA とローカルファイルの SHA-256 を両方更新する。
