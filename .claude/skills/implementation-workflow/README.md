# implementation-workflow

AI Coding Agentによる実装を、**高速に進めながら品質・設計判断・ドキュメント・セッション間の継続性を維持するための実装ワークフローSkill**です。

このSkillでは、Implementation Plan、GitHub Issue、Session Checkpoint、ADR、OKF（Open Knowledge Format）をそれぞれ異なる責務に分離し、AIによる開発で起こりやすい次の問題を抑えます。

- 実装計画が途中で陳腐化する
- 重要な設計判断がチャットの中だけに残る
- セッションを跨ぐと作業状況や未解決事項が抜け落ちる
- Issue本文が進捗メモで肥大化・陳腐化する
- 実装後にドキュメントが更新されず、コードと仕様が乖離する
- AIが大量のドキュメントを毎回読む必要がある

---

## 基本コンセプト

このSkillでは、開発中に生成される情報を役割ごとに分離します。

| 情報 | 役割 | 保存 |
|---|---|---|
| GitHub Issue Body | 現在有効な作業契約 | GitHub |
| GitHub Issue Comments | 作業履歴・変更履歴・Session Checkpoint | GitHub |
| Implementation Plan | 現在のセッションでの実装計画 | `.plans/` へ一時書き出し（git 管理外。コミットしない） |
| Repository / Code | 実装状態 | Git |
| Current-state Documentation | 現在何が正しいか | OKF |
| Decision Record / ADR | なぜその設計を選んだか | OKF |
| Release Log | 何が変わったか（未確定 `## v?.?.? (未確定)` および確定 SemVer 見出し） | OKF |

重要な原則は次のとおりです。

> **Planはローカル md として使い、コミットしない。  
> Issueは作業をつなぐ。  
> Codeは実装状態を表す。  
> OKFは現在の知識を表す。  
> ADRは判断理由を残す。**

---

## 解決したい課題

### Implementation Planの陳腐化

AI Codingでは、実装前に計画を作成しても、コード調査・テスト・ユーザーからの追加指示によって計画が変わることがよくあります。

そのため、このSkillではImplementation Planを必須としつつ、**恒久成果物にはしません**。

Implementation Planは `.plans/` 配下の Markdown として書き出し、必要な grilling のあとユーザー承認を得てから実装します。git 管理外の一時的な Working Artifact であり、最終的に価値のある情報だけをCurrent-state Documentation、ADR、Release Logへ昇格させます。Release Logは Phase 6 で `## v?.?.? (未確定)` 見出し下へ追記し、バージョンタグ確定時に SemVer 見出しへ置き換えます。

### セッションを跨いだ作業再開

Coding Agentのセッションを途中で終了しても、別セッションから漏れなく再開できるよう、GitHub IssueコメントへWork Checkpointを残します。

Checkpointには次のような情報を記録します。

- Branch / HEAD / Working Tree
- Completed
- In Progress
- Remaining
- Changed Files / Components
- Decisions Made
- Pending Decisions
- Verification
- External State
- Blockers / Known Issues
- Next Action

CheckpointはImplementation Planのコピーではなく、**その時点で確認できている事実**を記録します。

### GitHub Issueの陳腐化

Issue本文を日報や進捗メモとして使うと、すぐに陳腐化します。

そこで役割を分けます。

**Issue本文**

現在有効な作業契約を記載します。

- Goal
- Background / Context
- In Scope / Out of Scope
- Acceptance Criteria
- Constraints
- Related Knowledge

**Issueコメント**

履歴として追記します。

- Scope / Requirement Change
- Work Checkpoint
- Verification結果
- Review結果
- Completion Report

ScopeやAcceptance Criteriaが変わった場合は、Issue本文を現在状態へ更新し、変更理由をコメントへ残します。

これにより、

- 本文 = 現在の正しい作業定義
- コメント = Append-onlyの履歴

という構造を維持できます。

---

## GitHub Issueの扱い

作業開始時に、対象Issueがユーザーから指定されていない場合は、**新規Issueを作る前に既存Issueがあるかユーザーへ確認します**。

例:

> この作業に対応するGitHub Issueはすでに作成済みですか？  
> 作成済みの場合はIssue番号またはURLを指定してください。未作成の場合は新規Issueとして進めます。

既存Issueの確認なしに重複Issueを作成しないことが重要です。

