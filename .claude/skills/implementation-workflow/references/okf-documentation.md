# OKF Documentation

Phase 6 の OKF ルール、Current-state Documentation、Decision Record。

リポジトリが OKF を採用している場合、`AGENTS.md` で指定された Knowledge Bundle に対して以下を適用する。

## 1. Concept Document

予約ファイル以外の Markdown は Concept Document として扱う。

```yaml
---
type: <Concept Type>
title: <Human-readable title>
description: <One-line summary>
---
```

`type` は必須。`title` と `description` は原則付与する。

### 推奨 Concept Type

- `Business Requirements`
- `Architecture`
- `UI Capability`
- `Backend Capability`
- `API Contract`
- `Infrastructure`
- `Decision Record`
- その他、対象 Concept を自己説明できる type

## 2. Frontmatter Metadata

```yaml
resource: <canonical URI or path>
tags: [tag-a, tag-b]
status: stable
generated:
  by: <actor>
  at: <ISO 8601 datetime>
verified:
  - by: <actor>
    at: <ISO 8601 datetime>
stale_after: <RFC3339 datetime with offset>
sources:
  - id: <stable-source-id>
    resource: <URI or path>
    title: <source title>
```

ルール:

- `status` は `draft` / `stable` / `deprecated`
- frontmatter の `type` は Knowledge Catalog 連携時に `okf_type` へマップされる
- AI が Concept を更新した場合は `generated` を更新し、`verified` は人間確認まで付けない
- `verified` は実際に確認した actor のみ。AI が人間確認を推測してはいけない
- `stale_after` / `sources` は実データがある場合のみ。捏造しない
- producer-defined field（`decision_status`, `superseded_by` 等）は Catalog 往復時に `extra` へ格納される
- Attested Computation 用フィールド（`runtime`, `executor`, `attester` 等）は本リポジトリでは使用しない

### Actor Convention

- AI Agent / Tool: `<producer>/<version>`
- Human: `human:<id>`
- Automated Process: `process:<id>`

識別できない actor を作らない。

## 3. Cross-link

OKF Bundle 内では bundle-relative link を優先する。

```markdown
[Architecture](/current/architecture.md)
[Authentication Decision](/decisions/ADR-0012-authentication.md)
```

リンク自体に関係種別を埋め込まず、周囲の文章で関係を説明する。

## 4. `index.md`

- Bundle root と主要ディレクトリでは、`AGENTS.md` で指定された範囲の `index.md` を維持する
- Concept の追加・移動・削除・deprecated 化に応じて更新する
- root `index.md` 以外では frontmatter を付けない
- root `index.md` では `okf_version` を宣言できる

## 5. ADR と OKF lifecycle の分離

OKF の `status` は Concept の lifecycle。ADR 固有状態は `decision_status` を使う。

```yaml
---
type: Decision Record
title: "ADR-0012: Authentication strategy"
description: Authentication方式の選択と理由を記録する。
tags: [decision, architecture, authentication]
status: stable
decision_status: accepted
---
```

推奨 `decision_status`: `proposed`, `accepted`, `superseded`, `deprecated`, `rejected`

置き換え時:

```yaml
status: deprecated
decision_status: superseded
superseded_by: /decisions/ADR-0024-new-authentication.md
```

過去 ADR は削除せず履歴として維持する。

---

## Current-state Documentation

最終実装によって以下が変更された場合、該当 OKF Concept を更新する。

- ビジネス上の振る舞い
- システムアーキテクチャ
- UI / Backend 機能
- API / データモデル
- 外部連携 / インフラ / 運用振る舞い

Current-state Documentation には**最終実装**を記述する。破棄された Implementation Plan を書いてはいけない。

Concept が複数の独立知識を抱え、AI が毎回全文を読む必要が生じている場合は、適切な Concept 単位への分割を検討する。

---

## Decision Record

ADR 基準を満たす恒久的な意思決定が含まれる場合、Decision Record を作成または更新する。

本文には通常以下を含める:

- Context
- Decision
- Alternatives Considered
- Rationale
- Consequences
- Related Decisions

ADR 固有の状態は `decision_status` で管理し、OKF lifecycle の `status` とは分離する。

---

## Phase 6: Documentation Reconciliation

実装と検証の完了後、最終実装と恒久ドキュメントを照合する。Implementation Plan をそのままコピーしてはいけない。

| 問い | 保存先 |
|---|---|
| 現在何が正しいか？ | Current-state Documentation / OKF Concept |
| なぜこの設計を選んだか？ | Decision Record / OKF Concept |
| 何が変わったか？ | Release Note / OKF `log.md`（`## v?.?.? (未確定)`） |
| どのような過程で実装したか？ | 原則破棄 |

Release Log の詳細は `references/release-note.md` を読む。
