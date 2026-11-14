---
type: UI Capability
title: Open WebUIとMCP Apps
description: Keycloak SSO、role別MCP接続、検索結果一覧・チャンク本文・サーバー側ページ切替を持つチャットUI。
tags: [open-webui, ui, mcp, mcp-apps, oauth, keycloak, gateway]
status: stable
generated:
  at: "2026-11-14T12:06:12Z"
  by: process:codex-agent
---

# Open WebUIとMCP Apps

## エントリポイント

- URL: http://localhost:8080
- Host: Open WebUI v0.13.0。起動設定は`src/open_webui_ext/startup.py`、観測拡張は`src/open_webui_ext/tracing.py`。
- 認証: Keycloak SSOのみ。通常のメール・パスワード登録画面は無効。専用clientは`open-webui`。
- 採用判断は[ADR-0015](/decisions/ADR-0015-open-webui-mcp-apps.md)、認証フローは[認証認可](/current/features/authentication.md)。

## チャットとMCP接続

- `CHAT_MODEL`を既定モデルにし、native function callingを使う。設定されたknowledge / Web検索のうち、利用者に公開された接続先を既定ツールとして選ぶ。
- 初回起動時に`CHAT_MODEL`をOpen WebUIのモデルDBへ登録し、認証済み利用者全員へのread grant、native params、MCP tool metadata、usage capabilityを設定する。上流v0.13では未登録base modelが一般利用者に表示されないためで、providerの`/models`取得に依存しない。既存の管理者所有モデルは変更せず、system所有モデルでも管理者が編集したmetadata / paramsを保持する。
- `dev`は両MCP、`dev2`はWeb検索のみ、`readerless`はMCP接続なし。全員がKeycloakログイン後に通常のチャットを利用できる。
- 接続先は管理者がRegistryへ登録し、起動時に`TOOL_SERVER_CONNECTIONS`へ反映する。Open WebUIのDBに残った設定がRegistryを上書きしないよう、persistent configを無効にする。
- 利用者による任意URL / stdio / SSE接続は提供しない。旧Chainlitの接続・切断画面や`POST|DELETE /mcp`は使わない。
- MCP接続はOpen WebUIのバックエンドからGatewayへ行う。`system_oauth`で利用者のSSO access tokenを送り、下流MCP向けのToken ExchangeはGatewayが担う。
- Open WebUIがLLMへ公開するfunction名は接続先IDを含むHostの名前付けになる。MCP上のツール名`search_knowledge`、`get_document`、`search_web`は維持する。

## ナレッジ検索App

`search_knowledge`の結果に関連付いた`ui://knowledge/search-results.html`を、Hostが認証付きで読み取り、sandboxed iframeに表示する。

- 類似度順の順位、タイトル、抜粋、出典、類似度を一覧表示する。類似度は確率や正解率ではない。
- タイトル選択で既存の`get_document`をHost経由で呼び、同じApp内にチャンク本文を表示する。原本全体を結合しない。
- 「前へ／次へ」、現在ページ、表示範囲を表示する。1ページの表示件数は5・10・20件。件数変更時は先頭へ戻り、ページ変更時には前ページの詳細選択を解除する。
- ページ切替では`search_knowledge`へ同じ検索語と`offset`を渡す。既に受け取った最大20件だけを分割する方式ではない。総件数・総ページ数は表示しない。
- 読込中、空結果、取得エラーを表示する。ページ取得に失敗した場合は現在の一覧を維持し、後から返った古い応答で画面を上書きしない。
- 狭い画面では本文を一覧の下に配置する。キーボード操作とフォーカスを保ち、文書内容はHTMLとして実行せずテキストとして表示する。

App起点のページ取得と本文取得はMCP Tool呼び出しであり、Open WebUI標準の確認ダイアログを経由する。AppにBearerやAPIキーを渡さず、外部CDNや直接のAPI接続を要求しない。App内で検索語を変更する機能は持たない。

## データと観測

会話データとOAuth状態はOpen WebUIの`/app/backend/data`に保存する。`WEBUI_SECRET_KEY`は固定値を使い、再作成時にも維持する。以前のChainlit会話やCookieをOpen WebUIへ移行する処理は持たず、最初に再ログインする。

会話ごとにLangfuse sessionを分け、各ターンのLLM・MCP・検索処理を同一traceへ接続する。App内で後から実行した操作は独立した`mcp.app` trace。詳細は[トレーシング](/current/features/tracing.md)。

設定、起動、既存realmからの移行は[インフラ](/current/infrastructure.md)、Tool / Resource契約は[API](/current/features/api.md)を参照。
