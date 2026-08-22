# リリースログ

## 2026-08-22

- **Added**: `search_knowledge` と `get_document` ツールを持つ FastMCP ベクトル検索サーバー（[API 契約](/current/features/api.md)）
- **Added**: traced FastMCP クライアント付き Chainlit チャット UI（[UI 機能](/current/features/ui.md)）
- **Added**: アプリスタック用 Docker compose とピン留め Langfuse 公式 compose（[インフラ](/current/infrastructure.md)）
- **Added**: FastMCP、pgvector、Chainlit、Langfuse `_meta` トレーシングの ADR（[意思決定](/decisions/index.md)）
- **Added**: e2e トレース伝播の自動テスト（`tests/test_trace_propagation.py`、in-memory OTel）
- **Changed**: MCP ツール input の Langfuse 記録とトレースネスト（`chat.turn` 1 本に統合、[アーキテクチャ](/current/architecture.md)）
