---
type: Decision Record
title: "ADR-0009: Chainlit 2.12 の MCP user_servers allowlist"
description: 追加 MCP は user_servers と静的 URL allowlist に限定し、stdio は宣言しない。
tags: [decision, chainlit, mcp, security]
status: stable
decision_status: accepted
---

# ADR-0009: Chainlit 2.12 の MCP user_servers allowlist

## 背景

Chainlit 2.12.0 は CVE-2026-45018（stdio コマンドインジェクション）と CVE-2026-45019（任意 URL への SSRF）を直すため、MCP 設定を破壊的に変更した。レガシーの `[features.mcp.sse]` / `[features.mcp.stdio]` / `[features.mcp.streamable-http]` があると起動しない。ユーザー追加の SSE / Streamable HTTP は `[features.mcp.user_servers]` の明示オプトインと空でない `allowed_urls` が必須になった。allowlist 照合は scheme + host + port 完全一致と path prefix であり、任意ポートを 1 エントリで許可できない。

[ADR-0003](/decisions/ADR-0003-chainlit-traced-client.md) は追加 MCP を内蔵 UI で接続する方針を残している。`MCP_SERVER_URL` は環境ごとに異なるため、knowledge-mcp を `config.toml` の named server に固定できない。

## 決定

- Chainlit を `>=2.12.0,<3` に上げ、2.12 MCP スキーマへ移行する
- `user_servers.enabled = true` とし、テンプレート用の静的 allowlist を置く
  - `http://mcp-server:8000`
  - `http://localhost:8000`
  - `http://127.0.0.1:8000`
  - `http://host.docker.internal:8000`
- knowledge-mcp は named server にせず、`mcp-autoload.js` が Gateway エントリを MCP 一覧へ載せる（実接続の URL は載せない。切断は `/gateway-mcp` でセッションの利用フラグだけを更新する）
- `[[features.mcp.servers]]` に stdio サーバを置かない
- 上記以外の origin / port の追加 MCP は `.chainlit/config.toml` の allowlist を編集してから接続する

## 代替案

- 環境変数から allowlist を生成する — 任意ポートには柔軟だが、起動時の設定生成が増えるため不採用
- `user_servers` を無効化し named server のみにする — UI からの追加接続を捨てるため、ADR-0003 と合わない

## 理由

最小変更で 2.12 のセキュリティモデルに合わせ、compose の knowledge-mcp とホスト `:8000` の検証経路を残す。任意 URL は 2.12 では表現できないため、allowlist 外は設定編集を前提にする。

## 結果

- Chainlit コンテナはレガシー MCP キーでは起動しない
- 追加 MCP は allowlist 内の SSE / Streamable HTTP のみ
- stdio を UI から追加できない
- knowledge-mcp のツール呼び出しは MCP Gateway が担う。プラグ UI の一覧表示は `mcp-autoload.js` の表示専用エントリ（[ADR-0012](/decisions/ADR-0012-mcp-gateway-resource-server.md)）
