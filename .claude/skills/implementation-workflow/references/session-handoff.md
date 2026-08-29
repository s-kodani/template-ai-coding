# Session Handoff

Checkpoint 作成と Resume Protocol。

## Session Handoff Protocol

実装途中でセッションを終了する場合、`AGENTS.md` で指定された GitHub Issue へ Work Checkpoint コメントを追加する。

### Checkpoint を残すタイミング

- 作業途中でセッションを終了する前
- 別 Agent / 別セッションへ引き継ぐ前
- 大きなマイルストーン完了後に作業を中断する場合
- 未解決の Design Decision や外部状態を残したまま中断する場合

細かなコード変更ごとに Checkpoint を追加する必要はない。

### Checkpoint Format

```markdown
<!-- agent-work-checkpoint:v1 -->

## Work Checkpoint

### Repository State
- Branch: `<branch>`
- HEAD: `<commit-sha>`
- Working tree: `<clean | modified>`
- Related PR: `<PR or none>`

### Goal
- 現在取り組んでいる Goal

### Completed
- 完了した作業

### In Progress
- 実装途中の作業

### Remaining
- 未着手または未完了の作業

### Changed Files / Components
- 主な変更箇所

### Decisions Made
- このセッションで確定した重要な判断

### Pending Decisions
- 未確定の判断

### Verification
- 実行済み検証と結果
- 未実施の検証

### External State
- Migration 適用状況
- Cloud / SaaS / Feature Flag / Secret 等
- 該当なしの場合は `None`

### Blockers / Known Issues
- 失敗中の Test
- 未解決問題

### Next Action
1. 次セッションが最初に行う具体的な作業
```

値を確認できない項目は推測せず、`unknown` または `not checked` と記載する。

Checkpoint では**予定ではなく事実**を優先する。Implementation Plan を Checkpoint へそのままコピーしてはいけない。

---

## Resume Protocol

既存 Issue の途中作業を別セッションで再開する場合、コード変更前に:

1. `AGENTS.md` と適用 Skill を読む
2. Issue 本文から Goal / Scope / Acceptance Criteria / Constraints を確認
3. 最新の `agent-work-checkpoint:v1` コメントを特定
4. Checkpoint 以降のコメントをすべて確認
5. Repository の現在状態を確認（branch、HEAD、`git status`、diff、commits、PR）
6. Checkpoint と現在状態を比較
7. Changed Files / Completed / In Progress / Remaining が実コードと整合しているか確認
8. Pending Decisions が未解決のままか確認
9. External State が現在も有効か確認
10. 現在状態を基準に新しい Implementation Plan を作成し、必要なら grill-me / grilling
11. 必要に応じて Resume コメントを Issue へ残してから再開

### Source of Truth（優先順位）

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

Checkpoint は Navigation 情報であり、コードの Source of Truth ではない。Checkpoint 後に Repository が変更されている場合は差分を調査する。

### Subsequent Comment Rule

最新 Checkpoint 後のコメント（Scope 変更、Review feedback、Blocker 解消等）を無視して再開してはいけない。Issue 本文が陳腐化している場合は本文を更新し、変更履歴をコメントへ残す。
