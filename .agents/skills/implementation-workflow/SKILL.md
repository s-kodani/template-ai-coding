---
name: implementation-workflow
description: コードの実装・変更・リファクタリング・機能追加を行う際に、GitHub Issueによる作業トラッキングとSession Checkpoint、Implementation Planの作成（grill-me / grilling による計画 refinement を含む）、ADR候補の検出、実装・検証、OKFベースのCurrent-state Documentation・Decision Record・Release Note（未確定 `## v?.?.? (未確定)` および SemVer 確定見出し）への整合までを一貫して進めるためのワークフロー。実装スピードを維持しながら、セッションを跨いだ再開可能性、設計上の意思決定の追跡可能性、AIが利用しやすい知識構造、恒久ドキュメントの正確性を確保したい場合に使用する。
---

# 実装ワークフロー Skill

## 目的

このSkillは、アプリケーションコードの実装、変更、リファクタリング、拡張を行う際に使用します。

実装スピードを維持しながら、以下を確保することを目的とします。

- 実装品質
- アーキテクチャの一貫性
- 重要な設計上の意思決定の追跡可能性
- Current-state Documentationの正確性
- AI Agentが段階的に探索できる知識構造
- Coding Agentのセッションを跨いだ安全な作業再開
- GitHub Issue上での追記型の作業履歴とCheckpoint
- 完了前の確実な検証

Implementation Plan（実装計画）は一時的な作業成果物です。
明示的な指示がない限り、リポジトリへコミットしてはいけません。

恒久的に残す情報は、以下へ整理します。

- Current-state Documentation
- Architecture / Design Decision Record（ADR）
- Release Note

リポジトリがOpen Knowledge Format（OKF）を採用している場合、これらの恒久ドキュメントは`AGENTS.md`で指定されたOKF Knowledge Bundleとして管理します。

---

## 基本原則

1. **実装前に理解する**
   - 関連コード、Current-state Documentation、制約、過去の意思決定を理解する前に実装を始めない。

2. **コード変更前に計画する**
   - コードを編集する前に、必ずImplementation Planを作成する。
   - Implementation Planは一時的なものであり、原則リポジトリには保存しない。

3. **計画と恒久知識を分離する**
   - Implementation Planは「どのように実装する予定か」を示す。
   - Current-state Documentationは「現在何が正しいか」を示す。
   - Decision Recordは「なぜ重要な設計判断をそのように決めたか」を示す。
   - Release Noteは「どのバージョンで何が変わったか」を示す。実装完了時点では `## v?.?.? (未確定)` 見出し下へ追記し、バージョンタグ確定時に見出しを確定版 SemVer へ置き換える。

4. **Current-state Documentationを現在状態のSource of Truthとする**
   - Decision RecordやRelease Noteだけから現在状態を推測しない。

5. **実態に合わせて計画を変更する**
   - Implementation Planはガイドであり、恒久的な仕様書ではない。
   - コード調査、テスト結果、技術制約、ユーザーフィードバックによるPlan Driftを許容する。

6. **実装後に恒久知識を再構成する**
   - 当初計画ではなく、最終実装を基準にドキュメントを整合させる。
   - 一時的な検討過程をそのまま恒久ドキュメントへ残さない。

7. **OKFではConcept単位で知識を管理する**
   - 1つのMarkdownファイルは、原則1つの明確なConceptを表す。
   - 巨大なドキュメントへ知識を集約しすぎず、独立して探索・参照する価値がある単位で分割する。
   - 一方で、局所的な実装詳細まで過剰にConcept化しない。

8. **GitHub Issueを作業のCoordination Ledgerとして使用する**
   - Issue本文はGoal、Scope、Acceptance Criteriaなど、現在有効な作業契約を表す。
   - 実装途中の進捗、検証結果、未解決事項、Session CheckpointはIssueコメントとして追記する。
   - IssueをCurrent-state DocumentationやADRの代替として扱わない。

9. **セッション終了時に再開可能なCheckpointを残す**
   - 作業途中でセッションを終了する場合、別セッションがRepositoryの現在状態と照合して漏れなく再開できる情報をIssueコメントへ残す。
   - Checkpointは事実ベースで記録し、陳腐化したImplementation Planをコピーしない。

