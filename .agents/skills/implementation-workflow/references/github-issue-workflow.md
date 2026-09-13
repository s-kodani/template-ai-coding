# GitHub Issue Workflow

Phase 0 の詳細。本リポジトリでは `AGENTS.md` の GitHub Work Item Policy で Issue 紐付けを必須とする。

Phase 0 の前に、`SKILL.md` の「作業開始前: 最新 default branch の取り込み」を完了する。

## 既存 Issue の確認（必須）

新しい Issue を起票する前に、**すでにユーザーが手動で作成した Issue が存在する可能性を必ず確認**する。

ユーザーから対象 Issue が明示されていない場合:

> この作業に対応する GitHub Issue はすでに作成済みですか？  
> 作成済みの場合は Issue 番号または URL を指定してください。未作成の場合は新規 Issue として進めます。

ルール:

- 既存 Issue の有無を確認せず、新規 Issue を作成してはいけない
- ユーザーが既存 Issue を指定した場合は、その Issue を作業 Issue として使用する
- ユーザーが「未作成」と回答した場合にのみ、新規 Issue を起票する
- ユーザーが現在の依頼内ですでに Issue 番号または URL を指定している場合は、再確認せずその Issue を使用する
- 既存 Issue が作業目的と明らかに一致しない場合は、勝手に流用せずユーザーへ確認する
- Issue の重複作成を避けることを優先する

Issue は実装計画の保存場所ではない。

1. **Issue 本文** — 現在有効な作業契約
2. **Issue コメント** — 追記型の作業履歴、Checkpoint、重要な変更経緯

## Issue 本文

時間経過で陳腐化しにくい情報だけを記載する。

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

- [ ] 検証可能な完了条件 A
- [ ] 検証可能な完了条件 B

## Constraints

- ...

## Related Knowledge

- Current-state Documentation:
- ADR:
- Related Issue / PR:
```

本文へ保存しないもの:

- 詳細な Implementation Plan
- 叙事的な進捗率・日報（「何割終わった」「今日はこれをした」）
- 「次に何をするか」の一時的メモ
- 一時的な調査結果
- 未整理の Scratch Note
- Session 固有の状態

Acceptance Criteria の `[ ]` / `[x]` は作業契約の充足状態であり、叙事的進捗ではない。本文に持たせてよい。

## Acceptance Criteria タスクリスト

Acceptance Criteria は GitHub タスクリストで書く。実装 ToDo（「ファイル X を直す」）にはしない。検証可能な完了条件にする。

### 着手時の正規化

Phase 0 または Resume で本文を読んだとき、Acceptance Criteria が箇条書き（`- 条件`）なら、文言を変えずに `- [ ] 条件` へ変換する。変換したらコメントで理由を残す。既存 Issue の一括変換はしない。

### 再評価のタイミング

進捗コメントと同じ区切りで、**全項目**を再評価する。

- Phase 4 の実装が一区切りついた
- 修正対応が終わった
- その区切りの検証直後
- Phase 7 / Phase 8 の Close 判定前

ファイル保存や個別の編集操作ごと、同一区切り内の連続コミットごとには更新しない。

### チェック規則

1. 現在の Repository 状態で満たしたものだけ `[x]` にする
2. 後続変更で崩れた項目は `[ ]` に戻す
3. 未検証・部分実装ではチェックしない。検証していない項目を完了扱いしない
4. 進捗コメントに、今回 `[ ]` → `[x]` / `[x]` → `[ ]` した項目と根拠を書く
5. 契約そのもの（文言の追加・削除・意味変更）は Scope / Requirement Change として本文を更新し、コメントへ履歴を残す

### 本文の更新手順

チェック状態だけを変える。Goal / Scope など他節は契約変更がない限り触らない。

```bash
gh issue view <issue-number> --json body --jq .body > /tmp/issue-body.md
# Acceptance Criteria の [ ] / [x] だけを編集する
gh issue edit <issue-number> --body-file /tmp/issue-body.md
```

本文を書けない場合（`gh` read-only 等）は、同じ再評価結果を進捗 / PR コメントへ書き、本文を更新したと偽らない。

## Issue 本文の鮮度維持

Goal、Scope、Acceptance Criteria の文言、Constraints など作業契約が変更された場合は Issue 本文を更新し、同時にコメントへ履歴を残す。充足状態の `[x]` 更新だけなら Scope / Requirement Change コメントは不要（進捗コメントの Acceptance Criteria 欄で足りる）。

```markdown
## Scope / Requirement Change

