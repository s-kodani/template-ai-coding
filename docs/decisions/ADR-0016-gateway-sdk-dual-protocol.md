---
type: Decision Record
title: "ADR-0016: Gateway公開側を公式SDKで新旧MCPに対応させる"
description: 公式Python SDKで2026-07-28と従来2025-11-25を受け、下流FastMCPはlegacyで接続する。
tags: [decision, architecture, gateway, mcp, compatibility]
status: stable
decision_status: accepted
generated:
  at: "2026-11-15T03:44:00Z"
  by: process:codex-agent
---

# Gateway公開側を公式SDKで新旧MCPに対応させる

## 背景

[ADR-0013](/decisions/ADR-0013-mcp-gateway-per-server-streamable-http.md)の公開側は手書きの2025-11-25 JSON-RPC adapterで、2026-07-28クライアントのserver/discoverを拒否し、旧handshakeへフォールバックしていた。Gateway環境の公式Python SDK 2.3.0は新旧coreを扱える一方、下流FastMCPは別環境のSDK 1.xを使う。

Issue #146のImplementation Planと本アーキテクチャ方針は、PR #145のマージ確認後、依頼者の「進めてください」で承認された。必須legacy保証は2025-11-25、MCPエラーはSDK標準へ移すことも確認済み。

## 決定

- 公開側は公式Python SDK 2.3.0のlow-level ServerとStreamable HTTP appを使う。Registry登録ごとにServerを作り、親FastAPI lifespanで起動・停止する。
- `/mcp/{server_id}`を維持し、2026-07-28の各要求と従来の2025-11-25 handshakeを同じendpointで受ける。JSON応答・stateless HTTPを使い、暗黙のsessionや共有session storeを追加しない。
- wire形式・バージョン検証・標準メッセージの処理はSDKへ委譲する。SDK 2.3.0のheader-only新旧経路判定を補うため、modern本文をlegacyヘッダーで送る要求はSDKの公開classifierで入口検証する。入口のbodyにもSDKの4MiB上限を適用する。
- JWTとrole/Tool/Resource allowlist、Keycloak Token Exchange、TokenCacheの分離を維持する。principalはHTTP request stateに持ち、Server instanceへ保存しない。
- SDKがmodern tools/callの引数ヘッダー検証用にtools/listを内部取得する場合も、元のtools/callを認可してから交換・下流取得する。
- 下流は既存Clientのmode=legacyを維持し、2025-11-25で接続する。新coreの予約metadataはGatewayで終端し、Apps metadata・trace contextは維持する。
- core2026ではUI拡張をextensionsに広告し、2025の初期化ではSDKのexperimental_capabilities経由で広告する。Tool/ResourceのUI metadataとCSPは保持する。
- 認証・endpointエラーはHTTPエラー、handler内の拒否・下流失敗はSDKのJSON-RPC errorにし、既存code/statusをerror.dataに保持する。ToolのisErrorはTool結果のまま返す。GET /v1/mcpのREST契約は維持する。
- 権限依存のdiscovery/list/readはprivate、ttlMs=0（即時stale）とし、利用者横断のキャッシュを追加しない。

## 代替案

- server/discoverだけを追加: 各要求の検証・結果型・新旧変換を満たさないため不採用。
- 全wire処理を独自実装: 公式SDKと検証責務が重複するため不採用。
- 下流まで一括移行: FastMCP依存・SDK環境・App検証が拡大するため今回は不採用。
- SDKのhigh-level Tool再登録: 下流のschema・結果・metadataを中継する用途ではlow-level handlerの方が再定義が少ない。

## 結果

従来の認証境界と下流を維持しながら、新coreのクライアントがフォールバックなしに接続できる。2025-06-18以前への追加保証や、新しいTasks/sampling/subscriptions機能は提供しない。SDK公開APIの振る舞いは契約テストで保護する。

ADR-0013のサーバー単位endpoint・内部公開・Registryの判断は維持し、公開側を独自adapterとする部分のみ本ADRで改訂する。現在の仕様は[API](/current/features/api.md)、[認証認可](/current/features/authentication.md)、[トレーシング](/current/features/tracing.md)を参照する。
