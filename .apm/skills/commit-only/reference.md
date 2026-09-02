# Commit Message Reference

## Language

- `language = "ja"`
- Write commit summaries and bodies in Japanese unless there is a strong project reason to do otherwise.

## Required Format

```text
<Prefix>: <サマリ（命令形/簡潔に）>

- 変更内容1
- 変更内容2

Refs: #<Issue番号>（任意）
BREAKING CHANGE: <内容>（任意）
```

## Prefixes

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

## Generation Rules

- Inspect actual uncommitted diffs with `git diff` / `git diff --cached` before writing a commit message.
- Do not infer the message only from an issue title or branch name.
- Keep the first line concise, around 50 Japanese characters where possible, without a final punctuation mark.
- Use bullet points in the body to list concrete changes, impact, migration notes, risks, or rollback notes where relevant.

## Avoid

- A summary written only in a language other than Japanese.
- Vague summaries such as `update` or `fix bug`.
- A long unstructured body without bullets.
- Commits that only weaken or bypass static analysis without meaningful improvement.
