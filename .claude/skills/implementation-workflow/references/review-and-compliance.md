# Review and Compliance

Phase 8 の詳細。Phase 7 Completion Report のあと、Issue を Close する前に実施する。

Issue と PR は **1:N**。Issue Close は、紐づく**作業 PR がすべて closed**（merged または closed）になったあと、Phase 8 が pass したときに**手動**で行う。PR 本文の `Closes #<issue>` による自動 Close は使わない。詳細は `references/github-issue-workflow.md`。

## 目的

一連のワークフローが完了した最終状態について、次を確認する。

- 変更内容が Acceptance Criteria と実装方針に照らして妥当か（コードレビュー）
- この Skill の必須ステップを省略していないか（ワークフロー遵守）

レビュー結果は open PR がある場合は PR コメント、PR がない場合は Issue コメントへ残す。投稿手順は `references/github-issue-workflow.md` に従う。

## 実施タイミング

1. Phase 5〜7 まで完了したあと
2. ユーザーへ「完了」と報告する前
3. Issue を Close する前（**Issue 本文 AC がすべて `[x]` であることを必ず確認する**。**紐づく作業 PR がすべて closed であることも確認する**）

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

Phase 8 レビューコメント（投稿先が PR でも Issue でも）に載せる項目:

```markdown
- [ ] 最新 default branch を取り込んだ
- [ ] 作業 Issue を確定し、各 PR に `Refs #<issue>` を付けた（該当時。`Closes` は使わない）
- [ ] Plan 承認後に Issue へ Work Start コメントを残した（Coverage / Branch / Plan）
- [ ] 紐づく作業 PR を Issue 本文または `gh pr list` で把握した（1:N の場合は一覧を Review コメントに残す）
- [ ] Implementation Plan を `.plans/` へ書き出し、Phase 2 / 4 で `ponytail` Skill を読み、承認後に実装した
- [ ] 変更強度に応じた grilling を行った、または省略理由が「軽微」である
- [ ] Phase 3 Decision Check を行い、必要な ADR を扱った
- [ ] 実装・修正の区切りごとに進捗コメントを残し（Pre-PR: Issue / Post-PR: PR）、Acceptance Criteria タスクリストを再評価した（または書き込み不可を明示した）
- [ ] Issue 本文 Acceptance Criteria がすべて `[x]` であることを確認した（または撤回理由をコメントした）
- [ ] Phase 5 検証を実行し、未実施を成功と報告していない
- [ ] Phase 6 で恒久ドキュメント / Release Log を最終実装へ合わせた
- [ ] Phase 7 Completion Report を投稿した（Post-PR 時は PR、否则 Issue）
- [ ] PR 作成・マージ時に Issue へ最小通知を残した（該当時）
- [ ] 本レビュー結果を投稿した（Post-PR 時は PR、否则 Issue）
```

**投稿先が PR のとき、次は載せない。** Issue Close ゲートであり、当該 PR が open なのは正常。

```markdown
- [ ] 紐づく作業 PR がすべて closed（merged または closed）。open が残っている場合は Issue を Close しない
```

この項目は Issue Close 直前にだけ確認する。PR なしで Phase 8 を Issue へ投稿する場合も、Close する時点まで `[x]` にしない。

`AGENTS.md` が追加で要求する項目（例: Skill 同期、Release-Note 宣言）があれば、同じコメントに足す。

## 判定と次アクション

| 判定 | 意味 | 次の行動 |
|---|---|---|
| `pass` | must-fix なし。Issue 本文 AC がすべて `[x]` | レビュー完了。Issue Close は作業 PR がすべて closed になってから |
| `pass-with-nits` | 任意改善のみ。Issue 本文 AC がすべて `[x]` | nits を残課題としてコメント。Issue Close は作業 PR がすべて closed になってから |
| `must-fix` | 欠陥、ワークフロー欠落、Issue 本文 AC に未チェック | Phase 4 に戻る、AC を満たして本文を更新してから Phase 8 をやり直す |

open の作業 PR は Phase 8 の must-fix にしない。Issue Close を止める条件である。

must-fix の無限ループを避ける。再レビューは修正範囲に限定する。任意改善は残課題に回し、**open PR が無い**場合は Close を止めない。

Issue Close の条件は `references/completion-report.md` も満たすこと。作業 PR が存在しない変更では PR Close 条件は該当しない。

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
- AC body verified: `all [x]` | `blocked: unchecked items remain`
- Checklist:
  - [ ] ...

### Follow-ups
- none
```

値を確認できない項目は `not checked` と書き、完了扱いにしない。