---

# ワークフロー


## Phase 0: Work Item Setup — GitHub Issueの確認・紐付け

実装、変更、リファクタリング、機能追加などの作業に着手する際、`AGENTS.md`でGitHub Issue利用が指定されている場合は、コード変更前に作業Issueを確定します。

### 既存Issueの確認を必須とする

新しいIssueを起票する前に、**すでにユーザーが手動で作成したIssueが存在する可能性を必ず確認**します。

ユーザーから対象Issueが明示されていない場合は、Issueを新規作成する前に、以下の趣旨でユーザーへ確認します。

> この作業に対応するGitHub Issueはすでに作成済みですか？  
> 作成済みの場合はIssue番号またはURLを指定してください。未作成の場合は新規Issueとして進めます。

ルール:

- 既存Issueの有無を確認せず、新規Issueを作成してはいけない。
- ユーザーが既存Issueを指定した場合は、そのIssueを作業Issueとして使用する。
- ユーザーが「未作成」と回答した場合にのみ、新規Issueを起票する。
- ユーザーが現在の依頼内ですでにIssue番号またはURLを指定している場合は、再確認せずそのIssueを使用する。
- 既存Issueが作業目的と明らかに一致しない場合は、勝手に流用せずユーザーへ確認する。
- Issueの重複作成を避けることを優先する。

Issueは実装計画の保存場所ではありません。
Issueは以下の2つの役割を持ちます。

1. **Issue本文** — 現在有効な作業契約
2. **Issueコメント** — 追記型の作業履歴、Checkpoint、重要な変更経緯

### Issue本文

本文には、時間経過で陳腐化しにくい情報だけを記載します。

推奨構成:

```markdown
## Goal

この作業で達成すること。

## Background / Context

なぜこの作業が必要か。

## Scope

### In Scope
- ...

### Out of Scope
- ...

## Acceptance Criteria

- ...
- ...

## Constraints

- ...

## Related Knowledge

- Current-state Documentation:
- ADR:
- Related Issue / PR:
```

本文へ以下を保存しません。

- 詳細なImplementation Plan
- 現在の進捗率
- 「次に何をするか」の一時的メモ
- 一時的な調査結果
- 未整理のScratch Note
- Session固有の状態

### Issue本文の鮮度維持

Goal、Scope、Acceptance Criteria、Constraintsなど、**作業契約そのものが変更された場合はIssue本文を更新**します。

ただし、履歴を失わないため、同じタイミングでIssueコメントへ以下を残します。

```markdown
## Scope / Requirement Change

### Changed
- 変更した内容

### Reason
- 変更理由

### Impact
- Implementation / Verification / Documentationへの影響
```

Issue本文は常に「現在有効な作業契約」を表し、変更履歴はコメント側へ残します。

### Issueコメントの追記原則

作業履歴は原則Append-onlyで扱います。

過去のCheckpointコメントを後から現在状態に合わせて書き換えてはいけません。
誤りが判明した場合は、新しいコメントで訂正します。

---

## Phase 1: Understand — 現在状態の理解

Implementation Plan作成前に以下を確認します。

1. `AGENTS.md` などのリポジトリ固有ルール
2. 関連ソースコード
3. 関連するCurrent-state Documentation
4. 関連する既存ADR
5. アーキテクチャ上の制約とシステム境界
6. 影響を受けるモジュール、API、データ、インフラ、外部連携
7. 既存のテスト・検証手段
8. OKFを採用している場合は、Knowledge Bundleの`index.md`と関連Conceptのcross-link

### OKFでの探索順序

OKF Knowledge Bundleでは、可能な限り以下の順序で必要な知識だけを読みます。

1. Bundle rootの`index.md`
2. 関連ディレクトリの`index.md`
3. 関連Concept Document
4. Conceptからリンクされた関連Concept
5. 必要な場合のみDecision RecordやRelease Log

全ドキュメントを無条件に読み込むのではなく、`index.md`によるProgressive Disclosureを優先します。

ADRは判断理由の履歴であり、現在状態はCurrent-state Documentationを優先します。

---

## Phase 2: Implementation Plan — 実装計画の作成

