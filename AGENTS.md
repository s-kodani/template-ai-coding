# AGENTS.md

## 目的

このファイルには、このリポジトリ固有のルールと参照先のみを記載します。

実装時の共通ワークフロー、Implementation Plan、ADR判定、Verification、OKF Documentation Reconciliation、Completion Reportの詳細は、`implementation-workflow` Skillに従ってください。

---

## 使用するSkill

コードの実装、変更、リファクタリング、機能追加を行う場合は、`implementation-workflow` Skillを使用します。

Skillとこのファイルの指示が競合する場合は、このリポジトリ固有のルールである`AGENTS.md`を優先します。

---


## GitHub Work Item Policy

このリポジトリでは、コードの実装、変更、リファクタリング、機能追加などの作業は、原則としてGitHub Issueへ紐付けます。

### Issue作成前の確認

対象Issueがユーザーから明示されていない場合は、**新規Issueを作成する前に、すでに手動作成済みのIssueがあるかを必ずユーザーへ確認します。**

- 既存Issueがある場合: ユーザーが指定したIssue番号またはURLを使用する。
- 既存Issueがない場合: ユーザーの回答後に新規Issueを起票する。
- 現在の依頼ですでにIssue番号またはURLが指定されている場合: 再確認は不要。
- 既存Issueの有無が不明なまま、新規Issueを起票してはいけない。
- 重複Issueの作成を避ける。

- GitHub Issue: 作業契約・作業履歴・Session Handoff
- Pull Request: 実装差分・Review
- OKF Knowledge Bundle: 現在状態と恒久知識
- ADR: 重要な設計判断の理由

GitHub IssueをCurrent-state DocumentationやADRの代替として扱ってはいけません。

### Issue本文

Issue本文には現在有効な以下を記載します。

- Goal
- Background / Context
- In Scope / Out of Scope
- Acceptance Criteria
- Constraints
- Related Knowledge / Issue / PR

Implementation PlanやSession固有の進捗は本文へ保存しません。

Goal、Scope、Acceptance Criteria、Constraintsが変更された場合は、Issue本文を最新状態へ更新し、変更理由と影響をIssueコメントへ追記します。

### Session Checkpoint

作業途中でセッションを終了・引き継ぎする場合は、`implementation-workflow` Skillの`Session Handoff Protocol`に従って、対象IssueへWork Checkpointコメントを追加します。

過去Checkpointは編集せず、Append-onlyの履歴として維持します。

### Resume

別セッションで再開する場合は、`implementation-workflow` Skillの`Resume Protocol`に従います。

Issue本文やCheckpointだけを信用してコード変更を始めず、必ずRepositoryの現在状態と照合します。

### Pull Request linkage

Pull Requestは対応Issueを明示的に参照します。

IssueをPR mergeで完了扱いにできる場合は、Repositoryの運用に応じて`Closes #<issue>`等を使用します。
複数PRや後続作業が残る場合は、誤ってIssueをCloseしないよう`Refs #<issue>`等を使用します。

### Issue Close

IssueをCloseする前に以下を確認します。

- Acceptance Criteriaを満たしている
- 必要なVerificationが完了している、または未実施理由が記録されている
- Current-state Documentationが最終実装と一致している
- 必要なADRが作成・更新されている
- 必要なRelease Logが更新されている
- 残作業がある場合は別Issueとして追跡されている
- 最終Completion ReportがIssueコメントに残っている


## Documentation Format

このリポジトリの恒久ドキュメントはOpen Knowledge Format（OKF）のKnowledge Bundleとして管理します。

- Bundle root: `docs/`
- Target OKF version: `0.2`
- Current-state Documentation、Decision Record、Release Noteを同一Bundle内で管理する
- `docs/`配下の非予約`.md`ファイルはOKF Concept Documentとする
- Bundle rootの`index.md`で`okf_version: "0.2"`を宣言する

`docs/`の外側にある`AGENTS.md`、Skill、ソースコード、通常のREADME等はOKF Concept Documentとして扱いません。

---

## ドキュメント構成

このリポジトリでは、以下を標準構成とします。

