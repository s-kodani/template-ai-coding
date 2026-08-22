# Langfuse ローカルスタック（公式 compose）

初回起動前に `env.example` を `.env` にコピーしてください。`ENCRYPTION_KEY` は **64 文字の hex**（`openssl rand -hex 32`）が必須です。プレースホルダーのままだと Langfuse UI が 500 になります。

```bash
cp env.example .env
make -C infra network
docker compose -f docker-compose.yml -f network.yml --env-file .env up -d
```

http://localhost:3000 でサインアップ後、プロジェクトキーをリポジトリルートの `.env` に
`LANGFUSE_PUBLIC_KEY` と `LANGFUSE_SECRET_KEY` としてコピーしてください。