コード変更前に必ずImplementation Planを作成します。

Implementation Planは会話または一時作業コンテキストに置き、明示的な依頼がない限りファイル化・コミットしません。

GitHub Issueを使用していても、Implementation Plan全文をIssue本文へ転記しません。Planは陳腐化することを前提とし、セッション間で必要な現在状態はWork Checkpointとして別途記録します。

最低限、以下を含めます。

### Goal

何を実現するか。

### Current State

既存実装・Current-state Documentation・関連ADRを確認して判明したこと。

### Scope

影響する機能、モジュール、API、データ、インフラ、外部連携、ドキュメント。

### Implementation Approach

主要な変更方針、順序、互換性、移行方針。

### Files / Components

主な変更対象。

### Decision Candidates

ADRが必要になる可能性のある設計判断。

### Documentation Impact

最終実装によって更新が必要になる可能性のあるOKF Concept、`index.md`、Decision Record、Release Log（`## v?.?.? (未確定)` セクション）を列挙する。

この時点では更新予定であり、最終的な更新対象は実装後に再判定します。

### Risks / Open Questions

技術的不確実性、互換性、移行、データ、セキュリティ、性能、運用上のリスク。

### Verification

Test、Type Check、Lint、Build、Migration、Infrastructure、手動確認など。

### Plan Refinement — grill-me / grilling による計画の練り上げ

下書きの Implementation Plan を Phase 3 Decision Check または実装へ進める前に、必ず `grill-me` スキルを使って計画をストレステストします。

1. 上記の Implementation Plan 項目で下書きを作成する。
2. `grill-me` スキルを読む。shim の指示どおり `grilling` スキルを読み、そのインタビュー手法に従う。
3. `grilling` のルールどおり、design tree の **frontier** を **rounds** で問い、各問いに推奨案を付ける。事実の調査は Agent の責務、判断はユーザーの責務とする。
4. frontier が空になり、ユーザーが共有理解を確認するまで Phase 3 / 実装へ進まない。ユーザーが打ち切った場合のみ、その時点の合意で進む。
5. grill セッション後、確定した内容を反映して Implementation Plan を更新する。
6. 軽微な変更でも省略しない。単純な計画なら frontier が早く空になる想定でよい。

`grill-me` の `disable-model-invocation: true` は、ユーザーが明示しない限り Agent が勝手に発火しないための制約です。`implementation-workflow` が Phase 2 で `grill-me` を呼び出すことは、この Skill からの正規の呼び出しです。`grilling` は `grill-me` からの委譲先として使用します。

`grilling` の rounds / frontier 手順を本 Skill へ複製してはいけません。入口は `grill-me`、手法は `grilling` に任せます。

---

## Phase 3: Decision Check — 意思決定の判定

以下の1つ以上に該当する場合、その判断はADR候補です。

- 複数の合理的な選択肢が存在する
- 複数モジュールまたはシステム境界に影響する
- 後から変更することが難しい、または高コスト
- 長期的なアーキテクチャ制約を生む
- データ所有権またはデータライフサイクルを変更する
- APIまたは外部連携境界を変更する
- セキュリティ、可用性、性能、コストへ重大な影響を与える
- 主要な外部サービスまたはインフラ依存を導入する
- 将来の開発者が「なぜこの設計なのか」と疑問を持つ可能性が高い

原則ADR対象外:

- 命名
- 小規模なリファクタリング
- 局所的なコンポーネント分割
- 一時的な実装詳細
- 小規模で容易に差し替え可能なライブラリ利用
- コード自体から十分に理解できる実装詳細

### Decision Level

#### Level 1 — Architecture Decision

例: DB、認証、認可、マルチテナンシー、API方式、イベント方式、クラウド戦略、主要データ境界、サービス境界。

- ADRを作成または提案する。
- `AGENTS.md`で承認が必要とされている場合は実装前に確認する。

#### Level 2 — Design Decision

例: キャッシュ、リトライ、Queue、State Management、Consistency、Error Handling、重要ライブラリ、Background Job。

- ADR候補として扱う。
- 長期的影響が大きい場合はADRを作成する。

#### Level 3 — Implementation Decision

