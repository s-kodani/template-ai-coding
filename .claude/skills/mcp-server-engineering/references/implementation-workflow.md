# Implementation Workflow

このreferenceは実装着手、GitHub Issue運用、checkpoint、セッション引き継ぎ、完了報告で読む。

## 1. 着手前

以下を確認する。

- `AGENTS.md`
- 関連Skill
- Architecture / ADR
- 使用SDK / version
- 対象Specification
- Test / CI
- Deployment
- 関連Issue

## 2. GitHub Issue

作業開始時にユーザーへ次を確認する。

```text
今回の作業について、すでに手動で作成済みのGitHub Issueはありますか？
```

既存Issueがある場合はそれを利用する。
既存Issueの確認前に新規Issueを起票しない。

新規Issueを作る場合は、少なくとも以下を記録する。

- 背景 / Problem
- Goal
- Scope
- Out of Scope
- MCP specification / SDK version
- Architecture decision
- Tool / Resource / Prompt changes
- Security considerations
- Test plan
- Completion criteria

## 3. Issueを作業ログとして維持する

Issue本文を着手時の静的な計画書のまま放置しない。
設計判断や状況が変わったら更新する。

最低限、以下を陳腐化させない。

- Scope
- Current status
- Architecture decision
- Remaining work
- Risks / blockers
- Verification status

## 4. Checkpoint

長い作業、セッション終了前、大きな設計変更後にcheckpointを残す。

```markdown
## Checkpoint

### Current state
- ...

### Completed
- ...

### Decisions
- ...

### Changed files
- ...

### Verification
- ...

### Remaining
- ...

### Next action
1. ...
2. ...

### Risks / assumptions
- ...
```

「次のセッションが会話履歴なしでも再開できるか」を基準にする。

## 5. セッション再開

再開時は、最初にIssue / checkpoint / git diff / current testsを確認する。

以前の会話記憶だけで作業を再開しない。

確認順序の例:

1. Issue本文と最新checkpoint
2. Current branch / git status / diff
3. 関連設計ドキュメント
4. 変更ファイル
5. Test結果
6. Remaining tasks

Issueの記述と実コードが矛盾する場合は、実コードを確認した上でIssueを最新化する。

## 6. 実装中

大きな変更単位ごとに以下を更新する。

- 何を実装したか
- 設計判断
- 仕様との差分
- Test結果
- 未解決事項

MCP version / SDK compatibilityに関する判断が変わった場合は必ず記録する。

## 7. 完了報告

完了時は以下をまとめる。

```markdown
## MCP Design

Specification:
SDK:
SDK version:
Transport:
Authentication:
Primitives:
State model:

## Implemented
- ...

## Verification
- Unit:
- Contract:
- Integration:
- Inspector:
- Security:
- Real client:

## Remaining Risks
- ...

## Compatibility
- Supported MCP versions:
- Supported clients:
- Known limitations:
```

未実施のTestを成功と記載しない。

## 8. 完了条件

Issueを閉じる前に確認する。

- Scopeが現状と一致している
- 完了条件を満たした
- Test結果が記録されている
- Remaining riskが記録されている
- TODOが別Issue化または明示されている
- 最新checkpointが不要になる程度にIssue本文が最新化されている
