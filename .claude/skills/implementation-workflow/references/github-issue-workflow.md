# GitHub Issue Workflow

Phase 0 の詳細。`AGENTS.md` の GitHub Work Item Policy と併用する。

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

作業履歴は原則 Append-only。過去の Checkpoint コメントを後から書き換えてはいけない。誤りが判明した場合は新しいコメントで訂正する。