### Changed
- 変更した内容

### Reason
- 変更理由

### Impact
- Implementation / Verification / Documentation への影響
```

## Issue コメントの追記原則

作業履歴は原則 Append-only。過去の Checkpoint / 進捗 / Review コメントを後から書き換えてはいけない。誤りが判明した場合は新しいコメントで訂正する。

会話や PR 説明への記載だけで、所定の投稿先へのコメントを省略してはいけない。投稿先は「Issue と PR のコメント分担」に従う。

---

## Issue と Pull Request の関係（1:N）

1 Issue に対して PR は 0〜複数（**1:N**）。複数 PR に分割する場合も、作業契約は Issue 1 件に集約する。

### 紐付けルール

- 各 PR 本文には **`Refs #<issue>`** を付ける（`src/` 変更時は CI 必須）
- Issue 本文の `Related Issue / PR:` に、紐づく PR の URL または番号を追記・更新する
- 進捗コメントの `Related PR` に、その区切りで扱った PR を書く

### `Refs` と `Closes` の使い分け

| キーワード | 用途 | Issue Close |
|---|---|---|
| `Refs #<issue>` | **デフォルト**。作業中・後続 PR あり・1:N のいずれでも使う | 自動 Close しない |
| `Closes #<issue>` | **本ワークフローでは PR 本文に使わない** | PR **merge** 時に GitHub が自動 Close し、Phase 8 前に Issue が閉じる恐れがある |

Issue の Close は Phase 8 完了後に**手動**で行う。PR merge による自動 Close に頼らない。

### Issue Close の順序

Issue を Close する前に、次をすべて満たす。

1. Phase 8（Review & Compliance）が `pass` または `pass-with-nits`
2. **Issue 本文の Acceptance Criteria 節を読み直し、タスクリスト項目がすべて `[x]` であることを確認した**（必須ゲート。`[ ]` が 1 件でも残っていれば Close しない）
3. **その Issue に紐づく作業 PR がすべて closed**（`merged` または `closed`。open が残っていない）

1 Issue に複数 PR がある場合、**最後の PR が closed になるまで Issue を Close しない**。

#### AC 全チェック確認（Close 直前・必須）

Close 操作の直前に、Issue 本文の Acceptance Criteria 節を再読する。タスクリスト項目がすべて `[x]` であることを確認してから Close する。

- `[ ]` が 1 件でも残っていれば Close しない。Phase 4 に戻るか、AC を満たす作業・検証を完了してから本文を更新する
- 例外は **明示的撤回** のみ。Scope / Requirement Change コメントで理由を残し、該当 AC 行を本文から削除する。`[ ]` のまま残した AC がある状態では Close しない
- Phase 8 Review コメント（PR 存在時は PR 側）に `AC body verified: all [x]` または `blocked: unchecked items remain` を記載する

Close 判定手順の例:

```bash
gh issue view <issue-number> --json body --jq .body > /tmp/issue-body.md
# Acceptance Criteria 節に `- [ ]` が残っていないことを目視または grep で確認
grep -n '\- \[ \]' /tmp/issue-body.md  # AC 節内にヒットしたら Close 不可
```

作業 PR の確認例:

```bash
gh pr list --state all --search "refs:#<issue-number>" --json number,state,title,url
```

Issue 本文の `Related Issue / PR:` と進捗コメントの `Related PR` も照合する。確認できない PR は `not checked` とし、Issue Close を進めない。

### 例外

- 作業に PR が存在しない変更（Skill / docs のみで PR を作らない運用など）では、PR Close 条件は該当しない
- 誤って起票した PR を `closed`（未 merge）にした場合も「closed」として数える。残作業があるなら新しい PR を起票し、すべて closed になるまで Issue は open のまま

