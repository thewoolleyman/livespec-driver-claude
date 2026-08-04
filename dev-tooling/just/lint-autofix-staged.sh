#!/usr/bin/env bash
# Deliberately omit errexit: this pre-commit helper is advisory/autofix only.
# Unfixable issues must fall through to check-lint/check-format.
set -uo pipefail

mapfile -t staged < <(git diff --cached --name-only --diff-filter=AM | grep -E '\.py$' || true)
if [ "${#staged[@]}" -eq 0 ]; then
    exit 0
fi

uv run ruff check --fix --exit-zero --force-exclude "${staged[@]}"
uv run ruff format --force-exclude "${staged[@]}"
git add "${staged[@]}"
