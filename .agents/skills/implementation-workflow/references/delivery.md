# Delivery and Issue Completion

通常の実装・修正・Skill更新は、検証、commit、push、PR作成/更新までを納品範囲とする。既存PRがあれば同じPRへ反映する。これらを毎回追加承認の対象にしない。mergeは既存の人間承認・ブランチ保護に従い、PR提出の許可からmerge許可を推測しない。

「ローカルのみ」「commitのみ」「pushまで」「PR不要」はユーザーが明示した場合だけ適用する。エージェントがPlanへ書き込んだ対象外や「PR作成と言われていない」は例外の根拠にならない。明示例外でもIssueはOpenを維持し、通常の完了Closeとは扱わない。

## 状態と完了報告

| 状態 | 報告と次の操作 |
|---|---|
| ローカル実装・検証済み | PR提出前。通常納品は継続する |
| 最新変更をcommit/pushし、同じHEADのPRが存在 | 「PR提出済み」。CI待ち/レビュー待ちを区別し、IssueはOpen |
| 必要な作業PRが全件merged、最新SHAのCI・人間承認とAC充足を確認 | Issueの最終Close判定へ進める |

PRがOpenの段階でIssue全体を「完了」「Close済み」と報告しない。納品が妨げられた場合は実状態と理由をCheckpointへ記録し、完了扱いにしない。

## 作業PRの登録

Issue本文に次の節を維持し、必要な作業PRをすべて登録する。PR作成時の最小通知と同時に更新し、1:Nでも集合を省略しない。

```markdown
## Work PRs

- #142
```

PRなし、未登録PR、`closed`だが未merged、取得不能は正常完了の証拠にならない。誤作成PRの除外・作業撤回はユーザーの明示指示と変更理由を記録し、通常の実装納品と混同しない。

## 読み取り専用の実状態検査

リポジトリルートで次を実行し、成功した結果・PR URL・対象SHAを納品/最終確認に残す。

```bash
uv run python -m scripts.validate_delivery --repo OWNER/REPO --issue 139 --pr 142 --phase submitted
```

`submitted`は作業ツリーがclean、ローカルHEADとGitHub PR HEADが一致、PRがOpen、正しいbase/Issue参照、Issue本文のWork PRs登録を確認する。CI待ちなら「PR提出済み・CI待ち」と報告できる。

Issueを通常完了で閉じる直前には、登録した全PRを指定する。

```bash
uv run python -m scripts.validate_delivery --repo OWNER/REPO --issue 139 --pr 142 --phase close
```

`close`は次をGitHub APIの実状態から検証する。

- IssueのWork PRsが1件以上あり、指定した集合と一致する
- 全PRがそのIssueを参照し、対象baseへmerged済み
- 各PRの最終HEAD SHAに必要なCIチェックがすべて成功している
- 人間承認の証拠は、PR APIの`merged_by`が`type: User`かつ非空の`login`であること（作成者本人を含む）、または同じ最終SHAへの有効な人間のAPPROVEDレビューとする。bot/不明なマージ実行者だけでは承認としない
- 有効な人間レビューに未解消のCHANGES_REQUESTEDがない。Userによるマージでもこの条件を免除しない
- IssueのAcceptance Criteria節が空でなく、全項目が完了している

有効なAPPROVEDレビューは、PR作成者以外のUserで、OWNER/MEMBER/COLLABORATORによる最新の判断を使う。CI/承認は自己申告やチェック済みコメントを根拠にしない。API取得失敗や必要な証拠の欠落・不明・古いSHAは拒否する。判定成功後もPhase8/Documentationの確認を行い、merge後の最終確認が済んでからだけ手動Closeする。スクリプト自体はmerge/Issue更新をしない。

`User`はAPI上のアカウント種別であり、物理的な操作主体を証明しない。エージェントによるmergeには引き続き別の承認が必要。ブランチ保護のレビュー要件も、このClose判定から変更しない。

このvalidatorは通常操作の必須手順であり、汎用GitHub MCP/CLIによる直接Closeを技術的に禁止するものではない。接続側の権限制御を実装していない状態で「迂回不能」「絶対防止」と報告しない。