```text
docs/
├── index.md
│
├── current/
│   ├── index.md
│   ├── business-requirements.md
│   ├── architecture.md
│   ├── features/
│   │   ├── index.md
│   │   ├── ui.md
│   │   ├── backend.md
│   │   └── api.md
│   └── infrastructure.md
│
├── decisions/
│   ├── index.md
│   ├── ADR-0001-*.md
│   └── ...
│
└── releases/
    ├── index.md
    └── log.md
```

必要に応じてCurrent-state Documentationをより細かなConceptへ分割できます。
その場合も、関連`index.md`から辿れる構成を維持してください。

---

## Bundle Root Index

`docs/index.md`はBundleの入口です。

先頭に以下を記載します。

```yaml
---
okf_version: "0.2"
---
```

本文では少なくとも以下へ誘導します。

- `current/` — 現在状態
- `decisions/` — 設計上の意思決定履歴
- `releases/` — リリース履歴

Bundle root以外の`index.md`にはfrontmatterを付けません。

---

## Current-state Documentation

現在状態のSource of Truthは以下です。

- ビジネス要件: `docs/current/business-requirements.md`
- アーキテクチャ: `docs/current/architecture.md`
- UI機能: `docs/current/features/ui.md`
- Backend機能: `docs/current/features/backend.md`
- API: `docs/current/features/api.md`
- インフラ: `docs/current/infrastructure.md`

Decision RecordやRelease Logから現在状態を推測せず、上記のCurrent-state Documentationを優先してください。

各ファイルにはOKF frontmatterを付与します。

推奨type:

```text
business-requirements.md -> Business Requirements
architecture.md          -> Architecture
features/ui.md            -> UI Capability
features/backend.md       -> Backend Capability
features/api.md           -> API Contract
infrastructure.md         -> Infrastructure
```

---

## OKF Metadata Policy

### 必須

Concept Documentでは`type`を必須とします。

### 原則付与

以下は検索性・Progressive Disclosureのため原則付与します。

- `title`
- `description`
- `tags`（有用な場合）

### Lifecycle

OKF lifecycleの`status`は以下のみを使用します。

- `draft`
- `stable`
- `deprecated`

未指定時は`stable`として扱います。

### Provenance / Trust / Freshness

以下は実データがある場合のみ使用します。

- `generated`
- `verified`
- `sources`
- `stale_after`

AI Agentは、人間による確認、source、actor、時刻、staleness期限を推測・捏造してはいけません。

このリポジトリでは、AI AgentがConceptを意味のある形で変更した場合、既存のhuman verificationがその変更後の内容を確認したと誤解されないように扱います。
必要に応じて再レビュー対象としてCompletion Reportへ明示してください。

---

## Link Policy

Knowledge Bundle内のConcept間リンクは、原則bundle-relative linkを使用します。

例:

```markdown
[Architecture](/current/architecture.md)
[Authentication Decision](/decisions/ADR-0012-authentication.md)
```

`docs/`をbundle rootとするため、`/docs/current/...`とは書きません。

Conceptの追加・移動・削除・deprecated化を行った場合は、関連する`index.md`を更新します。

---

## Decision Record

Decision Recordは以下へ保存します。

```text
docs/decisions/
```

ファイル名は以下の形式を使用します。

```text
ADR-XXXX-short-title.md
```

OKF frontmatterでは以下を使用します。

```yaml
---
type: Decision Record
title: "ADR-XXXX: <title>"
description: <one-line summary>
tags: [decision]
status: stable
decision_status: accepted
---
```

ADR固有の状態は`decision_status`で管理し、OKF lifecycleの`status`へ`accepted`や`superseded`を設定してはいけません。

推奨`decision_status`:

- `proposed`
- `accepted`
- `superseded`
- `deprecated`
- `rejected`

Superseded時の例:

```yaml
status: deprecated
decision_status: superseded
superseded_by: /decisions/ADR-XXXX-replacement.md
```

### このリポジトリ固有の承認ルール

Level 1 — Architecture Decisionは、実装前に人間の確認を必須とします。

Level 2 — Design Decisionは、Skillの基準に従ってADR要否を判断します。
ただし、以下へ重大な影響を与える場合は実装前に人間へ確認します。

- セキュリティ
- データ整合性
- 可用性
- 外部公開API
- インフラコスト
- 外部サービスへの強い依存

---

## Release Note

