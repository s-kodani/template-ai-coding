# 機能

- [UI（Chainlit）](/current/features/ui.md) — Keycloak OAuth。Gateway MCP は `GET /v1/mcp` とサーバー単位 Streamable HTTP で配線。追加 MCP 接続 UI
- [Langfuse OTEL トレーシング](/current/features/tracing.md) — 分散トレース、MCP `_meta` 伝播、送信メタデータの正本
- [認証認可シーケンス](/current/features/authentication.md) — ログインから Gateway Token Exchange、knowledge-mcp 検証まで
- [Ingest（Langflow）](/current/features/ingest.md) — ホスト原本を Files / Flow API で chunk 化し、adapter 経由で `documents` へ載せる。Collection 確認は `QueryPgVector`
- [バックエンド（SearchService）](/current/features/backend.md)
- [API（MCP ツール）](/current/features/api.md)
