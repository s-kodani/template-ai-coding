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

- ...
- ...

## Constraints

- ...

## Related Knowledge

- Current-state Documentation:
- ADR:
- Related Issue / PR:
```

本文へ保存しないもの:

- 詳細な Implementation Plan
- 現在の進捗率
- 「次に何をするか」の一時的メモ
- 一時的な調査結果
- 未整理の Scratch Note
- Session 固有の状態

## Issue 本文の鮮度維持

Goal、Scope、Acceptance Criteria、Constraints など作業契約が変更された場合は Issue 本文を更新し、同時にコメントへ履歴を残す。

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

会話や PR 説明への記載だけで、Issue コメントを省略してはいけない。

---

## 実装・修正の進捗コメント（必須）

エージェント側の実装または修正対応が一段落するたびに、紐づく作業 Issue へ進捗コメントを残す。セッション終了時の Work Checkpoint（`references/session-handoff.md`）とは別物である。

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

1. 進捗コメントを投稿した
2. 投稿先にコメントが存在する（URL または Issue コメント一覧で確認した）

投稿していないのに「Issue へ残した」と報告してはいけない。

### 投稿手順

シェル解釈を避けるため、本文はファイル経由で投稿する。

```bash
gh issue comment <issue-number> --body-file <path-to-markdown>
```

投稿が成功したら、返されたコメント URL を控える。失敗したら 1 回再試行する。

### 書き込みできない場合

`gh` が read-only、認証不足、権限不足などで Issue へ書けない場合:

1. 同じ本文を、存在する PR のコメントへ投稿する（PR コメント用ツールがあればそれを使う）
2. ユーザー向け報告に、Issue へ書けなかった理由と本文の要約を残す
3. Issue へ投稿できたと偽らない

環境ポリシーが `gh` の書き込みを禁じている場合は、禁じられたコマンドを試さず、上記フォールバックへ進む。

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

### Remaining
- 残作業。なければ `none`

### Next
- 次に行うこと
```

値を確認できない項目は推測せず `unknown` または `not checked` と書く。予定ではなく事実を書く。

