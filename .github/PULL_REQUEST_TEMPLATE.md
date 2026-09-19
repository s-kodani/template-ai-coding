## Summary

<!-- 変更の概要を記載 -->

## Related Issue

<!-- src/ tests/ scripts/ infra/ e2e/ gateway/ .apm/ を変更する PR では Refs #<issue> が必須（CI 検証）。Closes / Fixes / Resolves は使わない -->

Refs #

## Release Note

<!-- src/ または infra/ を変更する PR では必須（CI 検証） -->

Release-Note: required

<!-- 観測可能な変更がない場合は以下に差し替え -->

<!-- Release-Note: not-required -->
<!-- Reason: （理由を1行以上） -->

## Checklist

- [ ] [implementation-workflow](.agents/skills/implementation-workflow/SKILL.md) に沿って実装した
- [ ] 対応 GitHub Issue を確認・紐付けした
- [ ] 主要イベント（PR 作成前の一区切り、Phase 5、レビュー修正）で進捗コメントを残し、Acceptance Criteria タスクリストを再評価した（Pre-PR: Issue / Post-PR: PR。書けない場合は書ける側へフォールバックし、理由を Notes に書いた）
- [ ] 完了後のコードレビューとワークフロー遵守チェックを実施した
- [ ] 検証を実行した（[project-verification](.agents/skills/project-verification/SKILL.md) 参照）
- [ ] `Release-Note: required` の場合、`docs/releases/log.md` の `## v?.?.? (未確定)` を更新した
- [ ] Skill / Agent 変更時、`uv run python scripts/check_skill_deploy.py --check` が通る
- [ ] Current-state Documentation / ADR を更新した（該当する場合）

## Verification

<!-- 実行したコマンドと結果 -->

```text

```

## Notes

<!-- レビュアー向けの補足 -->
