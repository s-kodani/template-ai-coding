---
type: Decision Record
title: "ADR-0011: Keycloak を Chainlit のローカル IdP にする"
description: ローカル検証スタックの Chainlit 認証に Keycloak OAuth / OIDC を使う。
tags: [decision, architecture, authentication, keycloak, chainlit]
status: stable
decision_status: accepted
generated:
  at: "2026-08-29T12:00:00Z"
  by: process:cursor-agent
---

# ADR-0011: Keycloak を Chainlit のローカル IdP にする

## 背景

Chainlit は認証なしでホストに公開されていた。ローカルでも IdP を含む OAuth フローを検証するため、専用の Identity Provider が必要になった。

候補は次のとおり。

- Chainlit のパスワード認証のみ
- GitHub / Google など外部 IdP
- Keycloak を Compose に載せる

外部 IdP は開発者アカウントとインターネット到達性に依存する。パスワード認証だけでは OIDC クライアントとしての検証にならない。

## 決定

- ローカル IdP として **Keycloak**（`quay.io/keycloak/keycloak:26.4.5`、`start-dev --import-realm`）をアプリ Compose に含める
- Chainlit は組み込みの **Keycloak OAuth provider**（`OAUTH_KEYCLOAK_*` と `@cl.oauth_callback`）を使う
- ブラウザと token / userinfo の両方で `http://localhost:8081` を使い、Chainlit コンテナには `extra_hosts: localhost:host-gateway` を付与する
- 対象は Chainlit のみ。FastMCP、Langfuse、Langflow の SSO は導入しない
- 認可は「Keycloak でログインできた利用者はチャット可能」とし、RBAC は持たない
- realm / client / 開発ユーザーは Git 上の realm JSON を Source of Truth とし、専用 Postgres は持たない

## 結果

- `make -C infra up` で Keycloak と Chainlit が揃い、未ログインではチャットできない
- ホストから Keycloak 管理 UI（`:8081`）と Chainlit（`:8080`）に到達できる
- start-dev のためデータはコンテナ再作成で消える。realm 定義を変えたあとは Keycloak コンテナの再作成が必要
- クライアントシークレットと管理者パスワードはローカル開発用プレースホルダであり、本番秘密ではない
