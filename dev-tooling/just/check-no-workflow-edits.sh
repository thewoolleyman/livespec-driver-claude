#!/usr/bin/env bash
set -euo pipefail

changed_workflows="$(git diff --name-only origin/master..HEAD -- .github/workflows || true)"
if [[ -z "$changed_workflows" ]]; then
    exit 0
fi

echo "Factory branches must not create or update .github/workflows/ files." >&2
echo "Restore these paths to origin/master before publishing:" >&2
echo "$changed_workflows" >&2
echo >&2
git diff origin/master..HEAD -- .github/workflows >&2
exit 1