---

## Issue と PR のコメント分担

Issue は作業契約と Pre-PR 履歴、PR は Post-PR の実装・レビュー履歴を担う。Acceptance Criteria の `[ ]` / `[x]` 更新は常に Issue 本文が正。

| フェーズ | 投稿先 | 内容 |
|---|---|---|
| 着手（Plan 承認後・実装前） | Issue | スコープカバレッジ、作業ブランチ、Implementation Plan |
| PR 作成まで | Issue | 進捗コメント、AC 再評価 |
| PR 作成時 | Issue | PR 作成の旨のみ |
| PR マージ時 | Issue | PR マージの旨のみ |
| PR 作成後〜マージ前 | PR | 以降の対応・検証・レビュー結果・Completion Report |
| 当初スコープ外 | Issue | コメント + Issue 本文更新 |
| AC チェック | Issue 本文 | 対応の都度 `[x]` 更新 |

### Pre-PR（Issue へ）

- 着手コメント（Work Start）
- Implementation Update（`agent-progress:v1`）
- Scope / Requirement Change（当初スコープ外を含む）
- Work Checkpoint（open PR がない場合。open PR がある場合は PR 側 — `references/session-handoff.md`）

### PR 作成時（Issue へ・最小通知）

PR 作成時は Issue へ詳細を書かず、事実通知のみ残す。

```markdown
<!-- agent-pr-opened:v1 -->
PR を作成しました: <PR URL>
Refs #<issue>
```

Issue 本文の `Related Issue / PR:` に PR URL を追記してよい。

### PR マージ時（Issue へ・最小通知）

PR マージ時も Issue へ詳細を書かず、事実通知のみ残す。Post-PR の詳細は PR 側に残したままとする。

```markdown
<!-- agent-pr-merged:v1 -->
PR がマージされました: <PR URL>
```

1 Issue に複数 PR がある場合（1:N）、**各 PR のマージごと**に Issue へ 1 件ずつ残す。Issue 本文の `Related Issue / PR:` は merged 状態が分かるよう更新してよい。

### Post-PR（該当 PR へ）

open PR が存在する場合、次は **該当 PR のコメント**へ投稿する。

- Implementation Update（`agent-progress:v1`）
- review-fix、Phase 5 検証結果
- Phase 7 Completion Report（`agent-completion:v1`）
- Phase 8 Review（`agent-workflow-review:v1`）
- Work Checkpoint（セッション中断時）

フォーマットは Issue 版を流用する。`Related PR` は自 PR を指す。Acceptance Criteria 欄にチェック変更根拠を書くが、**本文の `[ ]` / `[x]` 更新は Issue 側**で行う。

### 当初スコープ外の対応

Issue 本文の Scope / Acceptance Criteria から外れる作業を行う場合:

1. Issue へ Scope / Requirement Change コメントを残す
2. Issue 本文（Goal / Scope / Acceptance Criteria 等）を更新する
3. `.plans/` の Plan を更新し、再承認を得てから続行する

### 例外（PR なし）

Skill / docs のみ等で PR を作らない運用では、着手・進捗・Completion Report・Review を従来どおり Issue のみへ残す。

### 書き込みできない場合

`gh` が read-only 等で所定の投稿先へ書けない場合:

1. 同じ本文を、書ける側（Issue または PR）のコメントへ投稿する
2. ユーザー向け報告に、書けなかった理由と本文の要約を残す
3. 投稿できたと偽らない

---

## 着手コメント（Work Start）

Phase 2 で Implementation Plan を `.plans/` に書き出しユーザー承認を得た直後、Phase 3 / 4 に入る前に、紐づく作業 Issue へ着手コメントを残す。

Resume 時は PR が未作成なら再投稿不要。作業ブランチ・Plan・カバレッジが変わった場合のみ追記する。

### 必須冒頭行

コメント先頭に、Issue のどの範囲をこの作業ブランチでカバーするかを明記する。

- `**Coverage: full**` — Issue の Goal / Scope / Acceptance Criteria をこの作業ブランチですべてカバーする
- `**Coverage: partial**` — 一部のみ。対象 AC 項目と In Scope を列挙する