Release NoteはOKF reserved fileである以下へ記録します。

```text
docs/releases/log.md
```

`log.md`にはfrontmatterを付けません。

以下の形式を使用します。

```markdown
# Release Log

## v0.2.0

- **Added**: ...
- **Changed**: ...
- **Fixed**: ...
- **Deprecated**: ...
```

見出しはバージョンタグ名とし、新しいバージョンを上に追加します。
作成タイミング・差分の取り方・初回タグの扱いは`implementation-workflow` Skillに従います。
関連するCurrent-state ConceptやADRがある場合はMarkdown linkを付けます。

既存の日付見出し（`## YYYY-MM-DD`）は、初回バージョンタグ作成まで残してよい。初回タグ作成時に無からの差分として畳み込む。

---

## Index Maintenance

以下の`index.md`は維持対象です。

- `docs/index.md`
- `docs/current/index.md`
- `docs/current/features/index.md`
- `docs/decisions/index.md`
- `docs/releases/index.md`

Conceptを追加・移動・削除・deprecated化した場合は、同じ変更の中で関連indexを更新します。

各エントリには可能な限り、Conceptのfrontmatter `description`と整合する短い説明を付けます。

---

## OKF Validation

リポジトリにOKF validatorまたはdocumentation check commandが定義されている場合、実装完了前に実行します。

最低限、以下を検証対象とします。

- `docs/`配下の非予約`.md`にparse可能なYAML frontmatterがある
- `type`が存在し空でない
- root以外の`index.md`にfrontmatterがない
- `log.md`の見出しがバージョンタグ降順（新しいバージョンが上）として成立している。レガシー日付見出しがある場合は validator の規則に従う
- 主要cross-linkのリンク切れがない
- indexとConceptの不整合がない

具体的なコマンドは「リポジトリ固有の技術ルール」に定義します。

---

## リポジトリ固有の技術ルール

```text
Frontend:
- Framework: Chainlit 2.x (`src/chat_ui/`)
- Package manager: uv

Backend:
- Runtime: Python 3.12
- Framework: FastMCP 3.x (Streamable HTTP), SearchService in `src/knowledge_mcp/`
- Database: PostgreSQL 17 + pgvector (app compose)

Infrastructure:
- Platform: Docker Compose
- IaC: `infra/app/compose.yml`, `infra/langfuse/docker-compose.yml` + `network.yml`, `infra/langflow/compose.yml`
- Orchestration: `make -C infra up|down|migrate|seed`。Langflow は `make -C infra langflow-up|langflow-down|ingest-langflow|import-langflow`（デフォルト `up` には含めない）

Validation:
- Test: `uv run pytest`
- Lint: `uv run ruff check src tests scripts`
- Build: `docker compose -f infra/app/compose.yml build`
- OKF: `uv run python scripts/validate_okf.py`
- Local stack: `make -C infra up && make -C infra seed`
```

Coding conventions:

- TDD for SearchService and trace propagation tests
- Langfuse SDK initializes before FastMCP import in both Chainlit and MCP server processes
- Do not log API keys, embeddings, or full document bodies in spans
- MCP tools are read-only search; system ingest via `scripts/seed.py`, `scripts/run_langflow_ingest.py`, and `scripts/import_langflow.py`
- Langflow is an optional ingest sidecar; it writes to its own Collection. A host adapter copies chunks into app `documents`. SearchService does not read LangChain / Langflow Collection tables

Human approval:

- Level 1 architecture ADRs (0001–0005) were accepted with the implementation plan; confirm before production use outside local verification

---

## `AGENTS.md` に記載するもの

- このリポジトリ固有のディレクトリ構成
- 採用するOKF versionとBundle root
- Current-state Documentationの実際のパス
- ADR / Release Logの保存先
- 維持する`index.md`の範囲
- 利用技術・Framework
- Build / Test / Lint / OKF validationコマンド
- Deploymentルール
- Coding Convention
- 禁止事項
- Human Approvalが必要な操作
- GitHub Issue / PRの命名・Label・Project・Milestone等のRepository固有ルール

Implementation Planの作成方法、ADR候補の一般基準、実装・検証・Documentation Reconciliationの共通ワークフローは`AGENTS.md`に重複記載せず、`implementation-workflow` Skillへ集約します。
