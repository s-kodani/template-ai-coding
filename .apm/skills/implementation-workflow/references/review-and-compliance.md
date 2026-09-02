# Review and Compliance

Phase 8 の詳細。Phase 7 Completion Report のあと、Issue を Close する前に実施する。

## 目的

一連のワークフローが完了した最終状態について、次を確認する。

- 変更内容が Acceptance Criteria と実装方針に照らして妥当か（コードレビュー）
- この Skill の必須ステップを省略していないか（ワークフロー遵守）

レビュー結果は Issue コメントへ残す。投稿手順は `references/github-issue-workflow.md` に従う。

## 実施タイミング

1. Phase 5〜7 まで完了したあと
2. ユーザーへ「完了」と報告する前
3. Issue を Close する前

計画のみ・質問のみでコードも Skill も変えていない場合は Phase 8 不要。

## コードレビュー

実装エージェント自身が最終差分（作業ブランチと base branch の diff）をレビューする。会話上の自己評価だけで省略しない。

見る観点:

- Acceptance Criteria を満たしているか。本文タスクリストの未チェックが残っていないか（撤回した項目はコメント根拠があるか）
- スコープ外の変更が混ざっていないか
- テストが変更に見合っているか。失敗しているテストを無視していないか
- 秘密情報、認可バイパス、危険なデフォルトがないか
- Current-state / ADR / Release Log が最終実装と食い違っていないか
- デバッグ用の一時コードが残っていないか

ハーネスがプロジェクトの `review` サブエージェント（`.cursor/agents/review.md` / `.claude/agents/review.md`）を呼べるときは、自己レビューに加えて必ず起動する。`review` は読み取り専用であり、Issue / PR コメントは親エージェントが投稿する。自己レビューの代替にはしない。専用 subagent が使えない実行では、自己レビューだけでよい。

## ワークフロー遵守チェック

実施した事実だけを `[x]` にする。やっていない項目を完了扱いにしない。

```markdown
- [ ] 最新 default branch を取り込んだ
- [ ] 作業 Issue を確定し、PR に `Refs` / `Closes` を付けた（該当時）
- [ ] Implementation Plan を `.plans/` へ書き出し、承認後に実装した
- [ ] 変更強度に応じた grilling を行った、または省略理由が「軽微」である
- [ ] Phase 3 Decision Check を行い、必要な ADR を扱った
- [ ] 実装・修正の区切りごとに Issue 進捗コメントを残し、Acceptance Criteria タスクリストを再評価した（または書き込み不可を明示した）
- [ ] Acceptance Criteria に未チェックが残っていない、または撤回理由をコメントした
- [ ] Phase 5 検証を実行し、未実施を成功と報告していない
- [ ] Phase 6 で恒久ドキュメント / Release Log を最終実装へ合わせた
- [ ] Phase 7 Completion Report を Issue へ残した
- [ ] 本レビュー結果を Issue へ残した
```

`AGENTS.md` が追加で要求する項目（例: Skill 同期、Release-Note 宣言）があれば、同じコメントに足す。

## 判定と次アクション

| 判定 | 意味 | 次の行動 |
|---|---|---|
| `pass` | must-fix なし。未チェックの Acceptance Criteria もなし（または明示的撤回済み） | Issue を Close してよい（後続 PR がある場合は Close しない） |
| `pass-with-nits` | 任意改善のみ | nits を残課題としてコメントし、Close してよい |
| `must-fix` | 欠陥またはワークフロー欠落 | Phase 4 に戻る。修正後は進捗コメント → 再検証 → Phase 8 をやり直す |

must-fix の無限ループを避ける。再レビューは修正範囲に限定する。任意改善は残課題に回し、Close を止めない。

Issue Close の条件は `references/completion-report.md` も満たすこと。

## Review コメント Format

```markdown
<!-- agent-workflow-review:v1 -->

## Workflow Review

### Code Review
- Verdict: `pass` | `pass-with-nits` | `must-fix`
- Findings:
  - ...

### Workflow Compliance
- Verdict: `compliant` | `gaps`
- Checklist:
  - [ ] ...

### Follow-ups
- none
```

値を確認できない項目は `not checked` と書き、完了扱いにしない。
