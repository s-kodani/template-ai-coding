# Commit And PR Message Reference

## Commit Message

### Language

- `language = "ja"`
- Write commit summaries and bodies in Japanese unless there is a strong project reason to do otherwise.

### Required Format

```text
<Prefix>: <サマリ（命令形/簡潔に）>

- 変更内容1
- 変更内容2

Refs: #<Issue番号>（任意）
BREAKING CHANGE: <内容>（任意）
```

### Prefixes

- `feat`: 新機能の追加
- `fix`: バグ修正
- `refactor`: リファクタリング（挙動変更なし）
- `perf`: パフォーマンス改善
- `test`: テスト追加/修正
- `docs`: ドキュメント更新
- `build`: ビルド/依存関係の変更
- `ci`: CI関連の変更
- `chore`: 雑務（ツール設定/スクリプト等）
- `style`: スタイルのみの変更（コードロジック無関係）
- `revert`: 取り消し

Use `<Prefix>(scope):` when helpful.

### Generation Rules

- Inspect actual uncommitted diffs with `git diff` / `git diff --cached` before writing a commit message.
- Do not infer the message only from an issue title or branch name.
- Keep the first line concise, around 50 Japanese characters where possible, without a final punctuation mark.
- Use bullet points in the body to list concrete changes, impact, migration notes, risks, or rollback notes where relevant.

## Pull Request Message

### Language

- `language = "ja"`
- Write PR titles and bodies in Japanese unless there is a strong project reason to do otherwise.

### Title

```text
<Prefix>: <サマリ（命令形/簡潔に）>
```

- Use Conventional Commits-style prefixes such as `feat`, `fix`, `refactor`, `docs`, or `chore`.
- Keep the title concise, around 50 Japanese characters where possible, without a final punctuation mark.

### Body Template

```markdown
## 概要

このPRで実装・修正した内容の要約を記載

## 変更内容

- 変更点1の説明
- 変更点2の説明

## 技術的な詳細（任意）

- 必要に応じて実装の詳細や設計上の意図を記載

## テスト内容

- 実施したテストの種類
- 主要な動作確認の結果

## 関連Issue

- Closes #123
- Refs #456
```

### Generation Rules

- Inspect actual diffs and commit history before writing a PR title/body.
- Do not infer content only from the issue title or branch name.
- Include change scope, impact, and test results.
- Keep PR prefix and summary semantically aligned with the commit message format.

### Avoid

- A title/body written only in a language other than Japanese.
- Vague titles such as `update`, `fix issue`, or `changes`.
- Long unstructured text without sections or bullets.
- Claims that do not match the actual diff.
