# 検証済み依存関係（2026-09-06）

Python 依存の解決結果は `uv.lock` と `gateway/uv.lock` を Source of Truth とする。

| コンポーネント | 宣言 | lock / イメージ |
|---|---|---|
| Python | `>=3.12,<3.13` | 3.12 |
| Chainlit | `>=2.12.0,<3` | 2.12.0 (`uv.lock`) |
| FastMCP | `>=2.14.0` | 3.4.7 (`uv.lock`) |
| MCP SDK（アプリ） | FastMCP の依存 | 1.29.1 (`uv.lock`) |
| MCP SDK（Gateway） | `>=2.1,<3` | 2.1.1 (`gateway/uv.lock`) |
| Langfuse Python SDK | `>=3.0.0` | 4.15.1 (`uv.lock`) |
| OpenAI Python SDK | `>=1.60.0` | 3.6.0 (`uv.lock`) |
| Keycloak | Compose で固定 | `keycloak/keycloak:26.4.5` |
| Langflow | Compose で固定 | `langflowai/langflow:1.11.4` |
| pgvector（アプリ / Langflow） | Compose で固定 | `pgvector/pgvector:pg17` / `pg16` |
| Langfuse compose | upstream commit で固定 | `62751446149b702b419a9292ddfc2280cdf74b8c` |
| Embedding モデル | 設定で固定 | `text-embedding-3-small`（1536 次元） |

Langfuse compose の取得元と検証 hash は `infra/langfuse/SOURCE.txt` に記録する。更新時は upstream の git SHA とローカルファイルの SHA-256 を両方更新する。