例: 関数分割、変数名、局所的な構造、小規模なリファクタリング。

- ADR不要。

---

## Phase 4: Implement — 実装

以下に従って実装します。

- 合意された実装方針
- `AGENTS.md`のリポジトリ固有ルール
- Current-state Documentation
- 既存アーキテクチャ制約
- 適用されるADR

実装中は以下を守ります。

- 無関係なリファクタリングを避ける
- 不必要なスコープ拡大を避ける
- 実装と同時にテストを更新する
- 新たなアーキテクチャ制約を表面化する
- 新しい事実に応じてImplementation Planから逸脱してよい

Implementation Planは履歴文書ではありません。
コード調査、テスト、技術制約、ユーザーフィードバックで陳腐化しても、同期維持のためだけに更新しません。

---

## 実装中のDecision Detection

重要な設計判断が実装中に発生した場合:

1. 単なる実装詳細として扱わない。
2. Level 1 / 2 / 3 に分類する。
3. ADR候補基準で評価する。
4. 必要に応じて人間へ表面化する。
5. 必要ならADRを作成または更新する。
6. 必要な承認後に実装を継続する。

---


## Session Handoff Protocol — セッション終了時のCheckpoint

実装途中でCoding Agentのセッションを終了する場合、`AGENTS.md`で指定されたGitHub IssueへWork Checkpointコメントを追加します。

Checkpointの目的は、**別セッションが元の会話履歴を持たなくても、安全に現在状態を復元して作業を再開できること**です。

### Checkpointを残すタイミング

最低限、以下ではCheckpointを残します。

- 作業途中でセッションを終了する前
- 別Agent / 別セッションへ引き継ぐ前
- 大きな実装マイルストーンを完了した後で、そのまま作業を中断する場合
- 未解決のDesign Decisionや外部状態を残したまま作業を中断する場合

細かなコード変更ごとにCheckpointを追加する必要はありません。

### Checkpoint Format

Issueコメントには、機械的に検出しやすいmarkerを付けます。

```markdown
<!-- agent-work-checkpoint:v1 -->

## Work Checkpoint

### Repository State
- Branch: `<branch>`
- HEAD: `<commit-sha>`
- Working tree: `<clean | modified>`
- Related PR: `<PR or none>`

### Goal
- 現在取り組んでいるGoal

### Completed
- 完了した作業

### In Progress
- 実装途中の作業
- どこまで完了しているか

### Remaining
- 未着手または未完了の作業

### Changed Files / Components
- 主な変更箇所

### Decisions Made
- このセッションで確定した重要な判断
- ADRへ昇格済みの場合はリンク

### Pending Decisions
- 未確定の判断
- 候補、制約、ADR Level / Candidate状態

### Verification
- 実行済み検証と結果
- 未実施の検証

### External State
- Migration適用状況
- Cloud / SaaS / Feature Flag / Secret等、Repository外の状態
- 該当なしの場合は `None`

### Blockers / Known Issues
- 失敗中のTest
- 未解決問題
- 再現条件

### Next Action
1. 次セッションが最初に行う具体的な作業
2. ...
```

値を確認できない項目は推測せず、`unknown`または`not checked`と記載します。

### Checkpointの記録原則

Checkpointでは**予定ではなく事実**を優先します。

悪い例:

```text
次はAPIとUIを実装する予定。
```

良い例:

```text
Backend APIは実装済み。
UIは未着手。
Integration Testは未実施。
次はUI実装前にAPI contractを確認する。
```

Implementation PlanをCheckpointへそのままコピーしてはいけません。

---

## Resume Protocol — 別セッションでの再開

既存Issueの途中作業を別セッションで再開する場合、コード変更前に以下を行います。

1. `AGENTS.md`と適用Skillを読む。
2. GitHub Issue本文から現在有効なGoal / Scope / Acceptance Criteria / Constraintsを確認する。
3. 最新の`agent-work-checkpoint:v1`コメントを特定する。
4. そのCheckpoint以降に追加された人間・Agentのコメントをすべて確認する。
5. Repositoryの現在状態を確認する。
   - current branch
   - current HEAD
   - `git status`
   - relevant `git diff`
   - recent commits
   - related PR state
