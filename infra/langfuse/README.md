# Langfuse ローカルスタック（公式 compose）

初回起動前に `env.example` を `.env` にコピーしてください。

```bash
cp env.example .env
openssl rand -hex 32
```

コマンドの出力で `.env` の `ENCRYPTION_KEY` を置き換えます。`ENCRYPTION_KEY` は **64 文字の hex** が必須で、プレースホルダーのままだと Langfuse UI が 500 になります。置き換えてから起動してください。

```bash
make -C infra network
docker compose -f docker-compose.yml -f network.yml --env-file .env up -d
```

http://localhost:3000 でサインアップ後、プロジェクトキーをリポジトリルートの `.env` に
`LANGFUSE_PUBLIC_KEY` と `LANGFUSE_SECRET_KEY` としてコピーしてください。
