#!/usr/bin/env bash
set -euo pipefail

inventory="check-targets.txt"
mapfile -t inventory_targets < <(
    sed -n 's/[[:space:]]*#.*//; /^[[:space:]]*check-/p' "$inventory" \
        | sed 's/^[[:space:]]*//; s/[[:space:]]*$//'
)

if [[ "${inventory_targets[*]}" != "$*" ]]; then
    echo "check purity inventory does not match the just check aggregate" >&2
    echo "inventory: ${inventory_targets[*]}" >&2
    echo "aggregate: $*" >&2
    exit 1
fi

uv run python -m livespec_dev_tooling.green_token undeclared "$@"
