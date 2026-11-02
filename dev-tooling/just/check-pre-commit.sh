#!/usr/bin/env bash
set -euo pipefail

# The gate Job is already executing this aggregate for the staged tree. Its
# environment marker prevents a nested delegation attempt inside the Job.
if [[ -z "${LIVESPEC_GATE_CONTEXT:-}" ]]; then
    set +e
    uv run python -m livespec_dev_tooling.pre_commit_delegate run
    delegate_status=$?
    set -e
    case "$delegate_status" in
        0)
            exit 0
            ;;
        75)
            ;;
        *)
            exit "$delegate_status"
            ;;
    esac
fi

just check-plugin-structure
just check-lint
just check-format
