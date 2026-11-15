---
type: Decision Record
title: "ADR-0015: Open WebUIとMCP Appsによる検索UI"
description: ChainlitをOpen WebUIへ置き換え、認証付きApps Resource、検索ページ取得、限定したトレースhookを採用する。
tags: [decision, architecture, open-webui, mcp-apps, authentication, tracing, pagination]
status: stable
decision_status: accepted
generated:
  at: "2026-11-14T11:36:15Z"
  by: process:codex-agent
---

# ADR-0015: Open WebUIとMCP Appsによる検索UI

## 背景

検索結果をJSONや最終回答だけでなく、チャット内の一覧と本文として閲覧する必要がある。既存のChainlit構成はMCP Apps Hostを持たず、GatewayもTool metadataと`structuredContent`を落とし、Resourceを中継していなかった。

[Chainlitは2026年10月にアーカイブ](https://github.com/Chainlit/chainlit)されている。[Open WebUI v0.13.0](https://openwebui.com/blog/v0-13-0-your-model-gets-a-computer)は、UI Resourceの取得、sandbox、Host bridgeを含む[MCP Apps標準対応](https://docs.openwebui.com/features/extensibility/mcp/)を持つ。ただし標準のMCP呼び出しはトレース`_meta`を注入せず、そのままでは既存の1ターン1traceを維持できない。

ユーザーは2026-11-14の設計確認で、Open WebUIへの切替、MCP接続先の管理者登録、詳細トレース維持、一覧＋チャンク本文、サーバー側ページ取得を選択し、実装計画を承認した。UI・認証・観測の変更はLevel 1、検索ページ取得とResource契約はLevel 2の判断として記録する。

## 決定

- Open WebUI v0.13.0の固定派生イメージを標準チャットUIにする。Chainlitの実行構成と専用コードを退役する。
- Host・iframe sandbox・SSO・MCP接続は上流の標準機能を使う。MCP接続先はRegistryで管理し、利用者による任意URL追加を廃止する。
- Keycloak専用clientを`open-webui`とし、`system_oauth`でGatewayへ利用者のSSO tokenを送る。GatewayのJWT audience / authorized partyと下流Token Exchangeの境界を維持する。
- realm roleを`mcp_roles`としてID token / userinfoへ載せ、Open WebUIの固定グループと接続先grantへ同期する。Gatewayと下流MCPの認可も継続する。
- `search_knowledge`にUI URIを関連付け、`ui://knowledge/search-results.html`を認証付きResourceとして提供する。Appはplain JavaScriptと公式SDKを単一HTMLへbundleし、Host bridgeで検索ページと本文を取得する。
- GatewayはTool / 結果 / Resourceのメタデータとエラーを保持する。Resource取得はroleと完全一致URI allowlistで制限する。
- `search_knowledge(query, top_k=5, offset=0)`へ後方互換な引数とpaginationを追加する。1件余分に取得して続きを判定し、総件数・総ページ数は返さない。順位はexact cosine距離とUUIDで安定させる。
- Open WebUIの会話worker、generation、MCP raw call、App RPCの4点だけに観測hookを追加する。上流ソースのhash不一致や依存競合ではbuildを失敗させる。通常会話は`chat.turn`、後続App操作は独立した`mcp.app`とする。
- 既存realmは専用client / scopeの冪等同期で更新し、ユーザーや既存clientを削除しない。Keycloakデータを専用volumeへ保持し、初回は旧コンテナから非破壊で移してユーザーの`sub`を維持する。旧`chainlit_oauth_tokens`もデータとして残す。

## 代替案

| 案 | 判断 |
|---|---|
| ChainlitへApps Hostを独自追加 | sandbox、Resource、bridge、認証を保守する範囲が大きいため採用しない |
| LibreChat | Apps対応はあるが、今回の既存Gateway・SSO構成にはOpen WebUIの標準接続を採用する |
| Open WebUIを併設 | ユーザーが標準UIの切替を選択したため採用しない |
| Open WebUI標準観測だけを使う | 会話からMCP・DBまでの親子トレースを維持できないため採用しない |
| 取得済み20件をApp内で分割 | 20件を超える結果を閲覧できないため採用しない |
| HNSWの候補を単純OFFSET取得 | 探索上限により深いページが終了し得る。ローカル検証ではexact順位を選ぶ |
| 検索snapshot / cursor store | 新たな状態・所有権・期限の管理を増やすため現時点では導入しない |

## 結果と制約

標準Hostを利用しながら、一覧、本文、5・10・20件の前後移動を提供できる。Apps非対応クライアントには既存JSON textを返す。検索Toolとget_documentはread-onlyのまま。

ページごとにembeddingとO(N)の距離計算が発生する。大規模データ向けの索引候補ページングやキャッシュは別の設計判断にする。同時Ingest中のsnapshotは固定せず、総ページ数を表示しない。

AppからのTool呼び出しはOpen WebUI標準の確認ダイアログを経由する。iframeへtokenを渡さない。後続App callbackはchat IDを持たないため、過去ターンのtraceへ無理に接続しない。

上流更新時は固定ソースのパッチ、依存constraints、認証、stream / cancellation、並行ユーザー分離を再検証する。単にimage tagを上げる運用はしない。

## 関連する判断

本ADRはChainlit固有の[ADR-0003](/decisions/ADR-0003-chainlit-traced-client.md)、[ADR-0009](/decisions/ADR-0009-chainlit-mcp-user-servers-allowlist.md)、[ADR-0011](/decisions/ADR-0011-keycloak-chainlit-oauth.md)を置き換える。過去の本文は履歴として維持する。

[ADR-0004](/decisions/ADR-0004-langfuse-mcp-meta-tracing.md)のMCP trace伝播、[ADR-0012](/decisions/ADR-0012-mcp-gateway-resource-server.md)のToken Exchange境界、[ADR-0013](/decisions/ADR-0013-mcp-gateway-per-server-streamable-http.md)のサーバー単位輸送、[ADR-0014](/decisions/ADR-0014-mcp-direct-three-legged-oauth.md)の直結3LOは継続する。現在の構成の正本は[アーキテクチャ](/current/architecture.md)。