6. CheckpointのBranch / HEAD / Working Tree情報と現在状態を比較する。
7. Changed Files / Completed / In Progress / Remainingが実コードと整合しているか確認する。
8. Pending Decisionsが未解決のままか確認する。
9. External Stateが現在も有効か、確認可能な範囲で検証する。
10. 現在状態を基準に新しいImplementation Planを作成し、`grill-me` / `grilling` による Plan Refinement を行う。
11. 必要に応じて短いResumeコメントをIssueへ残してから実装を再開する。

### Source of Truth

再開時の優先順位は以下です。

```text
Current Repository State / Code
        ↓
Current-state Documentation
        ↓
Accepted ADR
        ↓
Current GitHub Issue Body
        ↓
Latest Checkpoint + Subsequent Comments
        ↓
Old Implementation Plan
```

CheckpointはNavigation / Handoff情報であり、コードのSource of Truthではありません。

Checkpoint作成後にRepositoryが変更されている場合は、Checkpointをそのまま信用せず差分を調査します。

### Subsequent Comment Rule

最新Checkpointの後にコメントが存在する場合、それらを無視して再開してはいけません。

特に以下はCheckpointより後の指示を優先します。

- Scope変更
- Acceptance Criteria変更
- 人間による設計判断
- Review feedback
- Blocker解消情報

ScopeやAcceptance Criteriaが変更されているのにIssue本文へ反映されていない場合は、本文を最新状態へ更新し、変更履歴をコメントとして残してから作業を進めます。

---

## Phase 5: Verify — 検証

実装完了前に、変更内容に応じた検証を行います。

例:

- Unit Test
- Integration Test
- End-to-End Test
- Type Check
- Lint
- Build
- Migration Validation
- Infrastructure Validation
- Security-sensitive Behavior Check
- Manual Behavior Check

実行していない検証を成功済みと報告してはいけません。

OKFを採用している場合、実装検証に加えてDocumentation Validationも実施します。

### OKF Documentation Validation

最低限、以下を確認します。

- Knowledge Bundle配下の非予約`.md`ファイルにYAML frontmatterが存在する
- Concept Documentの`type`が空でない
- YAMLがparse可能である
- `index.md` / `log.md`をConcept Documentとして扱っていない
- 新規・移動・削除・deprecated化したConceptが関連`index.md`へ反映されている
- 内部cross-linkが意図したConceptを指している
- Current-state Documentationが最終実装と一致している
- `verified`を実際の確認なしに追加していない
- `generated` / `sources` / `stale_after`等を使用する場合、その内容を捏造していない

---

## Phase 6: Documentation Reconciliation — ドキュメント整合

実装と検証の完了後、最終実装と恒久ドキュメントを照合します。

Implementation Planをそのままコピーしてはいけません。

| 問い | 保存先 |
|---|---|
| 現在何が正しいか？ | Current-state Documentation / OKF Concept |
| なぜこの設計を選んだか？ | Decision Record / OKF Concept |
| 何が変わったか？ | Release Note / OKF `log.md`（`## v?.?.? (未確定)` セクション） |
| どのような過程で実装したか？ | 原則破棄 |

Phase 6 では Current-state Documentation、ADR、Release Log を最終実装と整合させます。Release Log には観測可能な変更を `## v?.?.? (未確定)` 見出し下へ追記します。`git tag` の作成や見出しの SemVer 確定は、ユーザーがリリースまたはバージョンタグ作成を依頼したときのみ行います。

---

## OKF Documentation Rules

リポジトリがOKFを採用している場合、`AGENTS.md`で指定されたKnowledge Bundleに対して以下を適用します。

### 1. Concept Document

予約ファイル以外のMarkdownはConcept Documentとして扱います。

各Concept Documentには、最低限以下のfrontmatterを持たせます。

```yaml
---
type: <Concept Type>
title: <Human-readable title>
description: <One-line summary>
---
```

`type`は必須です。
`title`と`description`は、AI Agentによる検索・`index.md`生成・人間の可読性向上のため原則付与します。

### 2. 推奨Concept Type

Current-state Documentationでは、プロジェクトに応じて以下のような明確なtypeを使用します。