---

## ワークフロー

```text
GitHub Issue確認 / 起票
        ↓
Understand
        ↓
Implementation Plan（`.plans/` の md へ書き出し）
        ↓
grill-me / grilling（変更強度に応じて。結果を md へ反映）
        ↓
ユーザー承認（必須。修正があれば md を更新して再承認）
        ↓
Decision Check
        ↓
Implement
        │
        ├── セッション継続
        │
        └── セッション終了
        │        ↓
        │   Work Checkpoint
        │        ↓
        │   ── 別セッション ──
        │        ↓
        │   Resume Protocol
        │        ↓
        │   Plan再生成または更新（`.plans/` の md）+ 必要なら grilling + ユーザー承認
        │
        ↓
Verify
        ↓
Documentation Reconciliation
        │
        ├── Current-state Documentation
        ├── ADR
        └── Release Log（`## v?.?.? (未確定)` へ追記）
        ↓
Completion Report
        ↓
Issue Close

（別途）バージョンタグ確定時
        ↓
未確定見出しを SemVer へ置換 + `git tag`
```

---

## Session Handoff

作業途中でセッションを終了するときは、IssueコメントへCheckpointを残します。

Checkpointには機械的に検索しやすいmarkerを付けます。

```markdown
<!-- agent-work-checkpoint:v1 -->

## Work Checkpoint

### Repository State
- Branch:
- HEAD:
- Working tree:
- Related PR:

### Goal
- ...

### Completed
- ...

### In Progress
- ...

### Remaining
- ...

### Changed Files / Components
- ...

### Decisions Made
- ...

### Pending Decisions
- ...

### Verification
- ...

### External State
- ...

### Blockers / Known Issues
- ...

### Next Action
1. ...
```

過去のCheckpointは後から書き換えず、Append-onlyの履歴として維持します。

---

## Resume Protocol

別セッションで再開するときは、Checkpointを読んですぐ実装を始めません。

まず以下を照合します。

1. `AGENTS.md` と適用Skill
2. GitHub Issue本文
3. 最新Checkpoint
4. Checkpoint以降のIssueコメント
5. Current branch / HEAD
6. `git status`
7. relevant `git diff`
8. recent commits
9. related PR
10. Current-state Documentation / ADR

Checkpointと現在のRepository Stateが異なる場合は、Repository Stateを優先して再調査します。

再開時は古いImplementation Planを復元するのではなく、**現在状態をもとに `.plans/` の md を作成または更新**し、変更強度に応じた `grill-me` / `grilling` のあとユーザー承認を得てから実装を再開します。

---

## ADR

重要な意思決定は、Implementation PlanやIssueコメントだけに残しません。

判断は3段階に分類します。

### Level 1 — Architecture Decision

例:

- Database
- Authentication / Authorization
- Multi-tenancy
- API Architecture
- Event Architecture
- Cloud Platform
- Service Boundary
- Data Ownership

原則としてADRを作成し、リポジトリ固有ルールに応じて実装前に人間の確認を得ます。

### Level 2 — Design Decision

例:

- Cache
- Retry
- Queue
- State Management
- Consistency Model
- Error Handling
- Background Processing
- 重要なLibrary / Framework

長期的な影響がある場合はADR候補として扱います。

### Level 3 — Implementation Decision

例:

- 関数分割
- 変数名
- 小規模なComponent抽出
- 局所的なRefactoring

通常ADRは不要です。

---

## OKFによるドキュメンテーション

恒久ドキュメントはOpen Knowledge Format（OKF）のKnowledge Bundleとして管理します。

標準構成:

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

### Current-state Documentation

「現在何が正しいか」を記述します。

例:

- Business Requirements
- Architecture
- UI Capability
- Backend Capability
- API Contract
- Infrastructure

### Decision Record

「なぜその設計を選んだか」を記録します。

### Release Log

「どのバージョンで何が変わったか」を記録します。Phase 6 では観測可能な変更を `## v?.?.? (未確定)` 見出し下へ追記します。バージョンタグ確定時は未確定見出しを Semantic Versioning（SemVer、`vMAJOR.MINOR.PATCH`）の確定見出しへ置き換え、`git tag` を作成します。

Implementation PlanやSession CheckpointはOKF Knowledge Bundleへ保存しません。

---

