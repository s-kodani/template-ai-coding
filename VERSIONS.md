# ピン留め依存関係（2026-08-22）

| コンポーネント | 目標 |
|---|---|
| MCP 仕様 | 2026-07-28 系（実装時に再確認） |
| FastMCP | >=2.14、Streamable HTTP stateless |
| Chainlit | >=2.7 |
| Keycloak | `quay.io/keycloak/keycloak:26.4.5` |
| Langfuse | 公式 `docker-compose.yml`（`langfuse/langfuse` main） |
| Python | 3.12 |
| pgvector イメージ | `pgvector/pgvector:pg17` |
| Embedding モデル | `text-embedding-3-small`（1536 次元） |

Langfuse compose の取得元: セットアップ時に `langfuse/langfuse` の `main` から取得。
更新時は git SHA を `infra/langfuse/SOURCE.txt` に記録してください。
