# Review and Compliance

Phase 8 の詳細。Phase 7 Completion Report のあと、Issue を Close する前に実施する。

IssueとPRは1:N。通常納品とmerge後のIssue完了は`delivery.md`に従い分離する。必要PR1件以上・全件merged・最終SHAのCI/人間承認/ACの実状態確認後だけ手動Closeする。PR本文の自動Closeキーワードは使わない。

## 目的

一連のワークフローが完了した最終状態について、次を確認する。

- 変更内容が Acceptance Criteria と実装方針に照らして妥当か（コードレビュー）
- この Skill の必須ステップを省略していないか（ワークフロー遵守）

レビュー結果は open PR がある場合は PR コメント、PR がない場合は Issue コメントへ残す。投稿手順は `references/github-issue-workflow.md` に従う。

## 実施タイミング

1. Phase 5〜7 まで完了したあと
2. ユーザーへ「完了」と報告する前
3. Issue Close前（`delivery.md`のCloseゲートが成功し、merge後の最終確認ができたとき）

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
- [ ] 主要イベントで進捗コメントを残し（PR 作成前の一区切り / Phase 5 / レビュー修正。Pre-PR: Issue / Post-PR: PR）、Acceptance Criteria タスクリストを再評価した（または書き込み不可を明示した）
- [ ] Issue 本文 Acceptance Criteria がすべて `[x]` であることを確認した（または撤回理由をコメントした）
- [ ] Phase 5 検証を実行し、未実施を成功と報告していない
- [ ] Phase 6 で恒久ドキュメント / Release Log を最終実装へ合わせた
- [ ] Phase 7 Completion Report を投稿した（Post-PR 時は PR、否则 Issue）
- [ ] PR 作成・マージ時に Issue へ最小通知を残した（該当時）
- [ ] 通常納品をcommit/push/PR提出まで進め、Work PRs登録とsubmitted validatorの結果を確認した（CI待ち等は区別して報告）
- [ ] 本レビュー結果を投稿した（Post-PR 時は PR、否则 Issue）
```

**投稿先が PR のとき、次は載せない。** Issue Close ゲートであり、当該 PR が open なのは正常。

```markdown
- [ ] 必要PR1件以上・全件merged・最終SHAのCI/人間承認/ACをClose validatorで確認した
```

この項目は Issue Close 直前にだけ確認する。PR なしで Phase 8 を Issue へ投稿する場合も、Close する時点まで `[x]` にしない。

`AGENTS.md` が追加で要求する項目（例: Skill 同期、Release-Note 宣言）があれば、同じコメントに足す。

## 判定と次アクション

| 判定 | 意味 | 次の行動 |
|---|---|---|
| `pass` | must-fix なし。Issue 本文 AC がすべて `[x]` | PRレビュー完了。Issue Closeは`delivery.md`のmerge後ゲート成功後だけ |
| `pass-with-nits` | 任意改善のみ。Issue 本文 AC がすべて `[x]` | nitsを記録。Issue Closeは同じmerge後ゲート成功後だけ |
| `must-fix` | 欠陥、ワークフロー欠落、Issue 本文 AC に未チェック | Phase 4 に戻る、AC を満たして本文を更新してから Phase 8 をやり直す |

open の作業 PR は Phase 8 の must-fix にしない。Issue Close を止める条件である。

must-fixの無限ループを避け、再レビューは修正範囲に限定する。任意改善は残課題に回すが、Issue Close条件の不足をnitsとして免除しない。

PRなし・closed未merged・取得不能の状態でIssue Closeは不可。ユーザー明示のローカル限定作業はその事実を報告し、IssueはOpenのまま維持する。

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