## Progressive Disclosure

この Skill 自体も Progressive Disclosure 構成です。

- **入口**: `SKILL.md` — Phase 0–7 の概要と reference 対応表のみ
- **詳細**: `references/` — Phase やトピックごとの詳細ルール

Agent は最初に `SKILL.md` だけを読み、該当 Phase の作業に入る時点で必要な reference だけを読みます。`mcp-server-engineering` Skill と同じパターンです。

```text
implementation-workflow/
├── SKILL.md              # 入口（~150行）
├── README.md             # 人間向け概要
└── references/
    ├── github-issue-workflow.md
    ├── implementation-plan.md
    ├── decision-check.md
    ├── session-handoff.md
    ├── verification.md
    ├── okf-documentation.md
    ├── release-note.md
    └── completion-report.md
```

OKF Knowledge Bundle についても、`index.md` を入口として段階的に探索します。

```text
docs/index.md
    ↓
関連ディレクトリの index.md
    ↓
関連 Concept
    ↓
cross-link された Concept
    ↓
必要な場合のみ ADR / Release Log
```

---

## Documentation Reconciliation

実装完了後は、Implementation Planではなく**最終実装**を基準にドキュメントを整合させます。

| 問い | 保存先 |
|---|---|
| 現在何が正しいか？ | Current-state Documentation |
| なぜこの設計を選んだか？ | ADR |
| 何が変わったか？ | Release Log（`## v?.?.? (未確定)` セクション） |
| どのような過程で実装したか？ | 原則保存しない |

Phase 6 では Current-state Documentation、ADR、Release Log を最終実装と整合させます。

このステップによって、Implementation PlanやIssueコメントが恒久仕様書化することを防ぎます。

---

## SKILL.mdとAGENTS.mdの責務

### SKILL.md

複数プロジェクトで再利用可能な共通ワークフローを定義します。

例:

- GitHub Issue workflow
- Implementation Plan（`.plans/` への md 書き出し）
- Implementation Plan の grill-me / grilling による refinement（変更強度に応じて）
- ユーザー承認ゲート（Cloud / background agent も例外なし）
- Decision Check
- Session Handoff / Resume
- Verification
- Documentation Reconciliation
- OKF運用
- Completion Report

### AGENTS.md

リポジトリ固有の設定だけを定義します。

例:

- 使用するSkill
- GitHub Issue / PR運用
- Human Approvalルール
- Implementation Plan の一時ディレクトリ（既定は `.plans/`）
- OKF Bundleの配置
- Current-state Documentationのパス
- ADR / Release Logの保存先
- Framework / Runtime
- Test / Lint / Buildコマンド
- Deploymentルール

共通ワークフローを`AGENTS.md`へ重複記載しないことを推奨します。

---

## 導入方法

SkillをCoding Agentから利用できる場所へ配置します。

例:

```text
skills/
└── implementation-workflow/
    └── SKILL.md
```

Repository rootには`AGENTS.md`を配置します。

```text
repository/
├── AGENTS.md
├── docs/
├── src/
└── ...
```

`AGENTS.md`から`implementation-workflow` Skillを使用することを明示し、そのRepository固有のドキュメントパス、承認条件、技術スタック、Validationコマンドなどを設定します。

---

## 推奨運用

このSkillは、特に次のような開発で効果を発揮します。

- Claude Code / Codex等のCoding Agentを継続的に利用する
- 1つのIssueを複数セッションで実装する
- AIが設計判断を行う可能性がある
- Current-state Documentationを常に最新化したい
- ADRを過剰に増やさず重要判断だけ追跡したい
- AI向けContextをProgressive Disclosureしたい
- GitHub Issueを作業ログとして有効活用したい

---

## ファイル

```text
implementation-workflow/
├── SKILL.md
├── README.md
└── references/
    └── *.md
```

- `SKILL.md` — 共通実装ワークフロー（入口）
- `references/` — Phase / トピック別の詳細ルール
- `README.md` — この Skill の概要・導入・運用説明

---

## 設計原則

> **Planは `.plans/` の md として未来を考え、コミットしない。**  
> **Issueは作業をセッション間でつなぐ。**  
> **Codeは実装状態のSource of Truthとする。**  
> **OKFは現在の恒久知識を構造化する。**  
> **ADRは重要な判断理由を残す。**