- `Business Requirements`
- `Architecture`
- `UI Capability`
- `Backend Capability`
- `API Contract`
- `Infrastructure`
- `Decision Record`
- その他、対象Conceptを自己説明できるtype

typeを過度に細分化する必要はありません。
未知のtypeを許容できる前提で、内容を自己説明できる名称を選びます。

### 3. Frontmatter Metadata

必要に応じて以下を利用します。

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
stale_after: <YYYY-MM-DD>
sources:
  - id: <stable-source-id>
    resource: <URI or path>
    title: <source title>
```

ルール:

- `status`はOKF lifecycleとして`draft` / `stable` / `deprecated`を使用する。
- `generated`は現在の内容を誰・何が生成または最後に意味のある変更をしたかを表す。実際のactorや時刻を特定できない場合は捏造しない。
- `verified`は実際に内容を確認したactorだけを記録する。AIが人間による確認を推測してはいけない。
- `stale_after`は実際の見直し期限・鮮度要件がある場合のみ設定する。便宜的な期限を作らない。
- `sources`は外部・内部の根拠資料から知識を導出した場合に使用する。
- 特定の記述を特定sourceへ帰属させる必要がある場合は、`sources[].id`とMarkdown footnoteを対応させる。

### 4. Actor Convention

actorを記録する場合は、以下を使用します。

- AI Agent / Tool: `<producer>/<version>`
- Human: `human:<id>`
- Automated Process: `process:<id>`

実際に識別できないactorを作らないでください。

### 5. Cross-link

Concept間の関係は通常のMarkdown linkで表現します。

OKF Bundle内では、移動への耐性を高めるためbundle-relative linkを優先します。

例:

```markdown
[Architecture](/current/architecture.md)
[Authentication Decision](/decisions/ADR-0012-authentication.md)
```

リンク自体に関係種別を埋め込まず、周囲の文章で「depends on」「supersedes」「implemented by」などの関係を説明します。

### 6. `index.md`

`index.md`はProgressive Disclosureの入口として扱います。

- Bundle rootと主要ディレクトリでは、`AGENTS.md`で指定された範囲の`index.md`を維持する。
- Conceptの追加、移動、削除、deprecated化に応じて更新する。
- エントリには可能な限りConceptの`description`を付ける。
- root `index.md`以外ではfrontmatterを付けない。
- root `index.md`では、リポジトリが対象とするOKF versionを`okf_version`として宣言できる。

### 7. `log.md` / Release Note

OKFの`log.md`をRelease Noteとして使用するリポジトリでは、以下を守ります。

- 先頭（または最新位置）に、未リリース変更用の **`## v?.?.? (未確定)`** 見出しを置く。確定済みバージョン見出しはその下に並べ、新しいバージョンを上にする
- 確定済み見出しはバージョンタグ名（Semantic Versioning、例: `## v1.0.0`）。git タグ名と `log.md` 見出しは同じ SemVer 文字列を使う（例: タグ `v1.0.0`、見出し `## v1.0.0`）
- `## v?.?.? (未確定)` は git タグではなく、次回リリース候補の変更を蓄積するプレースホルダー見出しである
- 日付見出しは新規に使わない（レガシー日付見出しが残るリポジトリでは、`AGENTS.md`とvalidatorの規則に従う）
- 未確定セクションには、前回確定タグ（または初回リリース前であれば空）以降に観測可能な変更を追記する
- バージョンタグ確定時は、`## v?.?.? (未確定)` を確定 SemVer 見出しへ置き換え、必要なら新しい空の `## v?.?.? (未確定)` を先頭へ追加する
- 初回タグ確定時は、未確定セクションの内容を空（無）からの差分として扱ってよい
- ユーザー・運用者・外部連携先から見て観測可能な変更を記録する
- 実装手順や一時的なImplementation Planは記録しない
- 関連ConceptやDecision RecordへMarkdown linkを張る

### 8. ADRとOKF lifecycleの分離

OKFの`status`はConcept自体のlifecycleを表すため、ADR固有の状態管理に流用してはいけません。

ADRではproducer-defined fieldとして`decision_status`を使用します。

例:

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

