---
type: API Contract
title: MCP Tool・Apps Resource契約
description: ベクトル検索のページ取得、チャンク本文、Web検索、Gatewayによる認可付きApps Resource中継。
tags: [mcp, api, mcp-apps, pagination]
status: stable
generated:
  at: "2026-11-14T11:36:15Z"
  by: process:codex-agent
---

# MCP Tool・Apps Resource契約

輸送はStreamable HTTP、パス`/mcp`。Gatewayはcore `2025-11-25`のhandshake互換経路、MCP Appsはstable `2026-01-26`を対象とする。Apps非対応クライアントでも意味のあるJSON textを返し、同じ内容を`structuredContent`にも載せる。

knowledge-mcpはJWTの`aud=http://localhost:8000/mcp`、scope `mcp-tools`、role `knowledge-mcp-reader`を検証する。web-search-mcpは`aud=http://localhost:8001/mcp`、scope `web-search-mcp-tools`、role `web-search-reader`。UIからの認証は[認証認可](/current/features/authentication.md)、直結3LOは[ADR-0014](/decisions/ADR-0014-mcp-direct-three-legged-oauth.md)を参照。

## Gateway HTTP

| メソッド | パス | 用途 |
|---|---|---|
| GET | `/v1/mcp` | Registry内のenabledかつJWTのroleを満たす`{id, name, tools, url}`を返す。下流は呼ばない |
| POST | `/mcp/{server_id}` | `initialize`、`tools/list`、`tools/call`、`resources/list`、`resources/read`を処理する |

Gateway JWTは`aud=mcp-gateway`、`azp=open-webui`。Gatewayはホストポートを公開しない。Open WebUIのMCP接続先は`http://mcp-gateway:8082/mcp/knowledge`と`/mcp/web-search`。

- ToolとResourceの操作では、JWTと接続先`required_roles`をToken Exchange前に検証する。Tool実行は`allowed_tools`、Resource取得は`allowed_resources`の完全一致で制限する。
- `tools/list`は許可Toolだけを返す。`resources/list`は許可URIだけを返し、allowlist未設定なら空配列を返して下流を呼ばない。
- listの`cursor` / `nextCursor`を中継する。フィルタ後に空ページとなっても、上流の`nextCursor`を残す。
- Tool定義の`_meta.ui`・`outputSchema`・`annotations`、結果の全`content`・`structuredContent`・`isError`・`_meta`、ResourceのMIME・HTML・CSPを保持する。ネストしたリクエスト`_meta`を文字列化しない。
- Token ExchangeにはRegistryの`authentication.mode=keycloak_token_exchange`、`resource`、`scopes`が必須。下流用の既定値で補わない。タイムアウトは504、上流障害は502で返す。

## `search_knowledge`

| 引数 | 型 | 制約 |
|---|---|---|
| `query` | string | 必須。前後空白を除き、空は不可 |
| `top_k` | integer | 1ページの件数。既定5、1〜20 |
| `offset` | integer | 既定0、0以上。取得済みの順位数 |

戻り値は既存の`query`と`hits`に`pagination`を追加する。offset省略時の呼び方とhitの各フィールドは維持する。

```json
{
  "query": "認証フロー",
  "hits": [],
  "pagination": {
    "offset": 20,
    "page_size": 5,
    "has_more": false,
    "next_offset": null
  }
}
```

各hitは`document_id`、`title`、`excerpt`、`source`、`similarity`。`document_id`は検索対象チャンク行のUUIDで、親文書のIDではない。抜粋は本文の先頭240文字を基本とし、省略時は`...`を付ける。cosine類似度の範囲は`-1〜1`で、負値も保持する。

`has_more`がtrueのとき、次のリクエストへ`next_offset`を渡す。内部では1件余分に検索して続きを判定し、返却hitは`top_k`件までにする。ページをまたいで検索語と件数を揃え、変更時はoffsetを0へ戻す。総件数・総ページ数・snapshot tokenは返さない。同時Ingest中の固定スナップショットは保証しない。

検索順位はexact cosine距離とチャンクUUIDで安定させる。ページごとにembedding APIと距離計算を行うため、計算量と運用上の上限は[バックエンド](/current/features/backend.md)を参照。

Tool定義に`_meta.ui.resourceUri=ui://knowledge/search-results.html`を設定する。Appも同じToolをHost経由で呼び、ページを取得する。

## `get_document`

引数`document_id: string`にhitのチャンクUUIDを渡す。戻り値は`document_id`、`title`、`content`、`source`。見つからない場合は`error`を返す。親文書の全文結合はしない。

このToolはモデルとAppの両方が利用する。本文を画面に表示する一方、トレースへ送る本文はtruncateする（[トレーシング](/current/features/tracing.md)）。

## `search_web`（web-search-mcp）

引数は`query: string`（空不可）、`count: integer`（既定5、1〜20）。Brave Search APIから`title`、`url`、`snippet`を返す。`BRAVE_SEARCH_API_KEY`未設定時は`error`を返す。Apps Resourceは公開しない。

## Apps Resource

| 項目 | 値 |
|---|---|
| URI | `ui://knowledge/search-results.html` |
| MIME | `text/html;profile=mcp-app` |
| 内容 | JSとCSSをbundleした単一HTML |
| 認可 | knowledge-mcpのreader roleとscope。Gatewayでも同URIの完全一致allowlist |

HostはResourceを読み取り、sandboxed iframeへ表示する。Resourceの`_meta.ui.csp`を保持し、実行時の外部接続・外部リソースを要求しない。ブラウザはHost bridgeでToolを呼び、MCP tokenを直接持たない。AppのTool呼び出しはOpen WebUI標準の確認対象になる。

## 公開しない操作

文書Ingestと削除はホストの`scripts/seed.py`、`scripts/run_langflow_ingest.py`、`scripts/import_langflow.py`、`scripts/delete_document.py`を使う。MCPに書き込みTool、Prompt、許可UI以外の一般Resourceは公開しない。
