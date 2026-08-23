# リリースログ

## 2026-08-23

- **Added**: Langflow を任意サイドカーとして追加し、ファイル Ingest PoC を既存検索経路から分離する（[Ingest](/current/features/ingest.md)、[ADR-0005](/decisions/ADR-0005-langflow-ingest-sidecar.md)）
- **Fixed**: MCP `_meta` に Langfuse `langfuse_trace_id` baggage を載せ、同一トレースの FastMCP スパンが Langfuse 一覧の追加ルートにならないようにする（[インフラ](/current/infrastructure.md)、[ADR-0004](/decisions/ADR-0004-langfuse-mcp-meta-tracing.md)）

## 2026-08-22

- **Changed**: Langfuse へ FastMCP と asyncpg クライアントスパンを export する（[アーキテクチャ](/current/architecture.md)、[ADR-0004](/decisions/ADR-0004-langfuse-mcp-meta-tracing.md)）
- **Added**: Chainlit 内蔵 MCP 接続 UI で Streamable HTTP / SSE サーバを追加接続でき、既定の knowledge-mcp が一覧に表示される（[UI 機能](/current/features/ui.md)、[ADR-0003](/decisions/ADR-0003-chainlit-traced-client.md)）
- **Added**: `search_knowledge` と `get_document` ツールを持つ FastMCP ベクトル検索サーバー（[API 契約](/current/features/api.md)）
- **Added**: traced FastMCP クライアント付き Chainlit チャット UI（[UI 機能](/current/features/ui.md)）
- **Added**: アプリスタック用 Docker compose とピン留め Langfuse 公式 compose（[インフラ](/current/infrastructure.md)）
- **Added**: FastMCP、pgvector、Chainlit、Langfuse `_meta` トレーシングの ADR（[意思決定](/decisions/index.md)）
- **Added**: e2e トレース伝播の自動テスト（`tests/test_trace_propagation.py`、in-memory OTel）
- **Changed**: MCP ツール input の Langfuse 記録とトレースネスト（`chat.turn` 1 本に統合、[アーキテクチャ](/current/architecture.md)）