推奨`decision_status`:

- `proposed`
- `accepted`
- `superseded`
- `deprecated`
- `rejected`

置き換えられたADRでは、例えば以下のように表現します。

```yaml
status: deprecated
decision_status: superseded
superseded_by: /decisions/ADR-0024-new-authentication.md
```

過去ADRは削除せず、履歴として維持します。

---

## Current-state Documentation

最終実装によって以下が変更された場合、該当するOKF Conceptを更新します。

- ビジネス上の振る舞い
- システムアーキテクチャ
- UI機能
- Backend機能
- API
- データモデル
- 外部連携
- インフラ
- 運用上の振る舞い

Current-state Documentationには、最終的に実装された状態を記述します。

破棄されたImplementation Planの内容を書いてはいけません。

Conceptが複数の独立した知識を抱え、AIが毎回全文を読む必要が生じている場合は、適切なConcept単位への分割を検討します。

---

## Decision Record

最終実装にADR基準を満たす恒久的な意思決定が含まれる場合、Decision Recordを作成または更新します。

本文には通常、以下を含めます。

- Context
- Decision
- Alternatives Considered
- Rationale
- Consequences
- Related Decisions

ADR固有の状態は`decision_status`で管理し、OKF lifecycleの`status`とは分離します。

---

## Release Note

Release Note は Phase 6（Documentation Reconciliation）で更新します。観測可能な変更は `## v?.?.? (未確定)` 見出し下へ追記します。`git tag` の作成と見出しの SemVer 確定は、ユーザーがリリースまたはバージョンタグ作成を依頼したときのみ行います。

### 未確定見出し — `## v?.?.? (未確定)`

- `log.md` 先頭（確定済みバージョンより上）に置くプレースホルダー見出し
- git タグはまだ存在しない。文字列 `v?.?.?` は SemVer 未確定を表す
- 実装完了ごとに、当該作業の観測可能な変更をこのセクションへ追記する
- 同時に存在する未確定見出しは 1 つだけ
- 確定済みバージョン見出し（例: `## v1.0.0`）より上に置く

例:

```markdown
# Release Log

## v?.?.? (未確定)

- **Added**: ...
- **Changed**: ...

## v1.0.0

- **Added**: ...
```

`log.md` が存在しない、または未確定見出しがない場合は、Phase 6 で `# Release Log` と `## v?.?.? (未確定)` を作成してから追記します。

### 作成タイミング

| タイミング | 操作 |
|---|---|
| Phase 6（通常の実装完了） | 観測可能な変更を `## v?.?.? (未確定)` へ追記 |
| ユーザーがリリース / バージョンタグ作成を依頼 | 未確定見出しを確定 SemVer へ置換、`git tag` 作成、必要なら新しい未確定見出しを先頭へ追加 |

- ユーザー依頼がない限り、Agent が勝手に `git tag` を切ったり、未確定見出しを確定 SemVer へ置き換えたりしてはいけない
- 観測可能な変更がない実装では Release Log を更新しない

### 差分の取り方

**Phase 6（未確定セクションへの追記）**

- 当該実装で観測可能な **Added** / **Changed** / **Fixed** / **Deprecated** だけを要約する
- 実装手順や Implementation Plan は記録しない
- 既存の未確定エントリと重複しないよう、同じ変更を二重に書かない

**バージョンタグ確定時**

- 未確定セクションの内容を確定 SemVer 見出しへ移す（見出しを置換）
- 必要に応じて、前回確定タグ..HEAD の差分を `git log` と `git diff` で照合し、未確定セクションの記載漏れを補う
- 確定後、次の変更蓄積用に新しい `## v?.?.? (未確定)` を先頭へ追加してよい

### 初回タグ

- バージョンタグが1つもない場合でも、Phase 6 から `## v?.?.? (未確定)` へ変更を蓄積する
- 初回タグ確定時は、未確定セクションの内容を空（無）からの差分として扱う
- 存在しない旧バージョンを捏造しない
- レガシーの日付見出しエントリがある場合、初回タグ確定時に未確定セクションの内容とあわせて整理してよい

### 見出し形式

