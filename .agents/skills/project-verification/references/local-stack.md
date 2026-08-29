# Local Stack Validation

## 前提

- `.env` に `OPENAI_API_KEY`
- Docker daemon 起動（Cloud Agent: `bash .cursor/start.sh`）

## 起動

```bash
make -C infra up
make -C infra migrate   # 既存 volume 更新時
make -C infra seed
```

## ポート

| サービス | URL / ポート |
|---|---|
| Chainlit | http://localhost:8080 |
| FastMCP | http://127.0.0.1:8000/mcp |
| Langfuse | http://localhost:3000 |
| App Postgres | localhost:5433 |

## Langflow（任意）

```bash
make -C infra langflow-up
make -C infra langflow-down
```

デフォルトの `make -C infra up` には含まれない。

## 切り分け

- `docker info` 失敗 → `.cursor/start.sh`
- コンテナ間通信失敗 → Cloud 環境の `bridge-nf-call-iptables` 設定を確認（`AGENTS.md` Cursor Cloud 節）
