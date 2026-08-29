#!/usr/bin/env bash
# Configure required CI status checks on main via GitHub repository rulesets.
# Requires a token with admin access to the repository (classic: repo scope;
# fine-grained: Administration read/write).
set -euo pipefail

REPO="${GITHUB_REPOSITORY:-s-kodani/template-ai-coding}"
RULESET_NAME="${BRANCH_PROTECTION_RULESET_NAME:-main-required-ci}"
BRANCH_REF="${BRANCH_PROTECTION_REF:-refs/heads/main}"

REQUIRED_CHECKS=(
  quality
  security
  build-and-scan
  okf
)

if ! command -v gh >/dev/null 2>&1; then
  echo "error: gh CLI is required" >&2
  exit 1
fi

if ! gh auth status -h github.com >/dev/null 2>&1; then
  echo "error: authenticate with gh auth login (admin-capable token)" >&2
  exit 1
fi

checks_json="$(printf '%s\n' "${REQUIRED_CHECKS[@]}" | jq -R . | jq -s 'map({context: .})')"

payload="$(jq -n \
  --arg name "$RULESET_NAME" \
  --arg ref "$BRANCH_REF" \
  --argjson checks "$checks_json" \
  '{
    name: $name,
    target: "branch",
    enforcement: "active",
    conditions: {
      ref_name: {
        include: [$ref],
        exclude: []
      }
    },
    rules: [
      {
        type: "required_status_checks",
        parameters: {
          strict_required_status_checks_policy: true,
          do_not_enforce_on_create: false,
          required_status_checks: $checks
        }
      }
    ]
  }')"

existing_id="$(gh api "repos/${REPO}/rulesets" --jq ".[] | select(.name == \"${RULESET_NAME}\") | .id" | head -n1 || true)"

if [[ -n "$existing_id" ]]; then
  echo "Updating ruleset ${RULESET_NAME} (id=${existing_id}) on ${REPO}"
  gh api \
    --method PUT \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "repos/${REPO}/rulesets/${existing_id}" \
    --input - <<<"$payload" >/dev/null
else
  echo "Creating ruleset ${RULESET_NAME} on ${REPO}"
  gh api \
    --method POST \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "repos/${REPO}/rulesets" \
    --input - <<<"$payload" >/dev/null
fi

echo "Branch protection ruleset applied. Required checks:"
printf '  - %s\n' "${REQUIRED_CHECKS[@]}"