- 未確定: `## v?.?.? (未確定)`（固定。バリエーションを増やさない）
- 確定済み: そのバージョンタグ名（Semantic Versioning、例: `## v1.0.0`）
- 新しいバージョン（未確定または確定済み）を上にする

### バージョンタグ — Semantic Versioning

バージョンタグは [Semantic Versioning 2.0.0](https://semver.org/)（SemVer）に従います。

形式は `MAJOR.MINOR.PATCH` です。git タグには慣例として `v` 接頭辞を付けます（例: `v1.0.0`）。`log.md` の見出しも同じ文字列を使います（例: `## v1.0.0`）。

| 桁 | 上げるタイミング（例） |
|---|---|
| MAJOR | 後方互換性のない API や観測可能な振る舞いの変更 |
| MINOR | 後方互換性を保った機能追加 |
| PATCH | 後方互換性を保ったバグ修正 |

- 初回リリースは通常 `v1.0.0` とする（`v0.x` は pre-release や PoC 期間に限定）
- プレリリース識別子（`-alpha.1` 等）やビルドメタデータ（`+build.1` 等）は SemVer 規則に従い、必要な場合のみユーザーと合意して使う
- 次バージョン番号が不明な場合は、差分の性質（breaking / feature / fix）をユーザーへ確認してから決める
- ユーザー依頼がない限り Agent が勝手にバージョン番号を決めて `git tag` してはいけない

### 記載要否

通常Release Noteに含める例:

- 新しいユーザー向け機能
- ビジネス上の振る舞い変更
- APIの振る舞い変更
- 運用上重要なインフラ変更
- 観測可能なバグ修正
- 互換性変更
- 運用影響のあるMigration

通常Release Noteに含めない例:

- 外部影響のない内部リファクタリング
- 命名変更
- ローカルなコード整理
- テストのみの変更

対象期間は「今回の実装」単位で未確定セクションへ追記し、タグ確定時は未確定セクション全体を1つの確定バージョンとして扱います。

---

## Phase 7: Completion Report — 完了報告

実装完了時は、以下を報告します。

### Changes

実際に何を実装したか。

### Verification

実行した検証と結果。

### Documentation

関連する恒久ドキュメントの更新状況。

### GitHub Issue

GitHub Issueを使用している場合は、最終コメントとして以下を残します。

- 実際に完了したChanges
- Verification結果
- 作成・更新したADR / OKF Concept
- Release Log（`## v?.?.? (未確定)` への追記、またはタグ確定時の見出し置換）
- 残課題がある場合はそのIssueへの分離状況
- 関連PR / commit

Acceptance Criteriaを満たし、必要な恒久知識への昇格が完了したことを確認してからIssueをCloseします。

例:

```text
Documentation
- Business requirements: no change
- Architecture: updated
- UI/backend concepts: updated
- Infrastructure: no change
- ADR: ADR-0014 added
- Release log: updated under `## v?.?.? (未確定)`（または tag finalized to `vX.Y.Z`）
- OKF index: updated
- OKF validation: passed
```

---

## Temporary Artifact Rule — 一時成果物ルール

以下は原則コミットしません。

- Implementation Plan
- Scratch Note
- 中間案
- 破棄したDesign Draft
- Intermediate Reasoning
- 陳腐化したImplementation Approach

恒久的な価値がある情報だけを、Current-state Documentation、ADR、Release Noteへ昇格させます。

OKFを採用していても、一時的なImplementation PlanをKnowledge Bundleへ入れてはいけません。

GitHub IssueのCheckpointコメントは作業履歴として残して構いませんが、恒久的なArchitecture / Business / API knowledgeのSource of Truthにはしません。最終的に残すべき知識はOKF Concept、ADR、Release Logへ昇格させます。

---

## 要約

**Issueで作業契約を明確にする。  
コードを書く前に計画する。  
計画は grill-me / grilling で練る。  
セッションを跨ぐときはCheckpointを残す。  
恒久的な意思決定を検出する。  
実装して検証する。  
最終状態をOKFで構造化された恒久知識へ整合させる。  
Release Noteは Phase 6 で `## v?.?.? (未確定)` へ追記し、タグ確定時に SemVer 見出しへ置き換える（SemVer）。**