### 必須項目

- 作業ブランチ名
- Implementation Plan（`.plans/` の要約または全文。Plan は Issue 本文には載せない）

### Format

```markdown
<!-- agent-work-start:v1 -->

**Coverage: full** | **Coverage: partial**

## Work Start

### Branch
`<branch>`

### Implementation Plan
（`.plans/` の内容）

### Covered Acceptance Criteria（partial のとき）
- 対象 AC 項目

### In Scope（partial のとき）
- このブランチで扱う範囲
```

### 完了ゲート

着手コメントを Issue へ投稿し、URL またはコメント一覧で存在を確認するまで、Phase 3 / 4 に進まない。

```bash
gh issue comment <issue-number> --body-file <path-to-markdown>
```

---

## 実装・修正の進捗コメント（必須）

エージェント側の実装または修正対応が一段落するたびに、進捗コメントを残し、本文の Acceptance Criteria タスクリストを再評価する。セッション終了時の Work Checkpoint（`references/session-handoff.md`）とは別物である。

**投稿先**: open PR がない間は Issue。open PR がある場合は該当 PR（「Issue と PR のコメント分担」参照）。

### 残すタイミング

次のいずれかを満たしたら、その区切りを完了と報告する前にコメントする。

- Phase 4 の実装が一区切りついた（コミットまたはプッシュしたスライス、ユーザー依頼の実装完了）
- テスト失敗・レビュー指摘・ユーザー follow-up への修正対応が終わった
- その区切りの検証（Phase 5 相当）を実行した直後（結果を同じコメントに含めてよい）

残さなくてよいもの:

- ファイル保存や個別の編集操作ごと
- 同一区切り内の連続コミットごと（区切りの最後に 1 件）
- Phase 7 Completion Report が、そのセッション最後の実装区切りを兼ねる場合（重複投稿はしない）

Work Checkpoint は作業が未完のままセッションを終えるときに残す。進捗コメントは完了した区切りの事実を残す。

### 完了ゲート

次を満たすまで、その区切りを完了としない。

1. Acceptance Criteria タスクリストを再評価し、書ける場合は本文の `[ ]` / `[x]` を更新した
2. 進捗コメントを投稿した（Acceptance Criteria 欄に今回のチェック変更を含む）
3. 投稿先にコメントが存在する（URL または Issue コメント一覧で確認した）

投稿していないのに「Issue へ残した」と報告してはいけない。本文を更新できない場合は、その理由と再評価結果を同じコメントに書く。

### 投稿手順

シェル解釈を避けるため、本文はファイル経由で投稿する。

Pre-PR（Issue）:

```bash
gh issue comment <issue-number> --body-file <path-to-markdown>
```

Post-PR（該当 PR）:

```bash
gh pr comment <pr-number> --body-file <path-to-markdown>
```

ManagePullRequest 等の PR コメント用ツールがある場合はそれを使ってよい。

投稿が成功したら、返されたコメント URL を控える。失敗したら 1 回再試行する。

### 書き込みできない場合

所定の投稿先（Issue または PR）へ書けない場合は、「Issue と PR のコメント分担」のフォールバックに従う。

### 進捗コメント Format

```markdown
<!-- agent-progress:v1 -->

## Implementation Update

### Kind
`implementation` | `fix` | `review-fix` | `docs`

### Repository State
- Branch: `<branch>`
- HEAD: `<commit-sha>`
- Related PR: `<PR or none>`

### Done
- この区切りで完了した事実

### Changed Files / Components
- 主な変更箇所

### Verification
- 実行したコマンドと結果
- 未実施があればその旨

### Acceptance Criteria
- Checked: この区切りで `[x]` にした項目。なければ `none`
- Unchecked: この区切りで `[ ]` に戻した項目。なければ `none`
- Unchanged unmet: 未充足のままの項目。なければ `none`
- Body updated: `yes` | `no`（`no` のときは理由）

### Remaining
- 残作業。なければ `none`

### Next
- 次に行うこと
```

値を確認できない項目は推測せず `unknown` または `not checked` と書く。予定ではなく事実を書く。

