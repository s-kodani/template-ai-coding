---
type: Decision Record
title: "ADR-0012: MCP Gateway と knowledge-mcp Resource Server"
description: Chainlit の Keycloak トークンを MCP へパススルーせず、別プロセスの Gateway が Token Exchange して knowledge-mcp を呼ぶ。
tags: [decision, architecture, authentication, mcp, keycloak, gateway]
status: stable
decision_status: accepted
generated:
  at: "2026-08-30T06:40:00Z"
  by: process:cursor-agent
---

# ADR-0012: MCP Gateway と knowledge-mcp Resource Server

## 背景

Chainlit は Keycloak でログインするが、既定の knowledge-mcp 呼び出しは Bearer なしの FastMCP Client だった。[ADR-0011](/decisions/ADR-0011-keycloak-chainlit-oauth.md) は MCP SSO と RBAC をスコープ外としていた。

MCP の Authorization では、下流サーバーへ上流 Access Token をパススルーしてはならない。Chainlit トークン（`aud` に `mcp-gateway`）と knowledge-mcp トークン（`aud` に `http://localhost:8000/mcp`）を分け、Gateway だけが Token Exchange する必要がある。

ルートの `pyproject.toml` は Chainlit 2.12 の `mcp<2` 制約がある。Gateway の MCP クライアントは公式 `mcp>=2` が必要なため、同一 Python 環境には載せられない。

## 決定

- **mcp-gateway** を別プロセス / 別 Python プロジェクト（`gateway/`、`mcp>=2`）としてアプリ Compose に載せる。ホストポートは公開しない
- Chainlit の Gateway ツールは `GET /v1/mcp` と `GET /v1/mcp/{server_id}/tools` で発見し、`POST /v1/mcp/{server_id}/tools/{name}:call` で実行する。`GET /v1/mcp` は JWT の realm role が各サーバーの `required_roles` を満たすものだけ返す。LLM schema は knowledge 専用にハードコードしない。LLM 名は `{server_id}__{mcp_tool_name}`（OpenAI の `^[a-zA-Z0-9_-]{1,64}$`）。Token Exchange は各サーバーの `authentication.mode=keycloak_token_exchange` と `resource` / `scopes` を必須とし、knowledge 向けデフォルトは持たない
- knowledge-mcp は Keycloak の Resource Server とする（FastMCP `JWTVerifier` + `RemoteAuthProvider`）。検証する `aud` と PRM `resource` は `http://localhost:8000/mcp`。Keycloak 26 の standard token exchange（V2）では `audience` パラメータを付けない（付けると `Requested audience not available: knowledge-mcp`）。Resource `aud` は `mcp-gateway` の default scope `mcp-tools` の custom audience mapper が付与する
- Gateway は Chainlit トークンを検証し（`aud=mcp-gateway`、`azp=chainlit`）、`mcp-gateway` クライアントで Token Exchange する。ユーザー識別は JWT `sub` のみ。リクエスト body の `user_id` は拒否する
- ツール認可は realm role `mcp-reader`。scope 名は `mcp-tools`
- Chainlit の refresh token はアプリ Postgres に pgcrypto で保存する（`TOKEN_STORE_DATABASE_URL`）。Chainlit 内蔵 data layer の `DATABASE_URL` は空のまま
- Chainlit MCP 接続 UI には Registry の enabled サーバーを **表示専用** で載せる。`POST /mcp` による実セッションは張らず、トークンも渡さない。追加の未認証 MCP は `user_servers` allowlist のまま
- ローカル HTTP を許容する。TLS / mTLS / CIMD / Redis / 第 2 MCP はこの垂直スライスの対象外
- 本決定は [ADR-0011](/decisions/ADR-0011-keycloak-chainlit-oauth.md) の「MCP SSO は導入しない」「RBAC は持たない」を knowledge-mcp 経路について改訂する。Chainlit の IdP としての Keycloak 採用は ADR-0011 のまま
- 既定ツールが FastMCP Client を直接使わなくなる点で [ADR-0003](/decisions/ADR-0003-chainlit-traced-client.md) を更新する。Gateway が MCP `_meta` に W3C トレースを注入する点で [ADR-0004](/decisions/ADR-0004-langfuse-mcp-meta-tracing.md) を補う

## 結果

- knowledge-mcp は Compose 上で JWKS 検証を必須にする。MCP Inspector も Bearer が必要（`scripts/mcp_dev_token.py`）
- 既定ツールの実行は Gateway を経由し、Chainlit トークンは knowledge-mcp に届かない。現行シーケンスは [認証認可](/current/features/authentication.md)
- プラグ UI の Gateway MCP は表示専用であり、Chainlit の MCP セッションにはならない
- 追加 MCP（allowlist 内）は従来どおり Chainlit 内蔵クライアントで接続できる
- in-process FastMCP Client テストは `MCP_JWKS_URI` 未設定時に HTTP Bearer を要求しない
